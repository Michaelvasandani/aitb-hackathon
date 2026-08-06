# Deploying

> **This page used to say the product was a static site with no backend. That is no longer
> true, and believing it is how a deploy ends up serving a broken app.** ADR-0001 put the
> live Agent SDK pipeline back on the critical path. The history is preserved at the bottom,
> because the reasoning still explains why the deterministic core is duplicated in JS.

**Deploy target: Vercel.** It is the only host that runs what this app now needs.

The site is not self-contained. Three of its features are HTTP calls to serverless functions:

| Page | Calls | Backed by |
|---|---|---|
| `public/index.html` — the planner | `POST /api/plan` | `api/plan.js` — the paid Agent SDK run, up to 800s |
| `public/plan-view.html` — a permalink | `GET /api/plan/:id` | `api/plan/[id].js` → Neon Postgres |
| `public/plan-gallery.html` | `GET /api/plans` | `api/plans.js` → Neon Postgres |
| Email a plan (optional) | `POST /api/email` | `api/email.js` → Resend |

**A static host serves all four as 404**, and the `/plan/:id` permalink rewrite lives in
`vercel.json`, so it does not exist elsewhere either. Cloudflare Pages, GitHub Pages and
Netlify are all static-only for this repo's purposes — `netlify.toml` and `public/_headers`
are leftovers from the static era, not live configuration.

## Deploy on Vercel

1. Vercel → **Add New… → Project** → import this repo. No framework preset; `vercel.json`
   already sets `outputDirectory: public`, the function config, the rewrites and the CSP.
2. Set the environment variables below.
3. Apply the database schema and verify the spend guard (see below). **Both, in order.**

Pushes to `main` deploy automatically through Vercel's Git integration. Nothing in GitHub
Actions deploys this app — `.github/workflows/deploy.yml` only runs the tests.

### Environment variables

| Variable | Required | What breaks without it |
|---|---|---|
| `ANTHROPIC_API_KEY` | **yes** | `/api/plan` returns `503 endpoint_disabled` |
| `DATABASE_URL` | **yes** | No permalinks, no gallery — **and every run is refused**, because the spend guard fails closed |
| `RESEND_API_KEY` + `EMAIL_FROM` | no | `/api/email` returns `503 email_disabled` |
| `PLAN_DAILY_BUDGET_USD` | no | Defaults to $25/day |
| `PLAN_RATE_LIMIT_PER_HOUR` | no | Defaults to 5/hour per client |

Full list of cost knobs: `docs/COST-CONTROLS.md`.

### Before the first deploy — do not skip this

```bash
npm run db:init          # creates the runs + run_reservations tables
npm run db:verify-guard  # proves the reservation SQL actually executes
```

The spend guard **fails closed**: if `run_reservations` is missing or its SQL is wrong,
`/api/plan` returns 503 for every request and the app looks dead. The unit tests cannot
catch that — they inject a fake query function and never execute SQL. `db:verify-guard`
does, against the real database.

### Why not GitHub Pages

The Actions workflow used to publish `public/` there. It failed with *"Get Pages site
failed"* because Pages had never been enabled on the repo — and enabling it would have been
worse than the failure, replacing a loud error with a site that deploys successfully and
serves a planner whose every submission 404s. The deploy job was removed; see the note at
the bottom of `.github/workflows/deploy.yml`.

---

## History: why the deterministic core exists twice

*Kept because it explains a live design constraint, not because it describes the current
deployment.*

The API was once deleted from the critical path, because auditing it showed it did exactly
one piece of I/O: reading a JSON file that was already bundled. No database, no secrets, no
auth, no external calls — just deterministic computation over data the client already had.

So `core/*.py` was ported to `public/js/core.js` and the product became a static file. ADR-0001
later reversed that for the *research* pipeline, which genuinely needs a server (an API key
that cannot ship to a browser, and minutes of runtime). **The port stayed** — and is now
load-bearing on the server too: `api/_lib/deterministic.js` computes every timeline from
`public/js/core.js` before a token is spent (`docs/COST-CONTROLS.md`, Tier 0).

That is why the conformance guarantee below still matters, and matters more than it did.

---

## The duplicate-implementation risk, and why it is safe

Two implementations of the same rules is exactly the fork this project's architecture
review argued *against*. Two things make it safe, and both fail the build if violated:

**1. The rules are generated, not copied.** `public/js/rules.js` is projected from
`core/model.py` by `scripts/export_rules.py` — the phase graph, gates, unlock conditions,
artifact edges, thresholds, the artifact stylesheet, and the answer-implication copy. Change
a rule in one place only. `TestGeneratedRulesAreCurrent` regenerates and fails on any diff.

```bash
python3 scripts/export_rules.py   # after editing core/model.py, then commit both
```

**2. The logic is diffed against a fixture matrix.** `tests/test_conformance.py` runs ~60
cases — sub-floor runways, $0 budgets, holiday collisions, overdue artifacts, and runways
chosen to land on rounding boundaries — through *both* implementations and asserts byte-
identical results for timelines, gates, templates, warnings, budgets, hazards, and the
replan sentence.

That test earned its keep twice already:

- **Ordering.** `rules.js` was first generated with sorted keys, so JS iterated the artifact
  graph alphabetically while Python used declaration order. Same content, different BFS
  order, different replan sentence. Now the export preserves `model.py` order.
- **Rounding.** Python's `round()` is half-to-**even**; JavaScript's `Math.round` is
  half-**up**. `round(2.5)` is `2` in Python and `3` in JS — and that sits directly inside
  the countback (`round(weeks × factor × 7)`), where it silently shifts phase dates by a
  day. `pyRound()` in `core.js` reproduces Python's behaviour. Swapping it back for
  `Math.round` breaks 12+ conformance cases immediately.

---

## Favorites, recent searches, and the city lead cache

Two different problems, two different answers — and only one of them needs a database.

### Favorites + recents → `localStorage`, no database

The plan already lives in the URL hash, so a favorite is just a **link the app manages**.
`public/js/store.js` keeps a capped list of favorites and the last 8 cities. Consequences
worth being explicit about:

- No account, no auth wall, no server round-trip. Value still precedes signup.
- Nothing about a user ever leaves their device, so there is no PII, no consent banner,
  and nothing to breach. `store.exportAll()` returns *everything* the app holds about
  someone — that makes "we hold nothing" verifiable rather than a claim.
- Works offline and survives the site being switched off.
- **Trade-off, stated plainly:** favorites are per-device. Syncing them needs identity, and
  an auth wall is where the funnel dies for the non-technical organizers this is built for.

Private-browsing modes throw on write. The store catches that and the saved-plans strip
simply does not render — a broken store never becomes a broken planner.

### The lead cache → this is what earns a database

`public/data/fresno-leads.json` came from a research pass that took ~20 minutes of agent
work. Search any other city today and you get an honest empty state. The cache fixes that:
research a city once, serve it to everyone afterwards.

It needs **no accounts**, because it is global rather than per-user — which is exactly why
it is worth building and favorites-sync is not.

**Cloudflare D1**, two tables, no user table:

```bash
npx wrangler d1 create aitb-leads                                  # prints database_id
# paste it into wrangler.toml
npx wrangler d1 execute aitb-leads --remote --file=schema.sql
python3 scripts/seed_cache.py > seed.sql
npx wrangler d1 execute aitb-leads --remote --file=seed.sql
```

Free tier is 5 GB storage and 5 M row-reads/day. A cached city is ~40 KB.

### The rule this feature obeys: the database is never on the critical path

Leads load in three layers, each optional:

1. **Bundled file** in `public/data/` — instant, works offline, ships with the site
2. **D1 cache** — cities researched since the last deploy
3. **Nothing** — an honest empty state, and the city joins the research queue

Every failure mode of the database returns HTTP 200 with empty leads: no binding
configured, D1 throwing, unknown city, malformed request. Tested explicitly — see
`scripts/test_client_js.mjs`. **If you never create the D1 database at all, the site
behaves exactly as it does today.**

### What gets recorded, and what doesn't

`POST /api/demand` fires **only** when a real organizer clears chunk 1 for a city with no
leads — not on page load, not per keystroke. A crawler hitting the homepage is not demand,
and inflating that number would send someone to research a city nobody asked for.

It stores a city slug and a counter. No identity, no IP, no session. The research queue is
one query:

```sql
SELECT d.city_label, d.requests FROM city_demand d
LEFT JOIN lead_cache c USING (city_slug)
WHERE c.city_slug IS NULL ORDER BY d.requests DESC;
```

### Adding a city

Run a research pass, write `public/data/<slug>-leads.json` in the same shape, then either
redeploy (bundled — faster, survives the DB being down) or reseed (cached — no deploy
needed). Both paths work.

Cached leads older than **120 days** are served with a visible staleness warning rather
than quietly presented as current. Venues close and people change jobs; a stale list is
worse than an empty one because the organizer trusts it.

---

## Demo video on the landing page

A "Watch the demo" pill under the title expands into an embed on click — the iframe and
YouTube's JS never load until someone asks, so the page costs nothing by default.

1. Upload the `.mov` to YouTube as **Unlisted**. YouTube transcodes server-side, which also
   solves compressing the raw 320 MB source.
2. Copy the ID: `youtube.com/watch?v=`**`abc123XYZ`**
3. Set `const DEMO_VIDEO_ID = 'abc123XYZ';` in `public/index.html`.

Left as `''` the section renders nothing — an unset placeholder should never ship looking
like a real link. CSP already allow-lists exactly two origins for this
(`youtube-nocookie.com` for the frame, `i.ytimg.com` for the thumbnail) and a test keeps
that allowlist from widening.

**Not Drive:** its preview rate-limits and throws "too many views" under real traffic, needs
anyone-with-the-link sharing you do not control, has no adaptive bitrate, and Google changes
embed behaviour without notice.

---

## Local development

```bash
python3 -m http.server 8000 --directory public   # the real thing, exactly as deployed
python3 scripts/devserver.py                     # only if you want the optional API too
python3 -m unittest discover -s tests -t . -q    # 151 tests
```

---

## Before you call it shipped

- [ ] Complete both chunks on a **phone that is not yours**, on cell data.
- [ ] "Download your plan" produces a file that opens with **wifi off**.
- [ ] Network tab on the downloaded artifact shows **zero** outbound requests.
- [ ] A lead card's source link opens the page it claims.
- [ ] The shareable link (the URL hash) restores the plan in a fresh browser.

---

## Notes and limits

- **The plan lives in the URL hash**, base64-encoded. The link *is* the plan: shareable,
  bookmarkable, and no user data ever reaches a server. If you later need saved plans, add
  **one** table — `plans(id, slug, json, updated_at)` — not twenty-eight.
- **Leads are fetched per city** from `public/data/<city>-leads.json`. An unknown city
  yields no leads rather than invented ones. Add a city by dropping in a file.
- **Everything is cacheable and immutable-ish.** If you add a `Cache-Control` policy, make
  sure `index.html` stays short-lived so `js/` updates are picked up.
