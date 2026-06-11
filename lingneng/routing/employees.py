from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import EmployeeType
from lingneng.skills.catalog import LingNengSkillCatalog
from lingneng.skills.models import SkillCatalogItem


EMPLOYEE_PUBLIC_DISPLAY_NAMES = {
    "boss_assistant": "老板助手",
    "operation_specialist": "运营专员",
    "product_combo_advisor": "商品组合顾问",
    "marketing_planner": "营销策划",
    "marketing_content_creator": "营销内容创作",
    "member_operator": "会员运营",
}


class EmployeeDirectoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_type: EmployeeType
    display_name: str
    skill_id: str
    description: str = ""
    positioning: str | None = None
    aliases: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    recommended_task_skills: list[str] = Field(default_factory=list)
    recommended_capabilities: list[str] = Field(default_factory=list)


class LingNengEmployeeDirectory:
    def __init__(self, settings: LingNengSettings) -> None:
        self._items_by_type = self._load_items(settings)

    def items(self) -> list[EmployeeDirectoryItem]:
        return [
            self._items_by_type[employee_type]
            for employee_type in EmployeeType
            if employee_type in self._items_by_type
        ]

    def get(self, employee_type: EmployeeType | str) -> EmployeeDirectoryItem | None:
        parsed = _employee_type_or_none(employee_type)
        if parsed is None:
            return None
        return self._items_by_type.get(parsed)

    def label_for(self, employee_type: EmployeeType | str) -> str:
        parsed = _employee_type_or_none(employee_type)
        if parsed is None:
            return str(employee_type)
        if parsed.value in EMPLOYEE_PUBLIC_DISPLAY_NAMES:
            return EMPLOYEE_PUBLIC_DISPLAY_NAMES[parsed.value]
        item = self._items_by_type.get(parsed)
        return item.display_name if item is not None else parsed.value

    def _load_items(
        self,
        settings: LingNengSettings,
    ) -> dict[EmployeeType, EmployeeDirectoryItem]:
        try:
            catalog_items = LingNengSkillCatalog(settings).list_skills(
                kind="employee_base",
                limit=50,
            )
            items = _items_from_catalog(catalog_items)
        except Exception:
            return _static_items()

        for employee_type, item in _static_items().items():
            items.setdefault(employee_type, item)
        return items


def _items_from_catalog(
    catalog_items: list[SkillCatalogItem],
) -> dict[EmployeeType, EmployeeDirectoryItem]:
    items: dict[EmployeeType, EmployeeDirectoryItem] = {}
    for catalog_item in catalog_items:
        employee_type = _employee_type_or_none(catalog_item.employee_type)
        if employee_type is None or employee_type in items:
            continue
        public_display_name = EMPLOYEE_PUBLIC_DISPLAY_NAMES.get(employee_type.value)
        display_name = public_display_name or catalog_item.display_name or employee_type.value
        aliases = _aliases(catalog_item.display_name, display_name)
        items[employee_type] = EmployeeDirectoryItem(
            employee_type=employee_type,
            display_name=display_name,
            skill_id=catalog_item.package_name,
            description=catalog_item.description,
            aliases=aliases,
            domains=catalog_item.domains,
            tags=catalog_item.tags,
            recommended_task_skills=catalog_item.recommended_task_skills,
            recommended_capabilities=catalog_item.recommended_capabilities,
        )
    return items


def _static_items() -> dict[EmployeeType, EmployeeDirectoryItem]:
    return {
        employee_type: EmployeeDirectoryItem(
            employee_type=employee_type,
            display_name=EMPLOYEE_PUBLIC_DISPLAY_NAMES[employee_type.value],
            skill_id=f"employee-{employee_type.value.replace('_', '-')}",
        )
        for employee_type in EmployeeType
    }


def _employee_type_or_none(value: EmployeeType | str | None) -> EmployeeType | None:
    if value is None:
        return None
    if isinstance(value, EmployeeType):
        return value
    try:
        return EmployeeType(str(value))
    except ValueError:
        return None


def _aliases(
    catalog_display_name: str | None,
    public_display_name: str,
) -> list[str]:
    if not catalog_display_name or catalog_display_name == public_display_name:
        return []
    return [catalog_display_name]

