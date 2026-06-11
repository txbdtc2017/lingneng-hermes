from __future__ import annotations

import json
import re
import time
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from lingneng.config.settings import LingNengSettings
from lingneng.tools.image_generation import ImageGenerationRequest, ImageGenerationResult


_TEXT_TO_IMAGE_PATH = "/api/aigc/image/text2img"
_DEFAULT_SIZE = "1024x1024"
_DEFAULT_QUALITY = "standard"
_IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp"}
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class AigcImageProviderError(RuntimeError):
    """Internal-only AIGC image provider failure."""


class TextToImageSubmitResponse(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    code: int | str
    msg: str | None = None
    data: dict[str, Any] | None = None
    task_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("task_id", "taskId"),
    )

    @model_validator(mode="after")
    def _fill_nested_task_id(self) -> "TextToImageSubmitResponse":
        if self.task_id or not isinstance(self.data, dict):
            return self
        task_id = self.data.get("task_id") or self.data.get("taskId")
        if isinstance(task_id, str):
            self.task_id = task_id.strip()
        return self


class AigcMaterialTaskResult(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    task_id: str = Field(validation_alias=AliasChoices("task_id", "taskId"))
    status: Literal["success", "error", "pending"]
    msg: str | None = None
    task_type: Literal["IMAGE", "VIDEO"] = Field(
        default="IMAGE",
        validation_alias=AliasChoices("task_type", "taskType"),
    )
    material_urls: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("material_urls", "materialUrls"),
    )
    model: str | None = None
    raw: dict[str, Any] | None = None

    @field_validator("task_id", mode="before")
    @classmethod
    def _normalize_task_id(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: Any) -> str:
        return str(value or "").strip().lower()

    @field_validator("task_type", mode="before")
    @classmethod
    def _normalize_task_type(cls, value: Any) -> str:
        return str(value or "IMAGE").strip().upper()

    @field_validator("material_urls", mode="before")
    @classmethod
    def _normalize_material_urls(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, list | tuple):
            values = list(value)
        else:
            return []
        return [str(item).strip() for item in values if str(item).strip()]

    @model_validator(mode="after")
    def _validate_required_task_id(self) -> "AigcMaterialTaskResult":
        if not self.task_id:
            raise ValueError("task_id is required")
        return self


class AigcResultStore(Protocol):
    def get(self, task_id: str) -> AigcMaterialTaskResult | None: ...

    def wait(
        self,
        task_id: str,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> AigcMaterialTaskResult: ...


def aigc_environment_for_app_env(app_env: str) -> str:
    if app_env.strip().lower() in {"prod", "production", "main"}:
        return "PROD"
    return "DEV"


class AigcImageClient:
    def __init__(
        self,
        *,
        base_url: str,
        env: str,
        timeout_seconds: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.endpoint_url = _text_to_image_endpoint_url(base_url)
        self.env = aigc_environment_for_app_env(env)
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client

    def submit_text_to_image(self, *, prompt: str, size: str, quality: str) -> str:
        payload = {
            "prompt": prompt,
            "size": normalize_image_size(size),
            "quality": normalize_image_quality(quality),
            "env": self.env,
        }
        try:
            response = self._post(payload)
            response.raise_for_status()
            response_model = TextToImageSubmitResponse.model_validate(response.json())
        except AigcImageProviderError:
            raise
        except Exception as exc:
            raise AigcImageProviderError("aigc image submit failed") from exc

        if str(response_model.code) != "200":
            raise AigcImageProviderError("aigc image submit failed")
        task_id = (response_model.task_id or "").strip()
        if not task_id:
            raise AigcImageProviderError("aigc image submit failed")
        return task_id

    def _post(self, payload: dict[str, str]) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.post(
                self.endpoint_url,
                json=payload,
                timeout=self.timeout_seconds,
            )
        with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
            return client.post(self.endpoint_url, json=payload)


class RedisAigcResultStore:
    def __init__(
        self,
        *,
        redis_client: Any,
        key_prefix: str,
    ) -> None:
        self.redis_client = redis_client
        self.key_prefix = key_prefix.strip() or "lingneng-agent"

    @classmethod
    def from_settings(cls, settings: LingNengSettings) -> "RedisAigcResultStore":
        import redis

        socket_timeout = _redis_socket_timeout(settings)
        return cls(
            redis_client=redis.Redis.from_url(
                settings.aigc_redis_url,
                decode_responses=True,
                socket_connect_timeout=socket_timeout,
                socket_timeout=socket_timeout,
            ),
            key_prefix=settings.aigc_redis_key_prefix,
        )

    def key_for_task(self, task_id: str) -> str:
        return f"{self.key_prefix}:aigc:image_task:{task_id}"

    def get(self, task_id: str) -> AigcMaterialTaskResult | None:
        try:
            raw_value = self.redis_client.get(self.key_for_task(task_id))
        except Exception as exc:
            raise AigcImageProviderError("aigc image result read failed") from exc
        if raw_value is None:
            return None
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        try:
            payload = json.loads(str(raw_value))
        except (TypeError, ValueError) as exc:
            raise AigcImageProviderError("aigc image result payload invalid") from exc
        return _material_result_from_payload(payload)

    def wait(
        self,
        task_id: str,
        *,
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> AigcMaterialTaskResult:
        deadline = time.monotonic() + timeout_seconds
        while True:
            result = self.get(task_id)
            if result is not None and result.status != "pending":
                return result

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AigcImageProviderError("aigc image result timed out")
            time.sleep(min(poll_interval_seconds, remaining))


class AigcImageGenerationProvider:
    def __init__(
        self,
        settings: LingNengSettings,
        *,
        client: AigcImageClient | None = None,
        result_store: AigcResultStore | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or AigcImageClient(
            base_url=settings.aigc_image_base_url,
            env=aigc_environment_for_app_env(settings.app_env),
            timeout_seconds=settings.aigc_image_timeout_seconds,
        )
        self.result_store = result_store or RedisAigcResultStore.from_settings(settings)

    @classmethod
    def from_settings(
        cls,
        settings: LingNengSettings,
    ) -> "AigcImageGenerationProvider":
        return cls(
            settings,
            client=AigcImageClient(
                base_url=settings.aigc_image_base_url,
                env=aigc_environment_for_app_env(settings.app_env),
                timeout_seconds=settings.aigc_image_timeout_seconds,
            ),
            result_store=RedisAigcResultStore.from_settings(settings),
        )

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        count = _normalize_count(request.count, self.settings)
        size = normalize_image_size(request.size)
        quality = normalize_image_quality(request.quality)
        prompt = request.prompt.strip()
        artifacts: list[dict[str, Any]] = []
        task_ids: list[str] = []
        succeeded_count = 0
        failed_count = 0

        for task_index in range(1, count + 1):
            try:
                task_id = self.client.submit_text_to_image(
                    prompt=prompt,
                    size=size,
                    quality=quality,
                )
                task_ids.append(task_id)
                task_result = self.result_store.wait(
                    task_id,
                    timeout_seconds=self.settings.aigc_result_wait_timeout_seconds,
                    poll_interval_seconds=self.settings.aigc_result_poll_interval_seconds,
                )
            except AigcImageProviderError:
                failed_count += 1
                continue

            task_artifacts = _artifacts_from_task_result(
                task_result,
                next_artifact_index=len(artifacts) + 1,
            )
            if task_artifacts:
                artifacts.extend(task_artifacts)
                succeeded_count += 1
            else:
                failed_count += 1

        if not artifacts:
            raise AigcImageProviderError("aigc image generation produced no artifacts")

        safe_output = {
            "requested_count": count,
            "succeeded_count": succeeded_count,
            "failed_count": failed_count,
            "task_ids": task_ids,
            "size": size,
            "quality": quality,
            "artifact_count": len(artifacts),
        }
        return ImageGenerationResult(
            summary=_image_summary(succeeded_count=succeeded_count, failed_count=failed_count),
            artifacts=artifacts,
            safe_output=safe_output,
            metadata={
                "provider": "aigc",
                "task_ids": task_ids,
                "artifact_count": len(artifacts),
            },
        )


def normalize_image_size(value: str) -> str:
    stripped = str(value or "").strip()
    return stripped or _DEFAULT_SIZE


def normalize_image_quality(value: str) -> str:
    stripped = str(value or "").strip()
    return stripped or _DEFAULT_QUALITY


def create_external_image_artifact(
    *,
    task_id: str,
    index: int,
    url: str,
) -> dict[str, Any]:
    image_format = image_format_from_url(url)
    return {
        "artifact_id": f"artifact_aigc_image_{_safe_id_segment(task_id)}_{index}",
        "artifact_type": "image",
        "source": "image_generation",
        "file_name": f"generated-image-{index}.{image_format}",
        "mime_type": mime_type_for_image_format(image_format),
        "url": url,
        "object_key": f"external/aigc-image/{_safe_id_segment(task_id)}/{index}",
        "format": image_format,
        "target_format": image_format,
        "conversion_required": False,
        "conversion_owner": None,
    }


def image_format_from_url(url: str) -> str:
    try:
        path = urlsplit(url.strip()).path
    except ValueError:
        return "png"
    suffix = path.rsplit(".", maxsplit=1)[-1].lower() if "." in path else ""
    return suffix if suffix in _IMAGE_FORMATS else "png"


def mime_type_for_image_format(image_format: str) -> str:
    if image_format in {"jpg", "jpeg"}:
        return "image/jpeg"
    if image_format == "webp":
        return "image/webp"
    return "image/png"


def _text_to_image_endpoint_url(base_url: str) -> str:
    stripped = base_url.strip().rstrip("/")
    if not stripped:
        raise AigcImageProviderError("aigc image endpoint is not configured")
    if stripped.endswith(_TEXT_TO_IMAGE_PATH):
        return stripped
    return f"{stripped}{_TEXT_TO_IMAGE_PATH}"


def _material_result_from_payload(payload: Any) -> AigcMaterialTaskResult:
    if not isinstance(payload, dict):
        raise AigcImageProviderError("aigc image result payload invalid")
    candidate = payload
    data = payload.get("data")
    if isinstance(data, dict) and "status" not in payload:
        candidate = data
    candidate = dict(candidate)
    candidate.setdefault("raw", payload)
    try:
        return AigcMaterialTaskResult.model_validate(candidate)
    except Exception as exc:
        raise AigcImageProviderError("aigc image result payload invalid") from exc


def _artifacts_from_task_result(
    result: AigcMaterialTaskResult,
    *,
    next_artifact_index: int,
) -> list[dict[str, Any]]:
    if result.status != "success" or result.task_type != "IMAGE":
        return []
    artifacts: list[dict[str, Any]] = []
    for offset, url in enumerate(result.material_urls):
        if not _is_http_url(url):
            continue
        artifacts.append(
            create_external_image_artifact(
                task_id=result.task_id,
                index=next_artifact_index + offset,
                url=url,
            )
        )
    return artifacts


def _normalize_count(value: int, settings: LingNengSettings) -> int:
    return min(max(1, int(value or 1)), max(1, settings.image_max_count))


def _redis_socket_timeout(settings: LingNengSettings) -> float:
    return min(
        max(settings.aigc_result_poll_interval_seconds, 0.1),
        settings.aigc_result_wait_timeout_seconds,
        5.0,
    )


def _safe_id_segment(value: str) -> str:
    segment = _SAFE_ID_RE.sub("-", str(value or "").strip()).strip(".-")
    return segment or "task"


def _is_http_url(value: str) -> bool:
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return False
    return parts.scheme.lower() in {"http", "https"} and bool(parts.netloc)


def _image_summary(*, succeeded_count: int, failed_count: int) -> str:
    if failed_count:
        return f"图片生成部分完成，成功 {succeeded_count} 张，失败 {failed_count} 张"
    return f"图片生成完成，成功 {succeeded_count} 张"
