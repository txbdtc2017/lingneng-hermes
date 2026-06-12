from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BOUNDARY_DOC = (
    ROOT
    / "docs"
    / "lingneng-migration"
    / "specs"
    / "2026-06-12-phase-15-training-boundary-decision.md"
)


def test_phase_15_boundary_decision_doc_records_old_service_ownership():
    text = BOUNDARY_DOC.read_text(encoding="utf-8")

    assert "boundary_only" in text
    assert "Old LingNengAI remains the owner" in text
    assert "LINGNENG_TRAINING_MODE=old_service" in text
    assert "LINGNENG_TRAINING_MODE=disabled" in text
    assert "LINGNENG_TRAINING_MODE=hermes" in text
    assert "intentionally unsupported" in text


def test_phase_15_does_not_add_hermes_training_pipeline_package():
    assert not (ROOT / "lingneng" / "training").exists()


def test_phase_15_runtime_does_not_import_old_lingnengai_app_modules():
    runtime_files = list((ROOT / "lingneng").rglob("*.py"))
    assert runtime_files

    offenders: list[str] = []
    forbidden_fragments = (
        "from " + "app.",
        "import " + "app.",
        "/Users/rotas/Documents/work/hailun/LingNengAI" + "/app",
    )
    for path in runtime_files:
        text = path.read_text(encoding="utf-8")
        if any(fragment in text for fragment in forbidden_fragments):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
