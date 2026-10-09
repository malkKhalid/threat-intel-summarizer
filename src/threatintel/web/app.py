"""Flask dashboard for browsing bulletins, alerts and previewing reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

from ..config import get_settings
from ..filters import FilterRule, load_filter_rules
from ..models import Alert, Article, Bulletin, Enrichment
from ..storage import Storage


def _industries_for(rule_list: list[FilterRule], text: str) -> list[str]:
    found: set[str] = set()
    low = text.lower()
    for rule in rule_list:
        if any(kw in low for kw in rule.keywords):
            found.update(i for i in rule.industries if i != "all")
    return sorted(found) or ["general"]


def create_app(settings=None) -> Flask:
    settings = settings or get_settings()
    app = Flask(__name__, template_folder="templates")
    app.secret_key = settings.flask_secret_key
    storage = Storage(settings.database_path)

    def _load_bulletin() -> Bulletin:
        """Prefer the freshest generated JSON, fall back to the database."""
        latest = settings.report_output_dir / "latest.json"
        if latest.exists():
            data = json.loads(latest.read_text(encoding="utf-8"))
            bulletin = Bulletin(
                generated_at=datetime.fromisoformat(data["generated_at"]),
                title=data.get("title", "Daily Threat Intelligence Bulletin"),
            )
            for item in data.get("articles", []):
                article = Article(
                    title=item["title"],
                    link=item["link"],
                    source=item["source"],
                    published=datetime.fromisoformat(item["published"]),
                )
                enrichment = Enrichment(
                    article_hash=article.article_hash,
                    bulletin=item["bulletin"],
                    trend=item["trend"],
                    trend_confidence=item["trend_confidence"],
                    urgency_score=item["urgency_score"],
                    sentiment=item["sentiment"],
                    iocs=item["iocs"],
                )
                bulletin.articles.append((article, enrichment))
            for item in data.get("alerts", []):
                bulletin.alerts.append(
                    Alert(
                        article_hash="",
                        title=item["title"],
                        link=item["link"],
                        source=item["source"],
                        urgency_score=item["urgency_score"],
                        trend=item["trend"],
                        trend_confidence=0.0,
                        reason=item.get("reason", ""),
                        channels=item.get("channels", []),
                    )
                )
            return bulletin

        bulletin = Bulletin(generated_at=datetime.now(timezone.utc))
        for article, enrichment in storage.iter_enriched(limit=200):
            bulletin.articles.append((article, enrichment))
        bulletin.alerts = storage.recent_alerts(limit=100)
        return bulletin

    @app.route("/")
    def index() -> str:
        _, rules = load_filter_rules()
        bulletin = _load_bulletin()

        min_urgency = request.args.get("min_urgency", type=int, default=0)
        trend = (request.args.get("trend") or "").strip().lower()
        industry = (request.args.get("industry") or "").strip().lower()
        query = (request.args.get("q") or "").strip().lower()

        rows = []
        all_trends: set[str] = set()
        all_industries: set[str] = set()
        for article, enrichment in bulletin.articles:
            text = f"{article.title} {article.text}"
            inds = _industries_for(rules, text)
            all_trends.add(enrichment.trend)
            all_industries.update(inds)
            if enrichment.urgency_score < min_urgency:
                continue
            if trend and enrichment.trend.lower() != trend:
                continue
            if industry and industry not in inds:
                continue
            if query and query not in text.lower():
                continue
            rows.append(
                {
                    "article": article,
                    "e": enrichment,
                    "industries": inds,
                }
            )
        rows.sort(key=lambda r: r["e"].urgency_score, reverse=True)

        return render_template(
            "index.html",
            title=bulletin.title,
            generated_at=bulletin.generated_at,
            rows=rows,
            alerts=bulletin.alerts,
            all_trends=sorted(t for t in all_trends if t and t != "unknown"),
            all_industries=sorted(all_industries),
            total=len(bulletin.articles),
            filters={
                "min_urgency": min_urgency,
                "trend": trend,
                "industry": industry,
                "q": query,
            },
        )

    @app.route("/alerts")
    def alerts() -> str:
        return render_template(
            "alerts.html",
            title="Alert History",
            alerts=storage.recent_alerts(limit=200),
        )

    @app.route("/reports/<path:filename>")
    def reports(filename: str):
        directory = settings.report_output_dir
        target = (directory / filename).resolve()
        if not str(target).startswith(str(directory.resolve())) or not target.exists():
            abort(404)
        return send_from_directory(directory, filename)

    @app.route("/api/bulletin")
    def api_bulletin():
        bulletin = _load_bulletin()
        return jsonify(
            {
                "generated_at": bulletin.generated_at.isoformat(),
                "articles": len(bulletin.articles),
                "alerts": len(bulletin.alerts),
            }
        )

    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "articles": storage.count_articles(),
                "sources": storage.distinct_sources(),
            }
        )

    return app
