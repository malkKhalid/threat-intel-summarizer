"""Render daily bulletins as Markdown and HTML."""

from __future__ import annotations

import html
import json
from datetime import timezone
from pathlib import Path

from .iocs import ioc_summary
from .models import Bulletin


def _urgency_badge(score: int) -> str:
    if score >= 85:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    return "LOW"


def build_markdown(bulletin: Bulletin) -> str:
    ts = bulletin.generated_at.astimezone(timezone.utc)
    lines = [
        f"# {bulletin.title}",
        "",
        f"_Generated: {ts:%Y-%m-%d %H:%M UTC} • "
        f"{len(bulletin.articles)} articles • {len(bulletin.alerts)} alerts_",
        "",
    ]

    if bulletin.alerts:
        lines += ["## 🚨 Alerts", ""]
        for a in bulletin.alerts:
            lines.append(
                f"- **[{a.urgency_score}] {a.trend}** — {a.title} "
                f"({a.source}) — [{a.reason}] — <{a.link}>"
            )
        lines.append("")

    lines += ["## 📰 Key Bulletins", ""]
    ordered = sorted(bulletin.articles, key=lambda t: t[1].urgency_score, reverse=True)
    for article, e in ordered:
        lines.append(f"### [{e.urgency_score}] {article.title}")
        lines.append(f"*Source:* {article.source} • *Trend:* {e.trend} "
                     f"({e.trend_confidence:.0%}) • *Sentiment:* {e.sentiment} • "
                     f"*Risk:* {_urgency_badge(e.urgency_score)}")
        for bullet in e.bulletin:
            lines.append(f"- {bullet}")
        if e.iocs:
            lines.append(f"- **IOCs:** {ioc_summary(e.iocs)}")
            for kind, values in sorted(e.iocs.items()):
                lines.append(f"  - `{kind}`: {', '.join(f'`{v}`' for v in values[:10])}")
        lines.append(f"- [Read more]({article.link})")
        lines.append("")

    return "\n".join(lines)


def build_html(bulletin: Bulletin) -> str:
    ts = bulletin.generated_at.astimezone(timezone.utc)
    rows: list[str] = []

    alert_html = ""
    if bulletin.alerts:
        items = "".join(
            f'<li><span class="score">{a.urgency_score}</span> '
            f"<strong>{html.escape(a.trend)}</strong> — "
            f'<a href="{html.escape(a.link)}">{html.escape(a.title)}</a> '
            f"<em>({html.escape(a.source)})</em></li>"
            for a in bulletin.alerts
        )
        alert_html = f'<section class="alerts"><h2>🚨 Alerts</h2><ul>{items}</ul></section>'

    for article, e in sorted(bulletin.articles, key=lambda t: t[1].urgency_score, reverse=True):
        bullets = "".join(f"<li>{html.escape(b)}</li>" for b in e.bulletin)
        ioc_html = ""
        if e.iocs:
            ioc_items = "".join(
                f"<li><code>{html.escape(kind)}</code>: "
                + ", ".join(f"<code>{html.escape(v)}</code>" for v in values[:10])
                + "</li>"
                for kind, values in sorted(e.iocs.items())
            )
            ioc_html = f'<div class="iocs"><strong>IOCs:</strong><ul>{ioc_items}</ul></div>'
        risk = _urgency_badge(e.urgency_score)
        rows.append(
            f'<article class="card risk-{risk.lower()}">'
            f'<header><span class="badge {risk.lower()}">{risk} {e.urgency_score}</span>'
            f"<h3>{html.escape(article.title)}</h3></header>"
            f'<p class="meta">{html.escape(article.source)} • trend: '
            f"{html.escape(e.trend)} ({e.trend_confidence:.0%}) • sentiment: "
            f"{html.escape(e.sentiment)}</p>"
            f"<ul>{bullets}</ul>{ioc_html}"
            f'<p><a href="{html.escape(article.link)}">Read more →</a></p>'
            f"</article>"
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(bulletin.title)}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1c1e21;background:#f5f6f8}}
 h1{{margin-bottom:.2rem}} .meta{{color:#65676b;font-size:.85rem}}
 .card{{background:#fff;border-radius:12px;padding:1rem 1.25rem;margin:1rem 0;box-shadow:0 1px 3px rgba(0,0,0,.12);border-left:5px solid #888}}
 .card.risk-critical{{border-color:#b00020}} .card.risk-high{{border-color:#e8590c}}
 .card.risk-medium{{border-color:#f0a020}} .card.risk-low{{border-color:#2f9e44}}
 .badge{{font-size:.7rem;font-weight:700;padding:.15rem .5rem;border-radius:999px;color:#fff;background:#888}}
 .badge.critical{{background:#b00020}} .badge.high{{background:#e8590c}}
 .badge.medium{{background:#f0a020}} .badge.low{{background:#2f9e44}}
 .alerts{{background:#fff3f3;border:1px solid #f5c2c7;border-radius:12px;padding:1rem 1.5rem}}
 .score{{font-weight:700;color:#b00020}}
 code{{background:#eef0f3;padding:.05rem .3rem;border-radius:4px;font-size:.85rem}}
 a{{color:#0b6bcb}}
</style></head>
<body>
<h1>{html.escape(bulletin.title)}</h1>
<p class="meta">Generated {ts:%Y-%m-%d %H:%M UTC} • {len(bulletin.articles)} articles • {len(bulletin.alerts)} alerts</p>
{alert_html}
<section><h2>📰 Key Bulletins</h2>{''.join(rows)}</section>
</body></html>"""


def bulletin_to_dict(bulletin: Bulletin) -> dict:
    """Serialisable representation, also consumed by the web dashboard."""
    return {
        "title": bulletin.title,
        "generated_at": bulletin.generated_at.astimezone(timezone.utc).isoformat(),
        "articles": [
            {
                "title": a.title,
                "link": a.link,
                "source": a.source,
                "published": a.published.astimezone(timezone.utc).isoformat(),
                "bulletin": e.bulletin,
                "trend": e.trend,
                "trend_confidence": e.trend_confidence,
                "urgency_score": e.urgency_score,
                "sentiment": e.sentiment,
                "iocs": e.iocs,
                "risk": _urgency_badge(e.urgency_score),
            }
            for a, e in bulletin.articles
        ],
        "alerts": [
            {
                "title": x.title,
                "link": x.link,
                "source": x.source,
                "trend": x.trend,
                "urgency_score": x.urgency_score,
                "reason": x.reason,
                "channels": x.channels,
            }
            for x in bulletin.alerts
        ],
    }


def write_report_files(bulletin: Bulletin, output_dir: str | Path) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    date_str = bulletin.generated_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    paths = {
        "markdown": out / f"bulletin-{date_str}.md",
        "html": out / f"bulletin-{date_str}.html",
        "json": out / f"bulletin-{date_str}.json",
        "latest_html": out / "index.html",
        "latest_json": out / "latest.json",
    }
    md = build_markdown(bulletin)
    html_doc = build_html(bulletin)
    data = json.dumps(bulletin_to_dict(bulletin), indent=2)
    paths["markdown"].write_text(md, encoding="utf-8")
    paths["html"].write_text(html_doc, encoding="utf-8")
    paths["json"].write_text(data, encoding="utf-8")
    paths["latest_html"].write_text(html_doc, encoding="utf-8")
    paths["latest_json"].write_text(data, encoding="utf-8")
    return paths
