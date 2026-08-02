# Web intake form, streamed run, and self-contained HTML output

## Status

accepted — **amended by [ADR-0003](0003-persist-runs-public-gallery.md)**, which reverses
the "**No server persistence in v1**" clause: finished runs are now persisted to Neon Postgres
and browsable in a public gallery. Everything else here (one-shot form, streamed activity log,
self-contained HTML in a sandboxed iframe, key-rotation as the kill switch) still stands.

## Decision

The web front-end is replaced by **one short intake form** collecting the five agent inputs
(city, time constraints, budget, audience, purpose) plus org name and the local-anchor
question, mapped to the data-contract `inputs` object and **POSTed once**. The function
**streams run progress** back to the browser (SSE / streamed response) as a read-only live
activity log, then returns the finished **self-contained `plan.html`** (alongside `plan.json`),
displayed in a **sandboxed `<iframe srcdoc>`** with a Download button. **No server
persistence in v1.** The endpoint is protected only by keeping the `ANTHROPIC_API_KEY`
server-side; the kill switch is **rotating/deleting the key** — no access gate, no rate limit.

## Why

The old six-chunk form collected `facts` and gated templates — logic that lived in the
deterministic core, now set aside (ADR-0001). An agentic run also needs its seed inputs up
front to go research, and it *researches* venues/sponsors rather than collecting them, so
most chunk fields are obsolete; the site was also missing `audience` and `purpose` entirely
(the mismatch that motivated this work). A **form** over a conversational intake because
ADR-0001's runtime is a single stateless invocation — multi-turn chat would need session
state that fights that model. **Streaming** because a silent 3-minute wait reads as broken
and the "watch it search the web" moment is the credibility payload. **iframe srcdoc**
because the plan HTML carries its own inline styles and must not collide with the site; being
self-contained also satisfies the CSP and the "opens on a stranger's phone, no login" test.

## Considered options

- **Conversational chat intake** (mirrors the local `intake-clarifier`): rejected — needs
  multi-turn state, conflicts with the one-shot function.
- **Keep the six-chunk facts UX, add audience/purpose**: rejected — re-introduces the
  deterministic chunk logic that ADR-0001 sets aside.
- **Access gate + rate limit + spend cap**: rejected for v1 — real infra (external store,
  Vercel KV is discontinued) for a short judged demo. Accepted risk: cost accrues between
  abuse starting and the key being pulled, so the endpoint must not be left live unwatched.
- **Persist to Vercel Blob + mint a shareable URL**: deferred past v1 (keeps the old "a plan
  is a link" feature but adds storage infra). `plan.json` is returned now so per-section
  regenerate and sharing can be built later without re-architecting.

## Consequences

- The live site's identity shifts from "six questions at a time, templates unlock" to "type
  five things, watch it research your city."
- Hard rule #6 (each section independently regenerable) is honored *structurally* — we return
  `plan.json` — but the regenerate UI is deferred past v1.
- The streamed SDK event feed is noisy; the front-end must map raw events to a few
  human-readable stages.
