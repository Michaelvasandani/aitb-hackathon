"""Render plan state into ONE self-contained HTML file.

Inline CSS only. No external requests — no CDN, no fonts, no images, no analytics. It opens
from a Drive folder, an email attachment, or a URL, on any device, offline. The organizer can
drop it in their own Drive and own it. That portability is the product: a dashboard they have
to log into is a dashboard they stop opening.

Nothing here invents content. Every number comes from the deterministic core; every lead comes
from `plan.json` and must carry a source URL. A missing section renders as thin, never as full.
"""

import datetime as dt
import html
import json

from . import gates, model, plan as plan_mod

CSS = """
:root{--bg:#fff;--fg:#14181f;--muted:#5b6472;--line:#e6e9ef;--card:#f7f8fa;
--accent:#4f46e5;--accent-soft:#eef0ff;--hi:#0f8a4f;--hi-bg:#e6f6ec;--med:#b7791f;
--med-bg:#fdf3e2;--lo:#b23b3b;--lo-bg:#fbebeb;--warn:#b23b3b;--warn-bg:#fbebeb;
--lock:#8a8f98;--lock-bg:#f0f1f4}
@media (prefers-color-scheme:dark){:root{--bg:#0f1319;--fg:#e8ebf0;--muted:#9aa4b2;
--line:#232a35;--card:#171c24;--accent:#8b85f5;--accent-soft:#1e2130;--hi:#4ade80;
--hi-bg:#10281b;--med:#eab308;--med-bg:#2a2410;--lo:#f87171;--lo-bg:#2a1414;
--warn:#f87171;--warn-bg:#2a1414;--lock:#6b7280;--lock-bg:#161a21}}
:root[data-theme=dark]{color-scheme:dark;--bg:#0f1319;--fg:#e8ebf0;--muted:#9aa4b2;
--line:#232a35;--card:#171c24;--accent:#8b85f5;--accent-soft:#1e2130;--hi:#4ade80;
--hi-bg:#10281b;--med:#eab308;--med-bg:#2a2410;--lo:#f87171;--lo-bg:#2a1414;
--warn:#f87171;--warn-bg:#2a1414;--lock:#6b7280;--lock-bg:#161a21}
:root[data-theme=light]{color-scheme:light;--bg:#fff;--fg:#14181f;--muted:#5b6472;
--line:#e6e9ef;--card:#f7f8fa;--accent:#4f46e5;--accent-soft:#eef0ff;--warn:#b23b3b;
--warn-bg:#fbebeb;--lock:#8a8f98;--lock-bg:#f0f1f4}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:32px 20px 80px}
header.hero{border-bottom:1px solid var(--line);padding-bottom:20px}
h1{font-size:1.9rem;margin:0 0 6px;letter-spacing:-.01em}
.shape{color:var(--muted);font-size:1.05rem}
.countdown{display:inline-block;margin-top:10px;padding:4px 12px;border-radius:999px;
background:var(--accent-soft);color:var(--accent);font-weight:600;font-size:.9rem}
.principles{margin:16px 0 0;padding:10px 14px;border-radius:10px;background:var(--accent-soft);
font-size:.85rem}
.principles b{color:var(--accent)}
section{margin-top:40px}
h2{font-size:1.3rem;margin:0 0 14px;padding-bottom:6px;border-bottom:2px solid var(--line)}
h2 .thin{margin-left:8px;padding:2px 8px;border-radius:6px;background:var(--warn-bg);
color:var(--warn);font-size:.72rem;font-weight:700;vertical-align:middle}
/* progress: six chunks, six gates. the gate IS the progress bar. */
ol.chunks{list-style:none;display:flex;gap:6px;padding:0;margin:24px 0 0;flex-wrap:wrap}
ol.chunks li{flex:1 1 120px;padding:10px 12px;border-radius:10px;border:1px solid var(--line);
background:var(--card);font-size:.82rem}
ol.chunks li .n{font-weight:700;font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;
color:var(--muted)}
ol.chunks li .t{font-weight:700;margin-top:2px}
ol.chunks li .g{color:var(--muted);font-size:.75rem;margin-top:4px}
ol.chunks li.complete{border-color:var(--hi);background:var(--hi-bg)}
ol.chunks li.complete .n,ol.chunks li.complete .t{color:var(--hi)}
ol.chunks li.active{border-color:var(--accent);background:var(--accent-soft);
box-shadow:0 0 0 2px var(--accent-soft)}
ol.chunks li.active .n,ol.chunks li.active .t{color:var(--accent)}
ol.chunks li.locked{opacity:.6}
.warnbox{background:var(--warn-bg);border:1px solid var(--warn);border-radius:10px;
padding:12px 14px;margin-bottom:10px;color:var(--warn);font-size:.9rem}
.blocking{background:var(--warn-bg);border:2px solid var(--warn);border-radius:10px;
padding:14px 16px;margin-bottom:12px}
.blocking .h{font-weight:800;color:var(--warn)}
.blocking .w{color:var(--fg);font-size:.9rem;margin-top:4px}
.answer{padding:12px 0;border-bottom:1px solid var(--line)}
.answer .q{font-weight:600}
.answer .impl{color:var(--muted);font-size:.92rem}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:.9rem;min-width:520px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:.8rem;text-transform:uppercase;
letter-spacing:.03em}
td.risk{color:var(--warn);font-weight:600}
.gantt{margin-top:6px}
.gantt .row{display:flex;align-items:center;gap:10px;padding:6px 0;
border-bottom:1px solid var(--line)}
.gantt .nm{min-width:150px;font-weight:600;font-size:.88rem}
.gantt .track{position:relative;flex:1;height:16px;background:var(--lock-bg);border-radius:4px}
.gantt .bar{position:absolute;top:0;height:16px;background:var(--accent);border-radius:4px;
opacity:.85}
.gantt .bar.risk{background:var(--warn)}
.gantt .dt{min-width:96px;text-align:right;color:var(--muted);font-size:.78rem}
/* templates: they unlock, they don't all appear — and a locked one says why. */
ul.tpl{list-style:none;padding:0;margin:0;display:grid;
grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
ul.tpl li{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:var(--card)}
ul.tpl li.on{border-color:var(--hi)}
ul.tpl li.off{background:var(--lock-bg);border-style:dashed}
ul.tpl .nm{font-weight:700;font-size:.92rem}
ul.tpl li.off .nm{color:var(--lock)}
ul.tpl .why{font-size:.8rem;color:var(--muted);margin-top:4px}
ul.tpl .tag{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
ul.tpl li.on .tag{color:var(--hi)}
ul.tpl li.off .tag{color:var(--lock)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.card .top{display:flex;justify-content:space-between;align-items:start;gap:8px}
.card .name{font-weight:700;font-size:1.02rem}
.card .one{color:var(--muted);font-size:.88rem;margin:4px 0 8px}
.badge{padding:2px 8px;border-radius:999px;font-size:.72rem;font-weight:700;white-space:nowrap}
.badge.high{background:var(--hi-bg);color:var(--hi)}
.badge.med{background:var(--med-bg);color:var(--med)}
.badge.low{background:var(--lo-bg);color:var(--lo)}
.signals{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.sig{background:var(--accent-soft);color:var(--accent);font-size:.74rem;padding:2px 8px;
border-radius:6px}
.card a.src{color:var(--accent);font-size:.82rem;word-break:break-all}
.move{font-size:.85rem;margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)}
.move b{color:var(--muted);font-weight:600}
.empty{color:var(--muted);font-size:.9rem;padding:14px;border:1px dashed var(--line);
border-radius:10px}
ul.actions{padding-left:20px}
ul.actions li{margin:6px 0}
.sentence{background:var(--accent-soft);border-left:4px solid var(--accent);border-radius:8px;
padding:14px 16px;font-size:1rem;margin-top:10px}
footer{margin-top:60px;color:var(--muted);font-size:.8rem;text-align:center;
border-top:1px solid var(--line);padding-top:16px}
a{color:var(--accent)}
@media (max-width:560px){.wrap{padding:20px 14px 60px}h1{font-size:1.5rem}
.gantt .nm{min-width:110px}.gantt .dt{display:none}}
@media print{body{background:#fff;color:#000}.wrap{max-width:none}
ol.chunks li,ul.tpl li,.card{break-inside:avoid}footer{display:none}
a{text-decoration:underline}}
"""

# What each answer means for the plan. This is the "your answers, with implications" section —
# it is what makes the page feel like a plan rather than a form receipt.
IMPLICATIONS = {
    "CITY": "Everything below is sourced for this city — no national boilerplate.",
    "HAS_LOCAL_ANCHOR": {
        True:  "You have the person who unlocks venue, nonprofits, and credibility.",
        False: "The blocking task above. No template substitutes for this.",
    },
    "EVENT_DATE": "Every date below counts back from this one.",
    "PARTICIPANT_CAP": "Drives food, team count, badges, and the mentor ratio.",
    "IS_FREE": {
        True:  "Free entry — the normal shape. Costs go to sponsors or in-kind.",
        False: "Ticketed — factor no-shows into your headcount, not your revenue.",
    },
}


def e(x):
    return html.escape(str(x), quote=True)


def _implication(field, value):
    imp = IMPLICATIONS.get(field)
    if isinstance(imp, dict):
        return imp.get(value)
    return imp


def _bar_geometry(rows):
    """Map each phase window onto a 0-100% track spanning the whole plan."""
    if not rows:
        return []
    starts = [dt.date.fromisoformat(r["start_date"]) for r in rows]
    ends = [dt.date.fromisoformat(r["end_date"]) for r in rows]
    t0, t1 = min(starts), max(ends)
    span = max(1, (t1 - t0).days)
    out = []
    for r in rows:
        s = (dt.date.fromisoformat(r["start_date"]) - t0).days / span * 100
        w = max(1.5, (dt.date.fromisoformat(r["end_date"])
                      - dt.date.fromisoformat(r["start_date"])).days / span * 100)
        out.append((r, s, min(w, 100 - s)))
    return out


def render(facts, leads=None, today=None, title=None):
    """Return one complete HTML document as a string."""
    today = today or dt.date.today().isoformat()
    st = plan_mod.state(facts, today)
    leads = leads or {}
    city = facts.get("CITY") or "Your city"
    parts = []

    # ---------------------------------------------------------------- header
    parts.append(f'<header class="hero"><h1>{e(city)} Hackathon Plan</h1>')
    shape = " · ".join(str(x) for x in [
        facts.get("ORG_NAME"),
        f"{facts['EVENT_LENGTH']}-day" if facts.get("EVENT_LENGTH") else None,
        f"cap {facts['PARTICIPANT_CAP']}" if facts.get("PARTICIPANT_CAP") else None,
        facts.get("FOCUS_AREA"),
    ] if x)
    if shape:
        parts.append(f'<div class="shape">{e(shape)}</div>')
    if facts.get("EVENT_DATE"):
        d = st["timeline"]
        parts.append(f'<span class="countdown">{e(facts["EVENT_DATE"])} · '
                     f'{d["runway_days"]} days out ({st["weeks_out"]} weeks)</span>')
    principles = "; ".join(plan_mod.FIXED_PRINCIPLES)
    parts.append(f'<div class="principles"><b>Fixed principles (every plan):</b> '
                 f'{e(principles)}</div>')

    # progress — six chunks, six gates
    parts.append("<ol class=chunks>")
    for s in st["progress"]["states"]:
        mark = {"complete": "done", "active": "you are here", "locked": "locked"}[s["state"]]
        parts.append(
            f'<li class="{s["state"]}"><div class=n>{s["n"]} · {e(mark)}</div>'
            f'<div class=t>{e(s["title"])}</div>'
            f'<div class=g>{e(s["question"])}</div></li>'
        )
    parts.append("</ol></header>")

    # ------------------------------------------------------- blocking + warnings
    if st["blocking_tasks"]:
        parts.append("<section><h2>Do this first</h2>")
        for t in st["blocking_tasks"]:
            parts.append(f'<div class=blocking><div class=h>{e(t["title"])}</div>'
                         f'<div class=w>{e(t["why"])}</div></div>')
        parts.append("</section>")

    if st["warnings"]:
        parts.append("<section><h2>What this plan is honest about</h2>")
        for w in st["warnings"]:
            parts.append(f'<div class=warnbox>{e(w)}</div>')
        parts.append("</section>")

    # ------------------------------------------------------------ your answers
    answered = [f for f in model.all_fields() if facts.get(f["field"]) not in (None, "")]
    if answered:
        parts.append("<section><h2>Your answers</h2>")
        for f in answered:
            v = facts[f["field"]]
            shown = {True: "Yes", False: "No"}.get(v, v)
            imp = _implication(f["field"], v)
            parts.append(f'<div class=answer><div class=q>{e(f["prompt"])} '
                         f'<span style="font-weight:400">{e(shown)}</span></div>'
                         + (f'<div class=impl>{e(imp)}</div>' if imp else "") + "</div>")
        parts.append("</section>")

    # --------------------------------------------------------------- timeline
    if facts.get("EVENT_DATE"):
        risky = {r["phase"] for r in st.get("at_risk", [])}
        parts.append("<section><h2>Your timeline</h2>")
        parts.append(f'<div class=sentence>{e(st["risk_sentence"])}</div>')
        parts.append('<div class=gantt>')
        for row, left, width in _bar_geometry(st["timeline"]["timeline"]):
            label = (model.COUNTBACK_ROW_LABELS.get(row["phase"])
                     or model.PHASES.get(row["phase"], {}).get("label", row["phase"]))
            cls = " risk" if row["phase"] in risky else ""
            parts.append(
                f'<div class=row><div class=nm>{e(label)}</div>'
                f'<div class=track><div class="bar{cls}" '
                f'style="left:{left:.1f}%;width:{width:.1f}%"></div></div>'
                f'<div class=dt>{e(row["start_date"])}</div></div>'
            )
        parts.append("</div>")

        parts.append('<div class=scroll><table><thead><tr><th>Phase</th><th>Window</th>'
                     '<th>Start</th><th>End</th><th>Days</th><th>Do</th></tr></thead><tbody>')
        for row in st["timeline"]["timeline"]:
            label = (model.COUNTBACK_ROW_LABELS.get(row["phase"])
                     or model.PHASES.get(row["phase"], {}).get("label", row["phase"]))
            flag = ' class=risk' if row["phase"] in risky else ""
            parts.append(
                f'<tr><td{flag}>{e(label)}</td><td>{e(row["window"])}</td>'
                f'<td>{e(row["start_date"])}</td><td>{e(row["end_date"])}</td>'
                f'<td>{row["duration_days"]}</td>'
                f'<td>{e("; ".join(row["actions"]))}</td></tr>'
            )
        parts.append("</tbody></table></div></section>")

    # --------------------------------------------------------------- templates
    tpl = gates.template_states(facts)
    unlocked = sum(1 for t in tpl if t["unlocked"])
    parts.append(f"<section><h2>Your templates <span style='font-weight:400;color:var(--muted);"
                 f"font-size:.8rem'>{unlocked} of {len(tpl)} unlocked</span></h2>")
    parts.append("<ul class=tpl>")
    for t in tpl:
        if t["unlocked"]:
            parts.append(f'<li class=on><div class=tag>Unlocked</div>'
                         f'<div class=nm>{e(t["label"])}</div></li>')
        else:
            parts.append(f'<li class=off><div class=tag>Locked</div>'
                         f'<div class=nm>{e(t["label"])}</div>'
                         f'<div class=why>{e(t["reason"])}</div></li>')
    parts.append("</ul></section>")

    # ------------------------------------------------------------- local leads
    for key, heading, floor in (("venues", "Venues", 3),
                                ("sponsors", "Sponsors", 10),
                                ("in_kind_partners", "In-kind partners", 0),
                                ("mentors", "Judges & mentors", 6)):
        items = leads.get(key) or []
        thin = ' <span class=thin>thin</span>' if len(items) < floor else ""
        parts.append(f"<section><h2>{e(heading)}{thin}</h2>")
        if not items:
            parts.append('<div class=empty>Nothing sourced yet. This section stays empty '
                         'rather than guessing — every lead here carries a source link you '
                         'can click.</div></section>')
            continue
        parts.append("<div class=cards>")
        for ld in items:
            # Sourced or omitted. A lead with no source URL is not rendered at all.
            if not ld.get("source_url"):
                continue
            conf = ld.get("confidence", "low")
            parts.append(
                f'<div class=card><div class=top><div class=name>{e(ld.get("name", "—"))}</div>'
                f'<span class="badge {e(conf)}">{e(conf)}</span></div>'
                f'<div class=one>{e(ld.get("one_liner", ""))}</div>'
                + '<div class=signals>'
                + "".join(f'<span class=sig>{e(s)}</span>' for s in ld.get("signals", []))
                + '</div>'
                f'<a class=src href="{e(ld["source_url"])}" rel="noopener noreferrer" '
                f'target=_blank>{e(ld["source_url"])}</a>'
                + (f'<div class=move><b>First move:</b> {e(ld["suggested_first_move"])}</div>'
                   if ld.get("suggested_first_move") else "")
                + "</div>"
            )
        parts.append("</div></section>")

    # ------------------------------------------------------------ next actions
    na = st["next_action"]
    parts.append("<section><h2>What to do next</h2><ul class=actions>")
    parts.append(f'<li><b>{e(na["say"])}</b></li>')
    for t in st["blocking_tasks"]:
        parts.append(f'<li>{e(t["title"])}</li>')
    parts.append("</ul></section>")

    stamp = dt.datetime.now().isoformat(timespec="minutes")
    parts.append(
        f'<footer>Generated {e(stamp)} · dates and gates computed deterministically · '
        f'cost figures are illustrative until you add real quotes</footer>'
    )

    doc_title = title or f"{city} Hackathon Plan"
    return (
        "<!doctype html>\n<html lang=en>\n<head>\n<meta charset=utf-8>\n"
        '<meta name=viewport content="width=device-width,initial-scale=1">\n'
        f"<title>{e(doc_title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        '<div class=wrap>\n' + "\n".join(parts) + "\n</div>\n</body>\n</html>\n"
    )


def write(facts, path="plan.html", leads=None, today=None):
    import pathlib
    html_doc = render(facts, leads=leads, today=today)
    pathlib.Path(path).write_text(html_doc, encoding="utf-8")
    return path


def from_plan_json(path="plan.json", out="plan.html", today=None):
    p = plan_mod.load(path)
    return write(p.get("facts", {}), path=out, leads=p.get("leads"), today=today)


if __name__ == "__main__":  # pragma: no cover
    from .cli import DEMO_CHUNK1, DEMO_CHUNK1_GATE, DEMO_CHUNK2, DEMO_CHUNK2_GATE, TODAY
    f = {}
    for d in (DEMO_CHUNK1, DEMO_CHUNK1_GATE, DEMO_CHUNK2, DEMO_CHUNK2_GATE):
        f.update(d)
    print(write(f, today=TODAY))
