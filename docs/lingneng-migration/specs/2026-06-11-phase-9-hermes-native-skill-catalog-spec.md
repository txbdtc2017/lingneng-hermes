# Phase 9 Hermes-Native Skill Catalog And Skill Tools Spec

## Status

Drafted on `dev` after the business capability migration scope was written in:

- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`

This phase is the first executable phase of the remaining LingNeng business
migration. It only covers skill packages, skill catalog behavior, skill tools,
and prompt guidance needed for later employee handoff and business tools.

## Required Context Reloaded

Reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`

Current implementation inspected:

- `lingneng/skills/loader.py`
- `lingneng/skills/models.py`
- `lingneng/tools/stubs.py`
- `lingneng/tools/toolset.py`
- `lingneng/runtime/hermes_adapter.py`
- `toolsets.py`
- `tools/skills_tool.py`
- `agent/skill_utils.py`
- `agent/prompt_builder.py`
- `tests/lingneng/skills/test_skill_loader.py`
- `tests/lingneng/tools/test_toolset_policy.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`

LingNengAI reference inspected:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/skills/**/SKILL.md`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/skills/**/references/*.md`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/skills/middleware.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/skills/package_models.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/skills/registry.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/skills/employee_resolver.py`

## Goal

Make LingNeng skills available to the Hermes runtime as a real, bounded,
Hermes-native skill catalog, then replace the Phase 3 skill stubs with real
LingNeng skill tools:

- `list_skills`
- `search_skills`
- `read_skill`
- `read_skill_resource`

The phase must remove the runtime dependency on the old sibling
`/Users/rotas/Documents/work/hailun/LingNengAI/app/skills` path for normal
LingNeng API behavior.

## Why This Phase Comes First

Later phases depend on skills:

- Employee handoff routing needs employee boundaries and target employee
  metadata.
- Tool provider phases need task/capability skill guidance so the model knows
  when to use expensive or side-effectful tools.
- Prompt hardening needs a single source for trusted LingNeng business
  instructions.

Phase 9 intentionally does not implement route tools, provider tools, time
context, attachment parsing, or RAG training.

## Scope

Phase 9 includes:

1. Add repo-bundled LingNeng skill packages under `skills/lingneng/`.
2. Preserve existing LingNeng business metadata under `metadata.lingneng`.
3. Add Hermes-native metadata where useful under `metadata.hermes`.
4. Make `LingNengSkillLoader` load from repo-bundled LingNeng skills by
   default, plus configured `LINGNENG_SKILL_ROOTS`.
5. Add a focused LingNeng skill catalog service that can list, search, read,
   and read resources from validated packages.
6. Replace skill tool stubs with real handlers.
7. Update tool schemas only where needed to support bounded list/search/read
   behavior.
8. Update prompt context so the current employee sees:
   - employee base skill
   - recommended task skills
   - recommended capability skills
   - guidance to call skill tools for deeper instructions
   - guidance that handoff comes in Phase 10
9. Add tests for discovery, search, reading, resource safety, toolset exposure,
   and prompt context.

## Non-Goals

Phase 9 does not:

- Modify Java request or SSE contracts.
- Implement employee routing, handoff tools, route events, or pending
  confirmation storage.
- Implement real RAG retrieval/training.
- Wire web search, document generation, image generation, chart generation, or
  artifact storage providers.
- Implement attachment parsing/OCR/vision.
- Implement `read_workspace` or `write_workspace`.
- Add CI/CD or deployment automation.
- Import old `app.domain.skills` or any old `app.*` module at runtime.
- Add a new skill execution framework outside Hermes and `lingneng/skills`.
- Expose `skill_manage` or arbitrary Hermes skill mutation through the Java
  LingNeng toolset.

## Accepted Decisions

1. **Canonical bundled location:** repo-bundled LingNeng skills live under
   `skills/lingneng/`.
2. **Default discovery:** LingNeng API loads repo-bundled `skills/lingneng`
   by default. `LINGNENG_SKILL_ROOTS` remains an additive override for local
   comparison and deployment-specific skill directories.
3. **Old project path is not production config:** the old
   `/Users/rotas/Documents/work/hailun/LingNengAI/app/skills` path is never
   hardcoded as a default.
4. **Read-only skill tools:** Phase 9 exposes read/list/search tools only.
   It does not expose Hermes `skill_manage`.
5. **Skill metadata is trusted only after validation:** a package must have
   valid front matter, `metadata.lingneng.schema_version == "1.0"`,
   `status == "active"`, and `script_policy == "metadata_only"`.
6. **Skill bodies are bounded:** prompt injection and tool output never include
   unbounded skill body or resource content.
7. **Resource reads are progressive disclosure:** resources are only read when
   `read_skill_resource` is called, and only from allowed directories.
8. **Deterministic search:** Phase 9 search is lexical/metadata-based and does
   not call an LLM.
9. **No fake behavior:** if no valid skills exist, skill tools return safe empty
   results or not-found errors, not fake skill data.
10. **History boundary remains unchanged:** Java `history` still does not enter
    Hermes conversation context as part of this phase.

## User Confirmations Before Phase 9 Plan

No additional confirmation is required before writing the Phase 9 plan.

The following decisions are treated as approved by the total migration spec and
this Phase 9 spec:

- Copy/provision LingNeng skill packages into this Hermes runtime.
- Use `skills/lingneng/` as the repo-bundled default source.
- Keep old LingNengAI skills as reference input only.
- Replace skill stubs before implementing route/handoff.
- Keep workspace tools stubbed.
- Keep RAG training in the old project for now.

If any of these decisions change, update this spec before executing the plan.

## Skill Packages To Bundle

Phase 9 bundles the current LingNengAI skill package set.

Employee base skills:

- `employee-boss-assistant`
- `employee-operation-specialist`
- `employee-product-combo-advisor`
- `employee-marketing-planner`
- `employee-marketing-content-creator`
- `employee-member-operator`

Task skills:

- `knowledge-base-answer`
- `marketing-copy-generation`
- `member-repurchase-campaign`
- `restaurant-campaign-planning`
- `restaurant-channel-growth-strategy`
- `restaurant-combo-pricing-strategy`
- `restaurant-menu-engineering`
- `restaurant-strategy-planning`
- `store-operation-analysis`
- `training-summary-report`

Capability skills:

- `document-generation`
- `image-generation`
- `chart-visualization`
- `report-formatting`

Infrastructure contract skills:

- `artifact-output-contract`
- `business-answer-contract`
- `rag-citation-contract`
- `tool-observation-contract`

Reference files under package `references/` directories are included when
present. Other resource directories may be included only when they are already
part of the old skill package and pass the allowed-directory policy.

## Target Directory Shape

```text
skills/lingneng/
  employees/
    employee-boss-assistant/SKILL.md
    employee-marketing-content-creator/SKILL.md
  tasks/
    marketing-copy-generation/SKILL.md
    marketing-copy-generation/references/content-creation-playbook.md
    restaurant-campaign-planning/SKILL.md
    restaurant-campaign-planning/references/marketing-nodes.md
  capabilities/
    document-generation/SKILL.md
    image-generation/SKILL.md
  infrastructure/
    business-answer-contract/SKILL.md
    rag-citation-contract/SKILL.md
```

The package directory name must equal the `name` in `SKILL.md` front matter.

## Metadata Contract

Each bundled LingNeng `SKILL.md` must include standard Hermes-compatible front
matter:

```yaml
---
name: lower-kebab-case
description: bounded human-readable description
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: employee_base | task | capability | infrastructure
    source: python | imported | generated
    status: active
    user_visible: true | false
    script_policy: metadata_only
    tags: [restaurant]
    domains: [restaurant]
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
---
```

The existing old LingNeng metadata fields should be preserved when present:

- `tags`
- `domains`
- `employee_type`
- `display_name`
- `recommended_task_skills`
- `recommended_capabilities`
- `target_employee_types`
- `supporting_skills`
- `tools`

The loader and tools may ignore fields not needed in Phase 9, but they must not
drop them from bundled skill files.

## Catalog Source Rules

The catalog scans roots in this order:

1. Repo-bundled `skills/lingneng`.
2. Paths from `LINGNENG_SKILL_ROOTS`, in configured order.

If two packages have the same name, the later configured root overrides the
repo-bundled package. This allows local migration comparison without changing
production defaults.

The catalog must:

- scan at most three levels below each root for `SKILL.md`
- skip excluded directories such as `.git`, `.venv`, `__pycache__`,
  `node_modules`, and cache folders
- reject packages whose directory name does not equal the front matter `name`
- reject inactive, draft, deprecated, or disabled packages
- reject package names that are not lower-kebab-case
- reject non-`metadata_only` script policy
- reject unsupported schema versions
- preserve validation warnings without leaking absolute local paths in public
  tool output or prompt context

## Data Models

The existing `lingneng/skills/models.py` models should be extended rather than
replaced.

Required additions:

### `LingNengSkillMetadata`

Add optional fields:

- `tags: list[str]`
- `domains: list[str]`
- `recommended_task_skills: list[str]`
- `recommended_capabilities: list[str]`
- `target_employee_types: list[str]`
- `supporting_skills: list[str]`
- `tools: list[str]`

### `SkillCatalogItem`

Public item returned by list/search:

```text
package_name: str
description: str
kind: "employee_base" | "task" | "capability" | "infrastructure"
version: str
display_name: str | null
employee_type: str | null
target_employee_types: list[str]
tools: list[str]
recommended_task_skills: list[str]
recommended_capabilities: list[str]
tags: list[str]
domains: list[str]
score: float | null
matched_terms: list[str]
```

### `SkillReadResult`

Public result returned by `read_skill`:

```text
success: bool
skill: SkillCatalogItem | null
body: str
body_truncated: bool
resource_manifest: list[SkillResource]
warnings: list[SkillPromptWarning]
code: str | null
message: str | null
```

### `SkillResourceReadResult`

Public result returned by `read_skill_resource`:

```text
success: bool
skill_id: str
resource_id: str
content: str
content_truncated: bool
size_bytes: int
mime_type: str
code: str | null
message: str | null
```

Tool handlers may wrap these data in the common tool envelope if that is more
consistent with the rest of `lingneng/tools`.

## Tool Schemas

Phase 9 updates the four skill tool schemas.

### `list_skills`

Input:

```text
employee_type: str | null
kind: str | null
limit: int | null
```

Behavior:

- default `limit` is 20
- max `limit` is 50
- `employee_type` filters employee base skills by exact employee type and task
  skills by `target_employee_types`
- `kind` filters by exact LingNeng skill kind
- returns deterministic order: employee base, task, capability,
  infrastructure, then package name

### `search_skills`

Input:

```text
query: str
employee_type: str | null
kind: str | null
limit: int | null
```

Behavior:

- query is required and bounded
- default `limit` is 10
- max `limit` is 20
- search uses package name, description, triggers, metadata tags/domains/tools,
  headings, and bounded body excerpt
- results are sorted by descending score, then package name
- no LLM or external provider call is allowed

### `read_skill`

Input:

```text
skill_id: str
max_chars: int | null
```

Behavior:

- `skill_id` must match a valid package name exactly
- default `max_chars` uses `LINGNENG_SKILL_EXCERPT_MAX_CHARS`
- max output is clamped to `LINGNENG_SKILL_READ_MAX_CHARS`
- returns body and resource manifest
- returns `NOT_FOUND` for unknown or invalid packages

### `read_skill_resource`

Input:

```text
skill_id: str
resource_id: str
max_chars: int | null
```

Behavior:

- `resource_id` is a package-relative path
- allowed top-level directories:
  - `references`
  - `templates`
  - `examples`
  - `assets`
- reject absolute paths
- reject path traversal
- reject hidden path components
- reject symlinks escaping the package root
- reject files above configured size
- default `max_chars` is 12000
- max output is clamped to `LINGNENG_SKILL_RESOURCE_MAX_CHARS`

## Configuration Contract

Extend `LingNengSettings` with:

```text
LINGNENG_SKILL_READ_MAX_CHARS
  Type: int
  Default: 12000
  Minimum: 1000

LINGNENG_SKILL_RESOURCE_MAX_CHARS
  Type: int
  Default: 12000
  Minimum: 1000

LINGNENG_SKILL_RESOURCE_MAX_BYTES
  Type: int
  Default: 262144
  Minimum: 1024
```

`LINGNENG_SKILL_ROOTS` remains supported. It is additive to the repo-bundled
default root.

## Prompt Context Contract

For a normal Java request with a known employee type, system prompt context
should include:

- current employee base package name
- current employee display name
- employee role/body excerpt
- recommended task skill names
- recommended capability skill names
- selected skill excerpt when `request.skill.skill_id` exactly matches a valid
  package
- resource manifest only, not resource contents
- warnings only with sanitized package names and public warning codes
- a short instruction that deeper task instructions should be loaded through
  `read_skill` or `read_skill_resource`

Prompt context must not include:

- absolute local filesystem paths
- Java `history`
- `request.skill.inline`
- inactive skills
- full resource contents
- validation tracebacks

## Tool Result Safety

Skill tool results must not contain:

- absolute local paths
- Python tracebacks
- raw validation exceptions
- API keys, tokens, secrets, or authorization values
- Java `history`
- request payloads
- unbounded body/resource content

Tool failures must use stable public codes:

- `NOT_FOUND`
- `INVALID_ARGUMENT`
- `RESOURCE_NOT_ALLOWED`
- `RESOURCE_TOO_LARGE`
- `RESOURCE_UNREADABLE`
- `SKILL_CATALOG_EMPTY`

## Module Boundaries

Expected implementation modules:

- `lingneng/skills/catalog.py`
  - source root resolution
  - validated package index
  - list/search/read/resource operations
  - deterministic lexical scoring
- `lingneng/skills/loader.py`
  - reuse catalog package loading where possible
  - build prompt context from catalog
- `lingneng/skills/models.py`
  - extended metadata and public result models
- `lingneng/tools/skill_tools.py`
  - real handlers for the four skill tools
- `lingneng/tools/stubs.py`
  - remove the four skill tool names from stub-only handling
  - keep `read_workspace` and `write_workspace` as stubs
- `lingneng/tools/toolset.py`
  - register real skill tool handlers
- `lingneng/config/settings.py`
  - add skill read/resource limits

Expected tests:

- `tests/lingneng/skills/test_skill_catalog.py`
- `tests/lingneng/skills/test_skill_loader.py`
- `tests/lingneng/tools/test_skill_tools.py`
- `tests/lingneng/tools/test_toolset_policy.py`
- focused runtime prompt tests in
  `tests/lingneng/runtime/test_hermes_adapter_config.py`

## Test Strategy

Tests must use local temporary skill packages or repo-bundled LingNeng skills.
They must not import or execute code from the old LingNengAI project at runtime.

Required test coverage:

- repo-bundled `skills/lingneng` exists and contains all required package names
- loader finds repo-bundled employee base skill without `LINGNENG_SKILL_ROOTS`
- configured roots override bundled packages with the same name
- inactive/non-`metadata_only`/invalid package is skipped with public warning
- `list_skills` filters by kind and employee type
- `search_skills` returns deterministic matches for trigger/description/body
- `read_skill` returns bounded content and resource manifest
- `read_skill_resource` reads allowed references
- `read_skill_resource` rejects traversal, absolute paths, hidden paths, and
  oversized files
- skill tool handlers are registered as real handlers, not Phase 3 stubs
- `read_workspace` and `write_workspace` remain stubs
- Java request prompt context includes recommended skills but not resource
  contents or untrusted inline skill text
- package imports remain lightweight and do not import `run_agent`
- broader LingNeng tests still pass

## Acceptance Criteria

Phase 9 is complete when:

1. `skills/lingneng` contains the current LingNeng skill package set and
   reference files needed by those packages.
2. LingNeng API skill loading works without configuring the old sibling
   LingNengAI path.
3. `list_skills`, `search_skills`, `read_skill`, and
   `read_skill_resource` return real data for valid bundled skills.
4. The four skill tools are no longer Phase 3 `NOT_CONFIGURED` stubs.
5. `read_workspace` and `write_workspace` remain explicit stubs.
6. Skill resource access is bounded and path-safe.
7. Prompt context includes employee base and selected skill guidance without
   leaking local paths, Java history, inline untrusted skill text, or resource
   bodies.
8. Tests prove skill catalog, skill tools, prompt context, and toolset policy.
9. No runtime import from `/Users/rotas/Documents/work/hailun/LingNengAI` or
   old `app.*` modules is introduced.
10. The phase leaves route/handoff and provider work for Phase 10+.
