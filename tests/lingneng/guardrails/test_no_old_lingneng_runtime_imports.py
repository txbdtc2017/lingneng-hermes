from __future__ import annotations

import ast
from pathlib import Path

from tests.lingneng.tools.test_toolset_policy import DISALLOWED_HERMES_TOOLS
from toolsets import resolve_toolset


ROOT = Path(__file__).resolve().parents[3]
OLD_LINGNENG_APP_PATH = "/Users/rotas/Documents/work/hailun/LingNengAI" + "/app"


def _old_runtime_import_offenders(text: str, relative: str) -> list[str]:
    offenders: list[str] = []
    if OLD_LINGNENG_APP_PATH in text:
        offenders.append(f"{relative}:old_app_path")
    tree = ast.parse(text, filename=relative)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app" or alias.name.startswith("app."):
                    offenders.append(f"{relative}:{node.lineno}")
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            if module == "app" or module.startswith("app."):
                offenders.append(f"{relative}:{node.lineno}")
    return offenders


def test_phase_16_runtime_does_not_import_old_lingnengai_app_modules() -> None:
    offenders: list[str] = []
    for path in sorted((ROOT / "lingneng").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(ROOT))
        offenders.extend(_old_runtime_import_offenders(text, relative))
    assert offenders == []


def test_old_runtime_import_scan_allows_relative_app_imports_only() -> None:
    assert (
        _old_runtime_import_offenders(
            "\n".join(
                (
                    "from .app import create_app",
                    "from ..app import create_app as create_parent_app",
                )
            ),
            "lingneng/api/routes.py",
        )
        == []
    )

    assert _old_runtime_import_offenders(
        "\n".join(
            (
                "from .app import create_app",
                "from app.foo import bar",
            )
        ),
        "lingneng/api/routes.py",
    ) == ["lingneng/api/routes.py:2"]


def test_phase_16_does_not_add_native_training_pipeline() -> None:
    assert not (ROOT / "lingneng" / "training").exists()


def test_phase_16_lingneng_toolset_keeps_high_risk_tools_excluded() -> None:
    names = set(resolve_toolset("lingneng"))
    assert names.isdisjoint(DISALLOWED_HERMES_TOOLS)
