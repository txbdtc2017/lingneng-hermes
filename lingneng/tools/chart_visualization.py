from __future__ import annotations

import json
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
    _sanitize_public_value,
    _text_arg,
    _valid_artifact_dicts,
)


_CURRENT_SETTINGS: ContextVar[LingNengSettings | None] = ContextVar(
    "lingneng_chart_visualization_settings",
    default=None,
)
_CURRENT_PROVIDER: ContextVar[ChartVisualizationProvider | None] = ContextVar(
    "lingneng_chart_visualization_provider",
    default=None,
)


class ChartVisualizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str
    title: str = ""
    chart_type: str = ""
    data: Any = None
    data_summary: str = ""


class ChartVisualizationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    safe_output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    message: str | None = None


class ChartVisualizationProvider(Protocol):
    def generate(
        self,
        request: ChartVisualizationRequest,
    ) -> ChartVisualizationResult: ...


@contextmanager
def chart_visualization_context(
    settings: LingNengSettings,
    *,
    provider: ChartVisualizationProvider | None = None,
) -> Iterator[None]:
    settings_token = _CURRENT_SETTINGS.set(settings)
    provider_token = _CURRENT_PROVIDER.set(provider)
    try:
        yield
    finally:
        _CURRENT_PROVIDER.reset(provider_token)
        _CURRENT_SETTINGS.reset(settings_token)


def chart_visualization_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    settings = _settings()
    provider = _CURRENT_PROVIDER.get()
    if provider is None:
        return _json_result(
            _public_result(
                tool_name="chart_visualization",
                success=False,
                status="skipped",
                summary="Chart visualization provider is not configured.",
                code="NOT_CONFIGURED",
            ),
            settings=settings,
        )

    request = _build_chart_request(args or {})
    try:
        result = _coerce_result(provider.generate(request), ChartVisualizationResult)
    except Exception:
        return _json_result(
            _public_result(
                tool_name="chart_visualization",
                success=False,
                status="failed",
                summary="Chart visualization provider failed.",
                code="CHART_VISUALIZATION_PROVIDER_ERROR",
            ),
            settings=settings,
        )

    artifacts = _valid_artifact_dicts(
        result.artifacts,
        overrides={"artifact_type": "image", "source": "chart_visualization"},
        settings=settings,
    )
    if not artifacts:
        return _json_result(
            _public_result(
                tool_name="chart_visualization",
                success=False,
                status="failed",
                summary="Chart visualization returned no valid artifacts.",
                code="CHART_VISUALIZATION_NO_VALID_ARTIFACTS",
            ),
            settings=settings,
        )

    return _json_result(
        _public_result(
            tool_name="chart_visualization",
            success=True,
            status="succeeded",
            summary=result.summary or "Chart visualization completed.",
            safe_output={
                **result.safe_output,
                "title": request.title,
                "chart_type": request.chart_type,
                "data_summary": request.data_summary,
                "artifact_count": len(artifacts),
            },
            artifacts=artifacts,
            metadata={**result.metadata, "artifact_count": len(artifacts)},
        ),
        settings=settings,
    )


def _settings() -> LingNengSettings:
    return _CURRENT_SETTINGS.get() or LingNengSettings.from_env()


def _build_chart_request(raw_args: dict[str, Any]) -> ChartVisualizationRequest:
    raw_data = raw_args.get("data")
    public_data = _sanitize_public_value(raw_data)
    return ChartVisualizationRequest(
        instruction=_bounded_text(
            _text_arg(raw_args.get("instruction")),
            max_chars=4000,
        ),
        title=_bounded_text(_text_arg(raw_args.get("title")), max_chars=200),
        chart_type=_bounded_text(
            _text_arg(raw_args.get("chart_type")),
            max_chars=80,
        ),
        data=public_data,
        data_summary=_chart_data_summary(raw_args.get("data_summary"), public_data),
    )


def _chart_data_summary(data_summary: Any, public_data: Any) -> str:
    if isinstance(data_summary, str) and data_summary.strip():
        return _bounded_text(data_summary, max_chars=2000)
    try:
        dumped = json.dumps(public_data, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return ""
    return _bounded_text(dumped, max_chars=2000)
