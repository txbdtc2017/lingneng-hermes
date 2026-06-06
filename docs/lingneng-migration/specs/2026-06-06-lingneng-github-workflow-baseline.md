# LingNeng GitHub Workflow Baseline

## Repository Remote

This LingNeng-Hermes checkout is treated as GitHub-hosted.

Observed remote during Phase 0 Task 0.2:

```text
origin	git@github.com:txbdtc2017/lingneng-hermes.git (fetch)
origin	git@github.com:txbdtc2017/lingneng-hermes.git (push)
```

Because the observed fetch and push remote is
`git@github.com:txbdtc2017/lingneng-hermes.git`, later workflow planning should
use that GitHub repository as the baseline remote unless the controller records
an explicit remote change.

## Branch Flow

Runtime implementation work happens on `dev`.

Validation and promotion flow uses `test`. Runtime changes should be verified on
the task branch or active implementation branch before they are promoted through
the repository's normal branch process toward `test`.

Production stabilization and release policy are outside Phase 0. They should be
defined only after the Java-compatible runtime, contract tests, and deployment
boundary have enough evidence for a release process.

## CI/CD Target

Future automation targets GitHub Actions.

GitHub Actions is the intended surface for pull request checks, push checks,
contract tests, image build checks, and protected environment promotion when
those capabilities are planned in a later deployment phase.

Jenkins and Gitea are not target CI/CD surfaces for this repository.

## Deferred Deployment Boundary

Phase 0 is documentation-only and does not create runtime, Docker, deployment,
or CI assets.

The following work is deferred until the later deployment phase:

- Docker image build.
- Docker Compose deployment.
- Server deploy scripts.
- Rollback automation.
- GitHub Actions deployment workflows.

The deferred boundary does not remove these needs from the roadmap. It keeps
them out of the runtime implementation phases until the Java-compatible API,
session policy, SSE bridge, and safe LingNeng toolset are implemented and
verified.

## Phase Execution Rules

Every migration phase must follow this gate sequence:

```text
phase spec -> phase plan -> subagent-driven execution
```

Each phase spec and plan must be stored in this repository under:

```text
docs/lingneng-migration/specs/
docs/lingneng-migration/plans/
```

After context compaction, resume, or handoff, reload these three durable total
context files before writing specs, writing plans, changing runtime code,
running verification, committing, or pushing:

1. `LINGNENG_MIGRATION_CONTEXT.md`
2. `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
3. `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

Phase task execution may commit and push only after the relevant verification
commands pass and only when the controller-approved execution instructions allow
that task worker to commit and push.

## Secrets And Environment Boundary

Secrets must not be committed to Git.

Future GitHub Actions workflows should use repository secrets or protected
environment secrets for LLM provider keys, Java internal API keys, web search
keys, image registry credentials, and any external service credentials.

Deployment `.env` files, server credentials, registry tokens, MinIO keys, Redis
credentials, Milvus credentials, Nacos credentials, RocketMQ credentials, and
provider API keys remain outside tracked source. Tracked examples may document
variable names with empty or clearly non-secret sample values only.

## Observed Commands

Command:

```bash
git remote -v
```

Observed output:

```text
origin	git@github.com:txbdtc2017/lingneng-hermes.git (fetch)
origin	git@github.com:txbdtc2017/lingneng-hermes.git (push)
```

Command:

```bash
git status --short --branch
```

Observed output:

```text
## dev
```

## Phase 1 Planning Notes

Phase 1 planning should treat `dev` as the implementation branch and `test` as
the validation and promotion branch.

Phase 1 should not create Docker images, Compose files, deploy scripts,
rollback automation, or GitHub Actions deployment workflows. Those belong to the
later deployment phase after the runtime API contract is working.

Phase 1 should keep secrets out of Git and should use configuration boundaries
that can later map cleanly to GitHub Actions repository or environment secrets.

Before Phase 1 runtime code starts, the controller should ensure the dedicated
Phase 1 spec and Phase 1 plan are approved, then execute through
subagent-driven task slices with verification before any commit or push.
