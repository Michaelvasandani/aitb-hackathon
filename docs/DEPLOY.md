# Deploying

**The whole product is a static site.** No server, no database, no build step, no bundler,
no framework. `public/` is the site. That means it runs free, forever, on every host — and
there is nothing to cold-start, rate-limit, or fail at 4pm on demo day.

**Recommended: Cloudflare Pages** (unlimited bandwidth on the free plan).
**Zero-setup alternative: GitHub Pages** — the repo is already on GitHub and the workflow
is committed.

---

## Free-tier comparison, for this app specifically

| Host | Bandwidth | Build mins | Verdict |
|---|---|---|---|
| **Cloudflare Pages** | **Unlimited** | 500 builds/mo | **Best.** Nothing here can exceed it. |
| **GitHub Pages** | 100 GB/mo soft | 2,000 min/mo | Zero setup — workflow already committed. 1 GB site cap; we are ~150 KB. |
| **Netlify** | 100 GB/mo | 300 min/mo | Fine. Viable again now that no Python runtime is needed. |
| **Vercel Hobby** | 100 GB/mo | 6,000 min/mo | Fine as static. Hobby is non-commercial — see note below. |

We use roughly **150 KB per visitor** and zero compute. Every tier above is enormous
headroom; pick on preference, not limits.

> **On Vercel Hobby and commercial use:** Hobby is for non-commercial projects. This is a
> hackathon demo, so it qualifies. An organization running it commercially should upgrade
> to Pro — or just use Cloudflare Pages, which has no such restriction.

---

## Deploy it

### Cloudflare Pages
1. Pages → **Create** → **Connect to Git** → pick this repo.
2. Framework preset: **None**. Build command: **leave empty**. Output directory: **`public`**.
3. Save and Deploy.

Headers come from `public/_headers` automatically.

### GitHub Pages
Already wired: `.github/workflows/deploy.yml` runs the tests, then publishes `public/`.
Enable it once — repo **Settings → Pages → Source: GitHub Actions** — then push to `main`.

The workflow fails the deploy if the tests fail *or* if `public/js/rules.js` is stale, so a
broken or drifted build cannot reach the site.

### Netlify
Connect the repo. `netlify.toml` sets publish dir `public` and no build command.

### Vercel
```bash
npm i -g vercel && vercel --prod
```
`vercel.json` sets `outputDirectory: public`. The Python function under `api/` still
deploys and works, but **the site does not use it** — it is there for the optional
server-side path below.

---

## Why there is no backend

The API used to exist and was deleted from the critical path, because auditing it showed it
did exactly one piece of I/O: reading a JSON file that was already bundled. No database, no
secrets, no auth, no external calls — just deterministic computation over data the client
already had. A server for that is pure downside:

- a cold start the user waits through
- a bundling failure mode (`core/timeline.py` loads `countback.py` dynamically, which
  static import tracers miss)
- rate limits and a duration cap
- a host that must support Python, which ruled out Netlify entirely

So `core/*.py` was ported to `public/js/core.js` and the whole thing became a static file.

**`api/` is still in the repo** and still works — run `python3 scripts/devserver.py`. Keep
it if you later want server-side generation (bulk plans, an integration, a Pro-tier
feature). The site does not depend on it.

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
