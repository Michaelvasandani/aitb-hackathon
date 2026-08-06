# Threat Model: Hack-AI-Thon-in-a-Box

The thing that makes this app unusual: **one anonymous HTTP request causes an LLM agent with
tools to run for minutes and spend real money.** Most of the risk follows from that sentence.

Scope: the deployed Vercel app — `/api/plan`, `/api/plans`, `/api/plan/:id`, `/api/email`, the
static pages, the Neon database, and the GitHub Actions deploy.

> **Status.** Findings marked **FIXED** were confirmed by running the code (probe output and
> tests are cited), then fixed on this branch. Findings marked **ACCEPTED** or **OPEN** are
> hypotheses or known gaps, not proven exploits. Nothing here has been validated by an
> independent auditor, and one control (the durable spend guard) has **not yet executed
> against a real Postgres** — see Verification.

---

## Assets

Ranked. If everything is critical, nothing is.

| # | Asset | Owner | Leaked | Modified | Unavailable |
|---|---|---|---|---|---|
| 1 | **`ANTHROPIC_API_KEY` and the credits behind it** | repo owner | Full spend of the account, elsewhere | — | Product dead |
| 2 | **Ability to make the agent act** (tools, in the deployed sandbox) | repo owner | — | Code execution, repo tampering, egress from the function | Product dead |
| 3 | `DATABASE_URL` / Neon database | repo owner | Every plan + organizer inputs | Plans corrupted, gallery vandalised | No permalinks, no gallery |
| 4 | **Ability to send mail from the verified domain** | repo owner | — | Phishing with your domain's reputation | Email feature off |
| 5 | Saved plans + organizer inputs (city, org name, budget) | organizers | Low-sensitivity but public by default | Misleading plan shown as theirs | Gallery/permalinks down |
| 6 | GitHub Actions deploy path + secrets | repo owner | — | Attacker ships arbitrary code | No deploys |

Asset 1 is the one this document mostly exists for. Asset 2 is the one that would be worse.

---

## Entry points

Read from the code and config, not the diagram.

| Entry point | Auth | Costs money | Notes |
|---|---|---|---|
| `POST /api/plan` | **none** | **yes — $0.85–$1.79/run** | The only paid endpoint; runs the agent |
| `GET /api/plans` | none | no | Gallery list; card fields only |
| `GET /api/plan/:id` | none | no | One DB read; ids are UUIDs |
| `POST /api/email` | **none** | no (provider quota) | Disabled unless `RESEND_API_KEY` + `EMAIL_FROM` set |
| Static pages (`public/`) | none | no | CSP set in `vercel.json` |
| GitHub Actions `deploy.yml` | repo write | no | Runs on push to `main` |
| Agent's own `WebSearch` / `WebFetch` | — | yes | **Pulls attacker-controllable text into the agent's context** |

## Trust boundaries

| Boundary | Checked at the crossing | If that check were absent |
|---|---|---|
| internet → `/api/plan` | `cleanInputs` (allowlist, types, ranges, dates), then in-memory guards, then the durable reservation | Unbounded spend; nonsense plans built from junk |
| internet → agent prompt | Input fenced as untrusted data; **tool allowlist excludes `Bash`/`Edit`** | Injected text steers an agent that holds tools |
| **web page → agent** | Nothing. Fetched pages are untrusted by nature | A malicious page could try to steer the run |
| app → Postgres | Every statement parameterized; column lists from frozen constants | SQL injection |
| agent → filesystem | `Write` only, to two `os.tmpdir()` paths named by us | Repo tampering, secret exfiltration |
| CI → production | GitHub branch protection + Actions secrets | Attacker ships code |

## Attackers

| Persona | Starts with | Wants | Cheapest path |
|---|---|---|---|
| **Opportunistic scanner** | The URL | Free compute, a working exploit | POST junk to `/api/plan` in a loop |
| **Cost griefer** | The URL | Burn your Anthropic credits | Concurrent valid-looking requests |
| **Prompt injector** | A form field | The agent's tools, its context, your key | Type instructions into `city` or `purpose` |
| **Indirect injector** | A web page the agent will fetch | Same | Seed a page that ranks for "hackathon venue \<city\>" |
| **Mail abuser** | The URL | Send phishing from your domain | POST to `/api/email` with attacker HTML |
| **Curious visitor** | The gallery | Other organizers' data | Enumerate `/api/plan/:id` |

---

## Threat register (ranked)

| # | Threat | Boundary | Persona | L | I | Control | Status |
|---|---|---|---|---|---|---|---|
| 1 | **Injected text reaches an agent holding `Bash` under `bypassPermissions`** — code execution in the function, with `ANTHROPIC_API_KEY` in its env | internet → agent | Prompt injector | Med | **Critical** | `Bash`/`Edit` removed from `allowedTools` + `disallowedTools` set; input fenced as untrusted data | **FIXED** |
| 2 | **Credit exhaustion by concurrency** — all guards were in-memory, so each new serverless instance saw an empty budget; the daily breaker was per-instance too | internet → `/api/plan` | Cost griefer | **High** | **High** | `run_reservations` table; every limit inside one atomic `INSERT … WHERE`; fails closed | **FIXED**, needs live verification |
| 3 | **Past event date accepted** — produced `runway_days: -2409` and phase windows ending before they start, at the full price of a real run | internet → `/api/plan` | Any user | **High** | Med | Rejected in `cleanInputs` before any spend | **FIXED** |
| 4 | **Indirect prompt injection from a fetched page** — the agent searches the open web by design | web → agent | Indirect injector | Med | Med | Same tool allowlist as #1; no `Bash` to reach. Injected text can still corrupt *plan content* | **PARTIAL — see Accepted** |
| 5 | **Type-confusion in the budget** — `true` → $1, `"0x1F"` → 31, `-0.4` → 0 | internet → `/api/plan` | Any user | Med | Low | Booleans refused; decimal-only strings; range check before truncation | **FIXED** |
| 6 | **Mail relay** — sending attacker HTML from a verified domain | internet → `/api/email` | Mail abuser | Low | **High** | Attachment read via `store.getRun(run_id)`, never from the body; allowlist `['to','run_id','note']` | Pre-existing, **verified** |
| 7 | **A run that outlives its reservation** frees its slot early, so the concurrency ceiling stops binding | app → Postgres | Cost griefer | Low | Med | `RUN_TTL_MS` (1200s) must exceed `maxDuration` (800s); asserted in a test | **FIXED** |
| 8 | **Guard fails open on a DB outage** → unbounded spend precisely when you cannot see it | app → Postgres | Cost griefer | Low | **High** | Fails **closed** by default; `PLAN_GUARD_FAIL_OPEN=1` is opt-in and marks the run degraded | **FIXED** |
| 9 | **Client disconnect keeps the run burning tokens** | internet → `/api/plan` | Cost griefer | Med | Med | None — no abort signal threaded through `runPlan` | **OPEN** |
| 10 | **Gallery exposes organizer inputs** — every plan is public by default | internet → `/api/plans` | Curious visitor | High | Low | `LIST_COLUMNS` excludes blobs and `hidden`; ids are UUIDs (not enumerable) | **ACCEPTED** |
| 11 | **SQL injection** | app → Postgres | Scanner | Low | High | Fully parameterized; column lists frozen; asserted in a test | Pre-existing, **verified** |
| 12 | **Prototype pollution via payload** | internet → `/api/plan` | Scanner | Low | Med | Allowlist drops unknown keys; asserted in a test | Pre-existing, **verified** |
| 13 | **Compromised dependency** — the SDK runs with the API key in env | CI → prod | Supply chain | Low | **Critical** | 2 runtime deps, lockfile committed. No pinning-by-digest, no audit gate | **OPEN** |

### What was checked and found NOT to be a problem

- **IP spoofing to bypass the per-IP cap.** `clientKey` takes the leftmost `x-forwarded-for`
  entry, which is normally attacker-controlled. On Vercel it is not: Vercel **overwrites**
  the header and does not forward external IPs, explicitly to prevent spoofing
  ([request headers](https://vercel.com/docs/headers/request-headers)). **This control depends
  on that platform guarantee** — it breaks if the app is ever put behind another proxy, or
  moved off Vercel.
- **SQL injection** — every statement parameterized (#11).
- **`__proto__` in the payload** — dropped by the allowlist (#12).
- **Email as an open relay** — the attachment comes from the database by id (#6).

---

## Accepted risks

| Risk | Why accepted | What would change it |
|---|---|---|
| Plans are **public by default** in the gallery | It is the demo's whole point; inputs are a city, an org name, a budget — not personal data | Anyone submitting attendee names or contact details |
| **Indirect injection can corrupt plan *content*** (a fake venue with a real-looking source) | Bounded: the agent has no dangerous tool, and the product already requires a `source_url` per lead. It degrades plan quality, not system integrity | Anything acting on plan content automatically (auto-sent email, bookings) |
| **No authentication anywhere** | A hackathon demo; adding accounts would cost more than it protects | Real user data, or spend that outruns the daily breaker |
| **Spend limits are best-effort, not exact** | Reservations age out by time window rather than being reconciled; a crashed instance's row lingers until TTL. Over-counting briefly is the safe direction | Needing exact per-tenant billing |
| `maxTurns: 80` is the only bound on a single run's cost | A runaway run is capped by turns and the 800s timeout | Observing runs that hit the ceiling routinely |

---

## Verification plan

| Register entries | Verified by | Status |
|---|---|---|
| #1, #4 tool allowlist and prompt fencing | `tests/js/security.test.js` | Passing |
| #2, #7, #8 spend guard logic | `tests/js/security.test.js` (fake query fn) | Passing |
| **#2 spend guard SQL against a real Postgres** | `npm run db:verify-guard` | **NOT YET RUN — no database available locally** |
| #3, #5, #12 input validation | `tests/js/security.test.js` | Passing |
| #11 parameterization | `tests/js/security.test.js` | Passing |
| #6 email relay | `tests/test_email.py` | Passing |
| #9 client disconnect | — | No test; unfixed |
| #13 dependencies | `supply-chain-auditor` | Not run |
| End-to-end adversarial pass | `penetration-tester` | Not run |

### Before deploying this branch

```bash
npm run db:init          # creates run_reservations
npm run db:verify-guard  # proves the reservation SQL actually executes
```

**Do not skip the second command.** `checkDurableGuards` fails closed, so if the table is
missing or the SQL has a syntax error, `/api/plan` returns 503 for every request and the app
is down. The unit tests cannot catch that — they inject a fake query function and never
execute the SQL.
