from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from lingneng.config.settings import LingNengSettings
from lingneng.tools.document_generation import (
    _bounded_text,
    _coerce_result,
    _json_result,
    _public_result,
    _text_arg,
    _valid_artifact_dicts,
)


_CURRENT_SETTINGS: ContextVar[LingNengSettings | None] = ContextVar(
    "lingneng_image_generation_settings",
    default=None,
)
_CURRENT_PROVIDER: ContextVar[ImageGenerationProvider | None] = ContextVar(
    "lingneng_image_generation_provider",
    default=None,
)


class ImageGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    count: int = 1
    size: str = ""
    quality: str = ""
    style: str = ""


class ImageGenerationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    safe_output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    message: str | None = None


class ImageGenerationProvider(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...


@contextmanager
def image_generation_context(
    settings: LingNengSettings,
    *,
    provider: ImageGenerationProvider | None = None,
) -> Iterator[None]:
    settings_token = _CURRENT_SETTINGS.set(settings)
    provider_token = _CURRENT_PROVIDER.set(provider)
    try:
        yield
    finally:
        _CURRENT_PROVIDER.reset(provider_token)
        _CURRENT_SETTINGS.reset(settings_token)


def image_generation_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    settings = _settings()
    provider = _CURRENT_PROVIDER.get()
    if provider is None:
        return _json_result(
            _public_result(
                tool_name="image_generation",
                success=False,
                status="skipped",
                summary="Image generation provider is not configured.",
                code="NOT_CONFIGURED",
            ),
            settings=settings,
        )

    raw_args = args or {}
    from lingneng.tools.limits import guarded_tool_skip_result

    guard_result = guarded_tool_skip_result(
        "image_generation",
        raw_args,
        settings,
    )
    if guard_result is not None:
        return guard_result

    request = ImageGenerationRequest(
        prompt=_bounded_text(_text_arg(raw_args.get("prompt")), max_chars=4000),
        count=_normalize_count(raw_args.get("count"), settings),
        size=_bounded_text(_text_arg(raw_args.get("size")), max_chars=40),
        quality=_bounded_text(_text_arg(raw_args.get("quality")), max_chars=40),
        style=_bounded_text(_text_arg(raw_args.get("style")), max_chars=100),
    )
    try:
        result = _coerce_result(provider.generate(request), ImageGenerationResult)
    except Exception:
        return _json_result(
            _public_result(
                tool_name="image_generation",
                success=False,
                status="failed",
                summary="Image generation provider failed.",
                code="IMAGE_GENERATION_PROVIDER_ERROR",
            ),
            settings=settings,
        )

    artifacts = _valid_artifact_dicts(result.artifacts, settings=settings)
    if not artifacts:
        return _json_result(
            _public_result(
                tool_name="image_generation",
                success=False,
                status="failed",
                summary="Image generation returned no valid artifacts.",
                code="IMAGE_GENERATION_NO_VALID_ARTIFACTS",
            ),
            settings=settings,
        )

    return _json_result(
        _public_result(
            tool_name="image_generation",
            success=True,
            status="succeeded",
            summary=result.summary or "Image generation completed.",
            safe_output={
                **result.safe_output,
                "requested_count": request.count,
                "size": request.size,
                "quality": request.quality,
                "style": request.style,
                "artifact_count": len(artifacts),
            },
            artifacts=artifacts,
            metadata={**result.metadata, "artifact_count": len(artifacts)},
        ),
        settings=settings,
    )


def _settings() -> LingNengSettings:
    return _CURRENT_SETTINGS.get() or LingNengSettings.from_env()


def _normalize_count(value: Any, settings: LingNengSettings) -> int:
    try:
        count = int(value) if value is not None else 1
    except (TypeError, ValueError):
        count = 1
    return min(max(1, count), max(1, settings.image_max_count))
