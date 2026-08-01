---
name: managing-finances-aitb
description: AITB-scoped financial management. Route AITB sponsor deal reviews and follow-up requests.
---

# Managing Finances (AITB)

AITB-scoped router for financial and sponsor deal requests.

---

## Decision Tree

| Request pattern | Reference to read |
|-----------------|-------------------|
| "AITB deal review", "AITB sponsors", "sponsor pipeline" | [sales-deal-review](../sales-deal-review/reference.md) |
| "Pipeline analytics", "Thursday pipeline brief", "analyze AITB pipeline", "sponsor pipeline health check", "what's weird in the pipeline" | [analyzing-sales-pipeline](../analyzing-sales-pipeline/SKILL.md) |
| "AITB follow-ups", "sponsor follow-ups", "stale AITB deals" | [managing-sales-followups](../managing-sales-followups/reference.md) |
| "Look up AITB deal", "find sponsor deal" | [looking-up-deals](../looking-up-deals/reference.md) |
| "Look up AITB organization" | [looking-up-organizations](../looking-up-organizations/reference.md) |

---

## Guardrails

- Always read the relevant reference file before executing
- **Read-only analysis:** Sub-skills are read-only until explicitly creating tasks or sending commands
- If a step fails mid-workflow, report what succeeded and what failed
