from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from lingneng.config.settings import LingNengSettings
from lingneng.tools.chart_visualization import (
    ChartVisualizationRequest,
    ChartVisualizationResult,
)
from lingneng.tools.document_generation import _bounded_text
from lingneng.tools.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from lingneng.tools.image_provider import image_format_from_url


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_DANGEROUS_QUOTE_RE = re.compile(r"[\"'`“”‘’]")
_IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp"}


class ChartImageGenerationProvider:
    def __init__(
        self,
        *,
        settings: LingNengSettings,
        image_provider: ImageGenerationProvider,
    ) -> None:
        self.settings = settings
        self.image_provider = image_provider

    def generate(self, request: ChartVisualizationRequest) -> ChartVisualizationResult:
        image_result = ImageGenerationResult.model_validate(
            self.image_provider.generate(
                ImageGenerationRequest(
                    prompt=_chart_prompt(request),
                    count=1,
                    size="1024x1024",
                    quality="standard",
                    style="business chart",
                )
            )
        )
        artifacts = [
            {
                **artifact,
                "artifact_type": "image",
                "source": "chart_visualization",
                "file_name": _chart_file_name(request.title, index, artifact),
            }
            for index, artifact in enumerate(image_result.artifacts, start=1)
        ]
        safe_output = {
            **image_result.safe_output,
            "title": request.title,
            "chart_type": request.chart_type,
            "artifact_count": len(artifacts),
        }
        return ChartVisualizationResult(
            summary=_chart_summary(len(artifacts), image_result.safe_output),
            artifacts=artifacts,
            safe_output=safe_output,
            metadata={**image_result.metadata, "artifact_count": len(artifacts)},
        )


def _chart_prompt(request: ChartVisualizationRequest) -> str:
    title = _bounded_text(request.title, max_chars=120)
    chart_type = _bounded_text(request.chart_type, max_chars=80)
    instruction = _bounded_text(request.instruction, max_chars=1000)
    data_summary = _bounded_text(request.data_summary, max_chars=1800)
    lines = [
        "生成一张清晰、专业、适合业务汇报的图表图片。",
        "使用简洁中文标注，避免多余装饰。",
    ]
    if title:
        lines.append(f"标题：{title}")
    if chart_type:
        lines.append(f"图表类型：{chart_type}")
    if instruction:
        lines.append(f"要求：{instruction}")
    if data_summary:
        lines.append(f"数据摘要：{data_summary}")
    return "\n".join(lines)


def _chart_file_name(title: str, index: int, artifact: dict[str, Any]) -> str:
    image_format = _artifact_format(artifact)
    return f"{_safe_chart_title(title)}-{index}.{image_format}"


def _chart_summary(artifact_count: int, safe_output: dict[str, Any]) -> str:
    succeeded_count = safe_output.get("succeeded_count")
    failed_count = safe_output.get("failed_count")
    if isinstance(succeeded_count, int) and isinstance(failed_count, int) and failed_count:
        return f"图表生成部分完成，成功 {succeeded_count} 张，失败 {failed_count} 张"
    if artifact_count:
        return "图表生成完成"
    return "图表生成未返回有效图片"


def _artifact_format(artifact: dict[str, Any]) -> str:
    value = artifact.get("format")
    if isinstance(value, str) and value.lower() in _IMAGE_FORMATS:
        return value.lower()
    file_name = artifact.get("file_name")
    if isinstance(file_name, str):
        suffix = file_name.rsplit(".", maxsplit=1)[-1].lower() if "." in file_name else ""
        if suffix in _IMAGE_FORMATS:
            return suffix
    url = artifact.get("url")
    if isinstance(url, str):
        return image_format_from_url(url)
    return "png"


def _safe_chart_title(value: str) -> str:
    title = PurePosixPath(str(value or "").replace("\\", "/")).name
    title = _CONTROL_CHAR_RE.sub("", title)
    title = _DANGEROUS_QUOTE_RE.sub("", title)
    return title.strip(" .") or "图表"
