# Deploying

**Short answer: use Vercel.** `core/` is pure-stdlib Python, Vercel runs Python serverless
functions, and Netlify does not.

---

## The one-minute version

```bash
npm i -g vercel
cd ~/Documents/GitHub/aitb-hackathon
vercel          # preview URL
vercel --prod   # production
```

No environment variables. No database. No accounts to provision. There is nothing to
configure because there is nothing stateful to configure — which is the point.

---

## What actually gets deployed

```
public/index.html   →  static  · the six-chunk collection UI
api/index.py        →  lambda  · one function, every route
core/**             →  bundled · the deterministic layer
data/*-leads.json   →  bundled · verified leads per city
```

| Route | Does |
|---|---|
| `GET /api/health` | liveness, and whether `countback.py` actually bundled |
| `GET /api/leads?city=fresno` | verified leads for a city |
| `POST /api/state` | facts → progress, next questions, templates, timeline, warnings |
| `POST /api/render` | facts → one self-contained HTML document |
| `POST /api/replan` | facts + changes → the dominoes |

---

## The gotcha that will bite you — already handled

`core/timeline.py` loads `countback.py` at runtime with `importlib`, from a path inside
`.claude/`:

```python
_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / ".claude" / "skills" / ...
```

That is deliberate — the ownership rule says extend `countback.py`, never fork it. But
**Vercel's bundler traces static imports**, and a dynamic `spec_from_file_location` is
invisible to it. Left alone, the file does not ship and the function dies on the first cold
start with a confusing `ImportError`.

The fix is in `vercel.json`:

```json
"includeFiles": "{core/**,data/**,.claude/skills/timeline/scripts/**}"
```

`tests/test_api.py::TestDeploymentContract` asserts this stays true, and `/api/health`
reports `countback_loaded` so you can confirm it in one curl after deploying:

```bash
curl https://YOUR-DEPLOY.vercel.app/api/health
```

If it ever returns `"countback_loaded": false`, `includeFiles` is wrong — nothing else.

---

## Why there is no database

The plan lives in the **URL hash**, base64-encoded. That is not a shortcut, it is the
architecture:

- **No account.** Value before signup. Every auth wall between a curious librarian and
  their first useful timeline is a place the funnel ends.
- **Shareable by default.** The link *is* the plan. Send it to a colleague, bookmark it.
- **We never hold anyone's data.** Nothing to breach, nothing to migrate, no GDPR surface.
- **The artifact outlives the service.** "Download your plan" produces a self-contained
  HTML file that opens offline, forever, with the service switched off.

If you later need saved plans, add **one** table — `plans(id, slug, json, updated_at)` —
behind a shareable link. Not twenty-eight. Multi-tenancy is a column until there are
tenants.

---

## Demo video on the landing page

`public/index.html` has a "Watch the demo" pill under the title that expands into an
embedded video on click — the iframe (and YouTube's own JS) doesn't load until someone
actually clicks, so it costs the landing page nothing by default.

**To wire it up:**

1. Upload `HACKATHON VID DEMO 1.mov` to YouTube as **Unlisted** (not Private, not Public —
   Unlisted means anyone with the link can watch, but it won't appear in search or on your
   channel). YouTube transcodes it server-side, which also solves compressing the raw
   320MB source — nothing to do on your end.
2. Copy the video ID from the URL: `youtube.com/watch?v=`**`abc123XYZ`** → `abc123XYZ`.
3. In `public/index.html`, set `const DEMO_VIDEO_ID = 'abc123XYZ';` (search for
   `DEMO_VIDEO_ID`). Leave it as `''` and the section renders nothing — an unset
   placeholder should never ship as if it were a real link.

That's the only edit needed. The CSP in `vercel.json` already allow-lists exactly two
origins for this: `frame-src https://www.youtube-nocookie.com` (the embed itself, using
YouTube's cookie-free domain) and `img-src ... https://i.ytimg.com` (the thumbnail). Nothing
broader was opened.

**Why not embed it straight from Drive** — the option this replaced: Drive's preview isn't
built for production traffic (it rate-limits and throws "too many views" once a file gets
real traffic), requires "anyone with the link" sharing you don't control, has no adaptive
bitrate, and Google can change embed behavior without notice. YouTube unlisted gets you
free transcoding and a stable embed for the same one-link-sharing tradeoff.

---

## Netlify

**Netlify Functions run JavaScript, TypeScript, and Go. There is no Python runtime.** So
the interactive product cannot run there as written. `netlify.toml` in this repo ships the
**static half only** — the generated `plan.html`, which is a genuine deliverable (it opens
offline on any device) but is a fixed plan, not the collection flow.

Three ways forward if Netlify is a hard requirement:

1. **Split it.** Host `public/` on Netlify, run the API on Vercel/Fly/Render, and point
   `const API` in `public/index.html` at that origin. CORS is already permissive.
2. **Static only.** Ship the generated artifact. Costs you the interactivity.
3. **Port `core/` to TypeScript.** It is ~600 lines of pure logic with no I/O, so it is
   tractable — but it forks the determinism guarantee across two implementations, which is
   the precise thing this architecture exists to prevent. Only if you must.

---

## Running it locally

```bash
python3 scripts/devserver.py
```

Serves `public/` and routes `/api/*` through the same handler Vercel runs, so local
behaviour matches deployed behaviour. Single-threaded, no rate limiting — dev only.

```bash
python3 -m unittest discover -s tests -t . -q
```

---

## Before you call it shipped

- [ ] `curl .../api/health` returns `"countback_loaded": true`
- [ ] Complete both chunks on a **phone that is not yours**, on cell data. This is the
      standing rule and it is the one most often skipped.
- [ ] "Download your plan" produces a file that opens with **wifi off**.
- [ ] Network tab on the artifact shows **zero** outbound requests.
- [ ] A lead card's source link opens the page it claims.

---

## Cost and limits

Free tier is ample: the function is stdlib-only, does no I/O beyond reading a bundled JSON
file, and returns in milliseconds. `maxDuration` is set to 15s purely as a backstop; real
responses are far under it.

Two things genuinely missing before real traffic:

- **No rate limiting.** `/api/render` is the most expensive route and is unauthenticated.
  Add Vercel's firewall rules or a KV-backed limiter before publicising the URL.
- **CORS is `*`.** Fine today — the API is deterministic compute over client-supplied data,
  with no cookies, credentials, or secrets. Revisit if that ever stops being true.
