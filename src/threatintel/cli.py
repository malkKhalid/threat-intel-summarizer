"""Command line interface: `threatintel <command>`."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import get_settings
from .pipeline import Pipeline
from .report import build_markdown, write_report_files
from .scraper import load_feeds


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_run(args: argparse.Namespace) -> int:
    pipeline = Pipeline()
    bulletin, summary = pipeline.run(dry_run=args.dry_run, write_report=not args.no_report)
    print(summary.as_text())
    if summary.report_paths:
        for kind, path in summary.report_paths.items():
            print(f"  {kind:12s} {path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    settings = get_settings()
    pipeline = Pipeline()
    articles = pipeline.storage.recent_articles(limit=args.limit)
    from datetime import datetime, timezone

    from .models import Bulletin

    bulletin = Bulletin(generated_at=datetime.now(timezone.utc))
    for article in articles:
        enrichment = pipeline.storage.get_enrichment(article.article_hash)
        if enrichment:
            bulletin.articles.append((article, enrichment))
    bulletin.alerts = pipeline.storage.recent_alerts(limit=args.limit)

    if args.stdout:
        print(build_markdown(bulletin))
    else:
        paths = write_report_files(bulletin, settings.report_output_dir)
        for kind, path in paths.items():
            print(f"{kind:12s} {path}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .web.app import create_app

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def cmd_feeds(_: argparse.Namespace) -> int:
    feeds = load_feeds()
    print(f"{len(feeds)} configured feeds:")
    for feed in feeds:
        tags = ",".join(feed.tags)
        print(f"  - {feed.name:28s} [{tags}] {feed.url}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="threatintel", description="Threat Intel Summarizer & Alerts")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="scrape, analyze, alert and build today's report")
    p_run.add_argument("--dry-run", action="store_true", help="do not send notifications")
    p_run.add_argument("--no-report", action="store_true", help="skip report file generation")
    p_run.set_defaults(func=cmd_run)

    p_rep = sub.add_parser("report", help="rebuild a report from stored data")
    p_rep.add_argument("--limit", type=int, default=100)
    p_rep.add_argument("--stdout", action="store_true", help="print markdown instead of writing files")
    p_rep.set_defaults(func=cmd_report)

    p_serve = sub.add_parser("serve", help="run the Flask dashboard")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=5000)
    p_serve.add_argument("--debug", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_feeds = sub.add_parser("feeds", help="list configured feeds")
    p_feeds.set_defaults(func=cmd_feeds)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
