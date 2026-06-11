from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from lingneng.config.settings import LingNengSettings
from lingneng.tools.chart_visualization import ChartVisualizationProvider
from lingneng.tools.document_generation import DocumentGenerationProvider
from lingneng.tools.image_generation import ImageGenerationProvider
from lingneng.tools.web_search import WebSearchProvider


@dataclass(frozen=True)
class LingNengToolProviders:
    web_search: WebSearchProvider | None = None
    document_generation: DocumentGenerationProvider | None = None
    image_generation: ImageGenerationProvider | None = None
    chart_visualization: ChartVisualizationProvider | None = None


def build_lingneng_tool_providers(
    settings: LingNengSettings,
) -> LingNengToolProviders:
    image_provider = build_image_generation_provider(settings)
    return LingNengToolProviders(
        web_search=build_web_search_provider(settings),
        document_generation=build_document_generation_provider(settings),
        image_generation=image_provider,
        chart_visualization=build_chart_visualization_provider(
            settings,
            image_provider=image_provider,
        ),
    )


def build_web_search_provider(settings: LingNengSettings) -> WebSearchProvider | None:
    if settings.web_search_provider.strip().lower() != "bocha":
        return None
    if not settings.bocha_web_search_api_key.strip():
        return None
    provider_class = _optional_provider_class(
        "lingneng.tools.web_search_provider",
        "BochaWebSearchProvider",
    )
    if provider_class is None:
        return None
    return provider_class(settings)


def build_document_generation_provider(
    settings: LingNengSettings,
) -> DocumentGenerationProvider | None:
    if settings.document_provider.strip().lower() != "java_file":
        return None
    if not settings.document_provider_configured:
        return None
    provider_class = _optional_provider_class(
        "lingneng.tools.document_provider",
        "JavaFileDocumentProvider",
    )
    if provider_class is None:
        return None
    return provider_class.from_settings(settings)


def build_image_generation_provider(
    settings: LingNengSettings,
) -> ImageGenerationProvider | None:
    if not settings.image_provider_configured:
        return None
    provider_class = _optional_provider_class(
        "lingneng.tools.image_provider",
        "AigcImageGenerationProvider",
    )
    if provider_class is None:
        return None
    return provider_class.from_settings(settings)


def build_chart_visualization_provider(
    settings: LingNengSettings,
    *,
    image_provider: ImageGenerationProvider | None = None,
) -> ChartVisualizationProvider | None:
    if image_provider is None:
        return None
    provider_class = _optional_provider_class(
        "lingneng.tools.chart_provider",
        "ChartImageGenerationProvider",
    )
    if provider_class is None:
        return None
    return provider_class(
        settings=settings,
        image_provider=image_provider,
    )


def _optional_provider_class(module_name: str, class_name: str) -> Any | None:
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return None
        raise
    return getattr(module, class_name)
