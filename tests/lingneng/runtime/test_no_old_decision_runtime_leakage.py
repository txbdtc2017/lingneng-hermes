from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LINGNENG_ROOT = REPO_ROOT / "lingneng"

PROHIBITED_IDENTIFIERS = {
    "RuntimeDecisionService",
    "EntryDecisionService",
    "SemanticDecisionService",
    "RequestPlanner",
    "ToolAdmissionService",
    "build_fast_path_decision",
    "smalltalk_final_reply",
    "light_llm_answer",
    "tool_only_agent",
    "direct_attachment_answer",
}
PROHIBITED_RUNTIME_FILENAMES = {
    "runtime_decision.py",
    "entry_decision.py",
    "semantic_decision.py",
    "request_plan.py",
    "tool_admission.py",
    "light_llm_answer.py",
    "tool_only_agent.py",
    "direct_attachment_answer.py",
}


def _python_files() -> list[Path]:
    return sorted(
        path
        for path in LINGNENG_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def test_lingneng_runtime_does_not_import_old_lingnengai_app_modules() -> None:
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app" or alias.name.startswith("app."):
                        offenders.append(f"{path.relative_to(REPO_ROOT)} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0 and (module == "app" or module.startswith("app.")):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} imports from {module}")

    assert offenders == []


def test_lingneng_runtime_does_not_reintroduce_old_decision_component_names() -> None:
    offenders: list[str] = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        for identifier in PROHIBITED_IDENTIFIERS:
            if identifier in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)} contains {identifier}")

    assert offenders == []


def test_lingneng_runtime_does_not_add_old_decision_runtime_files() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in _python_files()
        if path.name in PROHIBITED_RUNTIME_FILENAMES
    ]

    assert offenders == []
