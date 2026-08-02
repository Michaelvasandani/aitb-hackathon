# 03 — Live activity log: watch it work

> GitHub: #5 · Parent: #2

**What to build:** The browser parses the event stream from `/api/plan` and renders a read-only live activity log keyed off the stage events, so a multi-minute run reads as progress rather than a hang. It must tolerate a noisy stream and surface a failed run instead of freezing.

**Blocked by:** 01 (#3), 02 (#4)

**Status:** ready-for-agent

- [ ] Submitting the form shows a live activity log that advances through the stages (e.g. "Researching venues in <city>… found 6… verifying sources…")
- [ ] The log is read-only during the run — no mid-run intervention
- [ ] A noisy or unrecognized event does not break the log
- [ ] A failed run surfaces an error state instead of hanging
- [ ] The log visibly reflects real web-search activity (the credibility payload)
