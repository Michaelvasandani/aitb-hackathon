---
name: managing-projects-aitb
description: AITB-scoped project management. Route AITB task CRUD, routing, morning briefing, inbox review, and event planning requests.
---

# Project Management (AITB)

AITB-scoped router for project management requests.

---

## Decision Tree

| Request pattern | Reference to read |
|-----------------|-------------------|
| "Create AITB task", "new AITB task" | [creating-tasks](../creating-tasks/reference.md) |
| "AITB project", "new AITB project" | [creating-projects](../creating-projects/reference.md) |
| "Execute AITB task", "work on AITB task" | [executing-tasks](../executing-tasks/reference.md) |
| "AITB priorities", "AITB for today" | [setting-todays-priorities](../setting-todays-priorities/reference.md) |
| "AITB morning briefing" | [generating-morning-briefing](../generating-morning-briefing/reference.md) |
| "AITB inbox", "what's new in AITB" | [airtable-inbox-review](../airtable-inbox-review/reference.md) |
| "Route AITB task" | [routing-airtable-tasks](../routing-airtable-tasks/reference.md) |
| "Plan AITB event", "AITB meetup", "AITB workshop", "create/publish/edit AITB Meetup event", "reschedule AITB event" | [planning-aitb-events](../planning-aitb-events/reference.md) |

---

## Guardrails

- Always read the relevant reference file before executing
- When composing workflows, respect each reference's guardrails
- If a step fails mid-workflow, report what succeeded and what failed
