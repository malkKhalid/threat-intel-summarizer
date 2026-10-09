# LLM-Based Threat Intelligence Summarizer and Alert System

Scrape 20+ threat-intel RSS feeds → summarize with an LLM → detect emerging
trends (zero-days, ransomware, APT…) → score urgency via sentiment → send
filtered alerts (Email / Slack / SMS) → publish a daily bulletin + web
dashboard.

```
Local dev ──git push──▶ GitHub ── GitHub Actions ──▶ Namecheap (cPanel)
                            │  (CI tests + daily pipeline)      │
                            └─────────────────────────────▶ Daily report + site
```

## Features

| Area | What it does |
|------|--------------|
| **Scraping** | `feedparser` over a YAML feed catalogue (AlienVault, CISA, Talos, The Hacker News, …), SQLite caching + de-dup. |
| **Summarization** | Provider abstraction. `huggingface` (local models) or dependency-free `extractive` fallback. |
| **Trend detection** | Zero-shot / few-shot classification into user-defined trend labels. |
| **Urgency** | Sentiment + keyword-weighted score (0–100) with trend severity baselines. |
| **IOCs** | CVE, IPv4, domain, URL, MD5/SHA1/SHA256, email extraction. |
| **Filters** | Industry-specific rules (finance, healthcare, energy/ICS, government, zero-day watch) in `config/filters.yaml`. |
| **Alerting** | SMTP email, Slack webhook, optional Twilio SMS (≥85 urgency only). |
| **Storage** | SQLite (`data/threatintel.db`) for articles, enrichments and alert history. |
| **Dashboard** | Flask app: bulletins, alert history, trend/industry/urgency filters. |
| **Automation** | GitHub Actions CI + scheduled daily pipeline that deploys reports to Namecheap. |

## Quickstart

```bash
# 1. Clone and create a virtual environment
git clone https://github.com/<you>/threat-intel-summarizer.git
cd threat-intel-summarizer
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux

# 2. Install (dev extras for tests/lint)
pip install -e ".[dev]"

# 3. Configure
copy .env.example .env            # then edit .env

# 4. Run the pipeline (dry-run = no notifications sent)
threatintel run --dry-run

# 5. Preview the dashboard
threatintel serve --port 5000     # http://127.0.0.1:5000
```

### Using local Hugging Face models

```bash
pip install -e ".[hf]"            # installs transformers + torch
# .env:  LLM_PROVIDER=huggingface
```

Default models: `sshleifer/distilbart-cnn-12-6` (summary) and
`facebook/bart-large-mnli` (zero-shot trend detection). On machines without a
GPU the pipeline still runs on CPU; use `extractive` for a fast, offline mode.

## CLI

| Command | Description |
|---------|-------------|
| `threatintel run [--dry-run] [--no-report]` | Full pipeline (scrape → analyze → alert → report). |
| `threatintel report [--stdout] [--limit N]` | Rebuild a report from stored data. |
| `threatintel serve [--host] [--port] [--debug]` | Run the Flask dashboard. |
| `threatintel feeds` | List the configured feed catalogue. |

## Project layout

```
config/            feeds.yaml, filters.yaml
src/threatintel/   scraper/, llm/, alerts/, web/, pipeline.py, cli.py …
tests/             pytest unit tests (no network required)
.github/workflows/ ci.yml, daily.yml
passenger_wsgi.py  WSGI entrypoint for cPanel Passenger
scripts/           run_daily.py scheduler wrapper
data/              SQLite db + generated reports (gitignored)
```

## CI/CD: Local → GitHub → Namecheap

### 1. Push code to GitHub

```bash
git init
git add .
git commit -m "chore: initial commit"
git branch -M main
git remote add origin https://github.com/<you>/threat-intel-summarizer.git
git push -u origin main
```

Every push runs **CI** (`ci.yml`): ruff + pytest on Python 3.10–3.12.

### 2. Add repository secrets

`Settings → Secrets and variables → Actions → New repository secret`:

| Secret | Purpose |
|--------|---------|
| `FTP_SERVER` | Namecheap server host (e.g. `server123.web-hosting.com`) |
| `FTP_USERNAME` | cPanel/FTP username |
| `FTP_PASSWORD` | cPanel/FTP password |
| `FTP_PORT` | `21` (FTP) or `22` (SFTP) |
| `FTP_SERVER_DIR` | Target folder, e.g. `/public_html/threatintel/` |
| `SMTP_ENABLED`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO` | Email alerts |
| `SLACK_ENABLED`, `SLACK_WEBHOOK_URL` | Slack alerts |
| `TWILIO_*` | Optional SMS alerts |

### 3. Namecheap (cPanel) setup

**A. Static report hosting (works everywhere):**
1. In cPanel create the folder `public_html/threatintel/`.
2. Grab the FTP host/user/password from *Files → FTP Accounts*.
3. The daily workflow uploads `data/reports/` there → preview at
   `https://yourdomain.com/threatintel/`.

**B. Interactive Flask dashboard (optional, needs Passenger):**
1. cPanel → *Setup Python App* → create an app, point the *Application root* at
   your project directory and *Application startup file* at `passenger_wsgi.py`.
2. Install requirements inside the app's virtualenv, then restart the app.

### 4. Daily automation

`daily.yml` runs at **06:00 UTC** (and on demand) and will:
1. Install deps and run the pipeline with the Hugging Face provider.
2. Send alerts based on your filters.
3. Upload the report as a build artifact.
4. Deploy the reports to Namecheap over FTP.

Trigger a manual run from *Actions → Daily Threat Intel Pipeline → Run workflow*.

## Configuration

- **Feeds:** `config/feeds.yaml` — add/remove sources, tag them for filtering.
- **Filters:** `config/filters.yaml` — keywords, trend labels, feed tags,
  minimum urgency and `require_iocs` per rule.
- **Runtime knobs:** `.env` (`FRESHNESS_HOURS`, `MAX_ARTICLES_PER_FEED`,
  `URGENCY_ALERT_THRESHOLD`, provider and alert credentials).

## Testing

```bash
pytest            # unit tests
ruff check src tests
```

## Evaluating accuracy

Run the pipeline against a week of feeds (`FRESHNESS_HOURS=168`), export
`alert` rows and compare the LLM `trend` classification against a hand-labelled
set to compute precision/recall. The `Enrichment.enriched_by` field records
which provider produced each result.

---

### دليل سريع (عربي)

1. `pip install -e ".[dev]"` ثم انسخ `.env.example` إلى `.env`.
2. لتشغيل الموديل المحلي: `pip install -e ".[hf]"` واضبط `LLM_PROVIDER=huggingface`.
3. جرّب محلياً: `threatintel run --dry-run` ثم `threatintel serve`.
4. ارفع على GitHub ثم أضف الأسرار (Secrets) أعلاه.
5. Workflow اليومي يبني التقرير ويرفعه تلقائياً إلى Namecheap عبر FTP، وتشاهد
   المعاينة على `https://yourdomain.com/threatintel/`.

## License

MIT — see [LICENSE](LICENSE).
