# LingNeng Output Comparison Report Template

## Objective

This migration report scaffold guides comparison of LingNengAI and
LingNeng-Hermes outputs after reviewers run controlled validation cases. It
does not contain real business quality judgments, live service responses,
private conversations, signed links, credentials, local paths, or raw provider
payloads.

Fixture:
`docs/lingneng-migration/reports/2026-06-06-output-comparison-fixture.json`

## Instructions

1. Start from the JSON fixture and run each case against LingNengAI and
   LingNeng-Hermes in a controlled non-production validation environment.
2. Copy only sanitized summaries into this report. Do not paste prompt bodies,
   raw tool payloads, full attachment text, provider responses, credentials, or
   private business content.
3. Keep every unresolved item marked `pending` or `deferred` until the reviewer
   has evidence for a `pass` or `fail` decision.
4. Use the same Java-compatible request identifiers from the fixture when
   recording SSE event order, citations, artifacts, and trace summary evidence.

## Case Table

| Case id | Employee type | Scenario type | Status | Reviewer |
| --- | --- | --- | --- | --- |
| `cmp_boss_assistant_no_tool_001` | `boss_assistant` | `no_tool` | `pending` | |
| `cmp_operation_specialist_rag_001` | `operation_specialist` | `rag` | `pending` | |
| `cmp_marketing_planner_artifact_001` | `marketing_planner` | `artifact` | `pending` | |
| `cmp_marketing_content_creator_attachment_001` | `marketing_content_creator` | `attachment` | `pending` | |
| `cmp_member_operator_long_conversation_001` | `member_operator` | `long_conversation` | `pending` | |
| `cmp_product_combo_advisor_no_tool_001` | `product_combo_advisor` | `no_tool` | `pending` | |

## Per-Case Checklist

For each case, record:

- Request identity: case id, request id, tenant id, user id, conversation id,
  employee id, and employee type.
- SSE event order: expected order from the fixture and observed order from each
  runtime.
- Tool calls: whether tools were expected, which allowed tools were called, and
  whether any forbidden tool appeared.
- Citations: citation count, citation ids, and whether cited summaries matched
  the requested scenario after sanitization.
- Artifacts: artifact count, artifact ids, artifact types, and whether
  `artifact_created` agrees with `final.artifacts`.
- Trace summary: run id, terminal status, tool call count, compression or
  continuity indicators when relevant, and any non-sensitive diagnostic keys.
- Evaluator notes: concise reviewer observations, open questions, and the
  decision rationale.

## Tool Calls

Record only sanitized tool call summaries. For no-tool cases, confirm that no
business tool was called. For RAG, artifact, and attachment cases, record the
expected tool family and status, but do not paste raw tool input, raw tool
output, provider payloads, attachment contents, or generated document body text.

## Citations

Record citation ids, counts, and high-level source categories only after
sanitization. Do not include private document excerpts or live RAG payloads.
If a case does not require RAG, leave the citation section empty and explain
that citations were not expected.

## Artifacts

Record artifact ids, types, public-safe names, and whether both runtimes emitted
compatible artifact metadata. Do not include generated files, private object
locations, signed links, or conversion service payloads.

## Trace Summary

Record the public trace summary fields needed to explain the decision: run id,
terminal status, event order, tool call count, citation count, artifact count,
and long-conversation continuity indicators. Do not include raw model messages,
Java history content, private request text, or raw tool output.

## Evaluator Notes

Use this section for reviewer judgment after evidence is collected. Notes should
focus on compatibility, task completion, event contract behavior, and business
acceptability. If evidence is missing, mark the case as `pending` or `deferred`
instead of guessing.

## Comparison Scoring Notes

Suggested status meanings:

- `pending`: comparison has not been run or evidence is incomplete.
- `pass`: LingNeng-Hermes is compatible enough for the evaluated case.
- `fail`: LingNeng-Hermes differs in a material way that requires follow-up.
- `deferred`: the case cannot be judged until a dependency or reviewer is
  available.

When scoring, separate event-contract failures from output-quality concerns.
Event order, terminal status, citations, artifacts, and trace summary evidence
should be checked before subjective quality review.

## Final Decision

Overall decision: `pending`

Required evidence before changing the final decision:

- Focused Java-compatible smoke result.
- Relevant LingNeng contract test result.
- Completed case table with evaluator notes.
- Sanitized tool calls, citations, artifacts, and trace summary evidence.
- Explicit reviewer decision for whether LingNeng-Hermes is ready for the next
  validation step.
