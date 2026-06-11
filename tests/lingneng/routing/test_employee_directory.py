import importlib
import sys

from lingneng.config.settings import LingNengSettings
from lingneng.routing.employees import (
    EMPLOYEE_PUBLIC_DISPLAY_NAMES,
    LingNengSkillCatalog,
    LingNengEmployeeDirectory,
)
from lingneng.schemas.chat_request import EmployeeType


def settings(tmp_path):
    return LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})


def test_static_employee_directory_covers_all_employee_types(tmp_path):
    directory = LingNengEmployeeDirectory(settings(tmp_path))
    items = directory.items()

    assert {item.employee_type for item in items} == {member for member in EmployeeType}
    assert [item.employee_type for item in items] == list(EmployeeType)
    assert EMPLOYEE_PUBLIC_DISPLAY_NAMES["marketing_content_creator"] == "营销内容创作"
    assert directory.label_for(EmployeeType.MARKETING_CONTENT_CREATOR) == "营销内容创作"


def test_employee_directory_reads_bundled_skill_metadata(tmp_path):
    directory = LingNengEmployeeDirectory(settings(tmp_path))
    item = directory.get(EmployeeType.MARKETING_CONTENT_CREATOR)

    assert item is not None
    assert item.employee_type is EmployeeType.MARKETING_CONTENT_CREATOR
    assert item.skill_id == "employee-marketing-content-creator"
    assert item.display_name
    assert isinstance(item.recommended_task_skills, list)
    assert isinstance(item.recommended_capabilities, list)


def test_employee_directory_falls_back_when_catalog_fails(tmp_path, monkeypatch):
    def fail_list_skills(*args, **kwargs):
        raise RuntimeError("catalog unavailable")

    monkeypatch.setattr(LingNengSkillCatalog, "list_skills", fail_list_skills)

    directory = LingNengEmployeeDirectory(settings(tmp_path))

    assert [item.employee_type for item in directory.items()] == list(EmployeeType)
    assert directory.get(EmployeeType.MARKETING_PLANNER).skill_id == (
        "employee-marketing-planner"
    )


def test_import_lingneng_routing_is_lightweight():
    sys.modules.pop("run_agent", None)

    importlib.import_module("lingneng.routing")

    assert "run_agent" not in sys.modules
