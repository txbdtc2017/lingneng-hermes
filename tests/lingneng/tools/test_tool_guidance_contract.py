from __future__ import annotations

from pathlib import Path

import yaml

from tests.lingneng.tools.test_toolset_policy import (
    APPROVED_LINGNENG_TOOLS,
    DISALLOWED_HERMES_TOOLS,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "skills" / "lingneng"
INFRA_ROOT = SKILL_ROOT / "infrastructure"


def _skill_body(package: str) -> str:
    text = (INFRA_ROOT / package / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    end = next(index for index, line in enumerate(lines[1:], start=1) if line == "---")
    return "\n".join(lines[end + 1 :])


def _frontmatter(package: str) -> dict:
    text = (INFRA_ROOT / package / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    end = next(index for index, line in enumerate(lines[1:], start=1) if line == "---")
    data = yaml.safe_load("\n".join(lines[1:end]))
    assert isinstance(data, dict)
    return data


def test_rag_and_web_search_guidance_is_explicit() -> None:
    body = _skill_body("rag-citation-contract")
    assert "retrieve_rag" in body
    assert "web_search" in body
    assert "内部训练资料" in body
    assert "实时公共事实" in body
    assert "不得编造引用" in body


def test_artifact_claims_require_real_artifact_result() -> None:
    body = _skill_body("artifact-output-contract")
    assert "artifact_created" in body
    assert "真实 artifact" in body
    assert "不要声称生成成功" in body
    assert "本地绝对路径" in body


def test_tool_observation_contract_denies_hidden_or_unavailable_tools() -> None:
    body = _skill_body("tool-observation-contract")
    assert "工具缺失或未配置" in body
    assert "隐藏或不可见工具不代表已授权" in body
    assert "不得把模型猜测包装成工具观察结果" in body


def test_contract_tools_are_lingneng_approved_only() -> None:
    for package in (
        "employee-answer-semantics-contract",
        "business-answer-contract",
        "tool-observation-contract",
        "artifact-output-contract",
        "rag-citation-contract",
    ):
        lingneng = _frontmatter(package)["metadata"]["lingneng"]
        declared = set(lingneng.get("tools", []))
        assert declared <= APPROVED_LINGNENG_TOOLS
        assert declared.isdisjoint(DISALLOWED_HERMES_TOOLS)
