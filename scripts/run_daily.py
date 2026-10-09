"""Entrypoint for schedulers (cPanel cron, Windows Task Scheduler, CI).

Usage:  python scripts/run_daily.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from threatintel.cli import main  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(main(["run", *(["--dry-run"] if args.dry_run else [])]))
