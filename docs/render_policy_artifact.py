#!/usr/bin/env python3
"""Render FOLIO-CHANGE-POLICY.md into the review artifact.

The artifact is generated from the markdown, never hand-copied, so a draft under
active revision cannot drift from the page Damien is reading. Re-run after every
edit; the output path is stable so republishing keeps the same artifact URL.

    python3 docs/render_policy_artifact.py
"""

from __future__ import annotations

import html
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
SRC = HERE / "FOLIO-CHANGE-POLICY.md"
OUT = Path.home() / "Coding Projects" / "briefs" / "board" / "folio-change-policy-draft.html"

# Sections rewritten in this review round. Everything else is the first draft and
# has not yet been through Damien's pen — worth showing, because it tells him where
# to spend attention.
REVISED = {"1", "3", "4", "5"}

OPEN_QUESTIONS = [
    ("Sections 2 and 4&ndash;7 have not had your pen on them",
     "&sect;1 and &sect;3 were rewritten with you; &sect;4 and &sect;5 were revised on your two "
     "rulings this round. &sect;2, &sect;6 and &sect;7 are still first-draft prose that only I "
     "have read. The vocabulary is now consistent throughout &mdash; no <code>T0</code>&ndash;"
     "<code>T4</code> or <code>MAJOR</code> survives except where &sect;3 and &sect;4 argue "
     "against SemVer deliberately."),
    ("&sect;6 and &sect;7 &mdash; still unreviewed",
     "&sect;1 and &sect;3 were rewritten with you; &sect;4 and &sect;5 revised on your rulings. "
     "&sect;2, &sect;6 and &sect;7 remain first-draft prose only I have read &mdash; &sect;6 "
     "proposes the diff format and &sect;7 is the checklist a maintainer would actually follow, "
     "so they carry the most operational weight of what is left."),
]


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(HERE.parent), *args],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def build() -> str:
    md_text = SRC.read_text(encoding="utf-8")
    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
    )

    # The template supplies the page title, so drop the document's own <h1>
    # rather than rendering two competing titles.
    body = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", body, count=1, flags=re.S)

    # Tag each <h2> so revised sections can be badged, and collect the nav.
    nav: list[tuple[str, str, bool]] = []

    def tag_h2(m: re.Match[str]) -> str:
        inner = m.group(1)
        plain = re.sub(r"<[^>]+>", "", inner)
        num = re.match(r"\s*(\d+)\.", plain)
        key = num.group(1) if num else ""
        revised = key in REVISED
        anchor = "sec-" + (key or re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-"))
        nav.append((anchor, plain, revised))
        badge = ' <span class="badge rev">revised</span>' if revised else \
                ' <span class="badge orig">first draft</span>'
        return f'<h2 id="{anchor}" class="{"revised" if revised else ""}">{inner}{badge}</h2>'

    # The `toc` extension already stamps an id, so match <h2 ...> not just <h2>.
    body = re.sub(r"<h2[^>]*>(.*?)</h2>", tag_h2, body, flags=re.S)

    # Wrap tables so wide ones scroll inside their own container.
    body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")

    nav_html = "\n".join(
        f'<li><a href="#{a}">{html.escape(t)}</a>'
        f'{"<span class=\"dot\"></span>" if r else ""}</li>'
        for a, t, r in nav
    )
    q_html = "\n".join(
        f'<li><h3>{t}</h3><p>{d}</p></li>' for t, d in OPEN_QUESTIONS
    )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    head = git("rev-parse", "--short", "HEAD")
    lines = len(md_text.splitlines())

    return TEMPLATE.format(
        body=body, nav=nav_html, questions=q_html,
        stamp=stamp, head=head, lines=lines,
    )


TEMPLATE = """<title>FOLIO change policy — draft</title>
<style>
:root {{
  --ink:#161a1d; --soft:#4c565e; --faint:#79858e;
  --paper:#fbfaf8; --panel:#ffffff; --rule:#e2e0da;
  --accent:#1f4d6b; --accent-dim:#e2ecf2;
  --flag:#8a2f22; --flag-dim:#f7e7e3;
  --ok:#2c6146;
  --serif:"Iowan Old Style","Palatino Linotype","Book Antiqua",Palatino,"Hoefler Text",Georgia,serif;
  --sans:Optima,Candara,"Gill Sans","Gill Sans MT","Trebuchet MS",ui-sans-serif,sans-serif;
  --mono:ui-monospace,"SF Mono","JetBrains Mono","IBM Plex Mono",Menlo,Consolas,monospace;
}}
@media (prefers-color-scheme:dark) {{
  :root {{
    --ink:#e8e6e1; --soft:#a9b2b9; --faint:#7d878e;
    --paper:#101416; --panel:#171c1f; --rule:#2a3236;
    --accent:#6fb3d4; --accent-dim:#14313f;
    --flag:#e08e7c; --flag-dim:#3a201b; --ok:#68b58e;
  }}
}}
:root[data-theme="dark"] {{
  --ink:#e8e6e1; --soft:#a9b2b9; --faint:#7d878e;
  --paper:#101416; --panel:#171c1f; --rule:#2a3236;
  --accent:#6fb3d4; --accent-dim:#14313f;
  --flag:#e08e7c; --flag-dim:#3a201b; --ok:#68b58e;
}}
:root[data-theme="light"] {{
  --ink:#161a1d; --soft:#4c565e; --faint:#79858e;
  --paper:#fbfaf8; --panel:#ffffff; --rule:#e2e0da;
  --accent:#1f4d6b; --accent-dim:#e2ecf2;
  --flag:#8a2f22; --flag-dim:#f7e7e3; --ok:#2c6146;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--serif);
  font-size:18px;line-height:1.62;-webkit-text-size-adjust:100%}}
.wrap{{max-width:47rem;margin:0 auto;padding:2rem 1.15rem 5rem}}
@media (max-width:640px){{body{{font-size:17px}}.wrap{{padding:1.5rem .95rem 4rem}}}}

.status{{border:1px solid var(--flag);background:var(--flag-dim);color:var(--flag);
  border-radius:7px;padding:.7rem .9rem;font-family:var(--sans);font-size:.86rem;
  font-weight:600;margin-bottom:1.5rem}}
.status span{{display:block;font-weight:400;color:var(--soft);margin-top:.2rem}}
h1{{font-size:clamp(1.7rem,5vw,2.4rem);line-height:1.15;margin:0 0 .5rem;
  letter-spacing:-.01em;text-wrap:balance}}
.meta{{font-family:var(--mono);font-size:.7rem;letter-spacing:.06em;color:var(--faint);
  margin:0 0 2rem;text-transform:uppercase}}

nav{{border:1px solid var(--rule);background:var(--panel);border-radius:8px;
  padding:.9rem 1.1rem;margin-bottom:2.5rem}}
nav p{{font-family:var(--mono);font-size:.66rem;letter-spacing:.12em;text-transform:uppercase;
  color:var(--faint);margin:0 0 .5rem}}
nav ul{{list-style:none;margin:0;padding:0;font-family:var(--sans);font-size:.93rem}}
nav li{{padding:.16rem 0}}
nav a{{color:var(--accent);text-decoration:none}}
nav a:hover{{text-decoration:underline}}
.dot{{display:inline-block;width:.42rem;height:.42rem;border-radius:50%;
  background:var(--accent);margin-left:.4rem;vertical-align:middle}}

h2{{font-size:1.5rem;line-height:1.2;margin:2.8rem 0 .6rem;letter-spacing:-.005em;
  padding-top:1.3rem;border-top:1px solid var(--rule);text-wrap:balance}}
h2:first-of-type{{border-top:none;padding-top:0}}
h3{{font-family:var(--sans);font-size:1.02rem;font-weight:600;margin:1.8rem 0 .4rem}}
p{{margin:0 0 1rem}}
blockquote{{margin:1.1rem 0;padding:.15rem 0 .15rem 1rem;border-left:3px solid var(--accent);
  color:var(--soft)}}
blockquote p{{margin:.3rem 0}}
ul,ol{{margin:0 0 1rem;padding-left:1.3rem}}
li{{margin:.3rem 0}}
strong{{font-weight:700}}
code{{font-family:var(--mono);font-size:.83em;background:var(--accent-dim);
  padding:.08em .32em;border-radius:3px;word-break:break-word}}
pre{{background:var(--panel);border:1px solid var(--rule);border-radius:7px;
  padding:.85rem 1rem;overflow-x:auto;margin:1.1rem 0}}
pre code{{background:none;padding:0;font-size:.78rem;line-height:1.5}}

.badge{{font-family:var(--mono);font-size:.56rem;letter-spacing:.11em;text-transform:uppercase;
  padding:.14rem .38rem;border-radius:3px;vertical-align:middle;white-space:nowrap;
  font-weight:400}}
.badge.rev{{background:var(--accent);color:var(--paper)}}
.badge.orig{{border:1px solid var(--rule);color:var(--faint)}}

.tw{{overflow-x:auto;margin:1.2rem 0;border:1px solid var(--rule);border-radius:7px;
  background:var(--panel)}}
table{{border-collapse:collapse;width:100%;min-width:30rem;font-family:var(--sans);
  font-size:.87rem}}
th,td{{padding:.5rem .75rem;text-align:left;border-bottom:1px solid var(--rule);
  vertical-align:top}}
thead th{{font-family:var(--mono);font-size:.63rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--faint);font-weight:400}}
tbody tr:last-child td{{border-bottom:none}}

.questions{{border:1px solid var(--accent);border-radius:8px;background:var(--accent-dim);
  padding:1.2rem;margin:3rem 0 0}}
.questions > p:first-child{{font-family:var(--mono);font-size:.66rem;letter-spacing:.12em;
  text-transform:uppercase;color:var(--accent);margin:0 0 .6rem}}
.questions ul{{list-style:none;margin:0;padding:0}}
.questions li{{margin:0 0 1.1rem}}
.questions li:last-child{{margin-bottom:0}}
.questions h3{{margin:0 0 .2rem;font-size:.97rem}}
.questions p{{margin:0;font-size:.93rem;color:var(--soft)}}
hr{{border:none;border-top:1px solid var(--rule);margin:2rem 0}}
a{{color:var(--accent)}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style>

<div class="wrap">
  <div class="status">DRAFT — NOT FOR RELEASE
    <span>Unpushed, local branch only. Under active revision with Damien; nothing here is
    published or binding, and no ontology file has been modified.</span>
  </div>

  <h1>FOLIO change policy</h1>
  <p class="meta">generated {stamp} · from FOLIO-CHANGE-POLICY.md · {lines} lines · repo {head}</p>

  <nav>
    <p>Contents — dot marks a section revised this round</p>
    <ul>{nav}</ul>
  </nav>

  {body}

  <div class="questions">
    <p>Open — waiting on you</p>
    <ul>{questions}</ul>
  </div>
</div>
"""


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
