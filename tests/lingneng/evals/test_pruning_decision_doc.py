from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DECISION_DOC_PATH = (
    REPO_ROOT
    / "docs"
    / "lingneng-migration"
    / "specs"
    / "2026-06-06-hermes-feature-pruning-decision.md"
)

REQUIRED_HEADINGS = (
    "Status",
    "Kept For LingNeng",
    "Disabled By Default For LingNeng API",
    "Future Removal Candidates",
    "Required Evidence Gates",
)
REQUIRED_REFERENCES = (
    "scripts/lingneng-chat-smoke.py",
    (
        "docs/lingneng-migration/reports/"
        "2026-06-06-output-comparison-fixture.json"
    ),
    (
        "docs/lingneng-migration/reports/"
        "2026-06-06-output-comparison-template.md"
    ),
)
REQUIRED_EVIDENCE_GATES = (
    "Java smoke script pass",
    "LingNeng contract tests pass",
    "Docker/server deployment validation from Phase 7",
    "output comparison report",
    "production or test soak",
)
KEPT_FEATURE_TERMS = (
    "AIAgent",
    "SessionDB",
    "compression",
    "LingNeng API facade",
    "LingNeng toolset",
    "skills loader",
    "SSE bridge",
    "observability",
    "trace summary",
    "RAG",
    "artifact",
    "attachment",
)
DISABLED_BY_DEFAULT_TERMS = (
    "terminal",
    "code execution",
    "arbitrary filesystem access",
    "browser automation",
    "cross-channel messaging",
    "unrelated platform adapters",
    "non-LingNeng toolsets",
)
FUTURE_REMOVAL_TERMS = (
    "unused platform/channel adapters",
    "server runtime image",
    "unused UI surfaces",
    "production deploy packaging",
    "optional plugins",
    "LingNeng server",
)
SECRET_LIKE_PATTERNS = (
    "api_key=",
    "Bearer ",
    "password=",
    "X-Amz-Signature",
    "/Users/",
    "AKIA",
    "BEGIN PRIVATE KEY",
    "sk-",
)
IMMEDIATE_REMOVAL_PHRASES = (
    "authorized for immediate removal",
    "authorized for immediate deletion",
    "authorized for immediate disablement",
    "remove now",
    "delete now",
    "disable now",
    "phase 8 will remove",
    "phase 8 will delete",
    "phase 8 will disable",
)
COMPLETED_DEPLOYMENT_CLAIMS = (
    "phase 7 deployment is complete",
    "phase 7 deployment completed",
    "deployment validation is complete",
    "deployment validation completed",
    "docker/server deployment validation is complete",
    "docker deployment validation is complete",
    "docker compose validation completed",
    "compose validation is complete",
    "github actions validation completed",
    "github actions workflow is complete",
    "deployment evidence is complete",
)


def load_doc() -> str:
    return DECISION_DOC_PATH.read_text(encoding="utf-8")


def heading_pattern(heading: str) -> re.Pattern[str]:
    return re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)


def extract_section(document: str, heading: str) -> str:
    match = heading_pattern(heading).search(document)
    assert match is not None, heading

    next_heading = re.search(r"^##\s+", document[match.end() :], re.MULTILINE)
    if next_heading is None:
        return document[match.end() :]
    return document[match.end() : match.end() + next_heading.start()]


def assert_all_terms_present(section: str, terms: tuple[str, ...]) -> None:
    section_lower = section.lower()
    missing_terms = [term for term in terms if term.lower() not in section_lower]
    assert missing_terms == []


def test_decision_document_exists_and_has_required_sections() -> None:
    document = load_doc()

    for heading in REQUIRED_HEADINGS:
        assert heading_pattern(heading).search(document), heading


def test_status_is_documentation_only_decision_gate() -> None:
    document_lower = load_doc().lower()

    assert "decision gate only" in document_lower
    assert "documentation-only" in document_lower


def test_feature_classification_sections_cover_required_terms() -> None:
    document = load_doc()

    assert_all_terms_present(
        extract_section(document, "Kept For LingNeng"),
        KEPT_FEATURE_TERMS,
    )
    assert_all_terms_present(
        extract_section(document, "Disabled By Default For LingNeng API"),
        DISABLED_BY_DEFAULT_TERMS,
    )
    assert_all_terms_present(
        extract_section(document, "Future Removal Candidates"),
        FUTURE_REMOVAL_TERMS,
    )


def test_required_evidence_gates_and_references_are_present() -> None:
    document = load_doc()

    for gate in REQUIRED_EVIDENCE_GATES:
        assert gate in document
    for reference in REQUIRED_REFERENCES:
        assert reference in document


def test_phase_8_does_not_authorize_removal_and_requires_later_plan() -> None:
    document_lower = load_doc().lower()

    assert "no removal is authorized in phase 8" in document_lower
    assert "later approved spec and plan" in document_lower
    assert "broad removal" in document_lower


def test_phase_7_deployment_evidence_remains_deferred_and_pending() -> None:
    document_lower = load_doc().lower()

    assert "phase 7 deployment evidence" in document_lower
    assert "pending" in document_lower
    assert "deployment deferred" in document_lower

    for phrase in COMPLETED_DEPLOYMENT_CLAIMS:
        assert phrase not in document_lower


def test_document_contains_no_secret_like_values() -> None:
    document = load_doc()

    for pattern in SECRET_LIKE_PATTERNS:
        assert pattern not in document, pattern


def test_document_does_not_authorize_immediate_removal_or_disablement() -> None:
    document_lower = load_doc().lower()

    assert "no removal is authorized in phase 8" in document_lower
    for phrase in IMMEDIATE_REMOVAL_PHRASES:
        assert phrase not in document_lower
