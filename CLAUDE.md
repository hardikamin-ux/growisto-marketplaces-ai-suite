# Growisto Marketplaces AI Suite — Handoff Document

## What this project is

An internal hub of AI-powered Amazon marketplace tools for the Growisto team. It's a static website hosted on Render with a custom domain. Teammates access it via a shared link — no installation needed on their end.

**Live site:** Deployed on Render → Custom domain → Accessible to all teammates  
**GitHub repo:** `hardikamin-ux/growisto-marketplaces-ai-suite`  
**Deployment:** Render watches the GitHub repo and auto-deploys on every push to `main`

---

## The 7 Tools

| Tool | Type | What it does |
|------|------|--------------|
| Search Term Harvest & Negate | Live (React/Vite) | Upload Sponsored Ads report → pivot by search term → harvest/negate + Keepa ASIN lookup |
| ASIN Performance Analyser | Live (React/Vite) | Blend SP + SD reports with Total Sales → group by custom labels → dynamic pivot table |
| Amazon Listing Generator | Claude Plugin | 9-step workflow → titles, bullets, descriptions, backend terms → Excel export |
| BSR Scrapper | Live (Python desktop app) | Scrape Best Seller Rankings across multiple Amazon geographies in bulk |
| Amazon Review Scrapper | Live (Python desktop app) | Scrape all reviews + ratings from Amazon India → desktop app |
| Amazon Review Sentiment Analysis | Claude Plugin | AI-tag reviews → 4-sheet Excel: KPIs, problems, rating trends, feature matrix |
| FBA Fees Calculator | Live (HTML/JS) | Calculate FBA fees for US + India → size tier auto-assign → fee reduction tips |

---

## Project Structure

```
growisto-marketplaces-ai-suite/
├── index.html                          ← Main suite homepage (entry gate + tool cards)
├── render.yaml                         ← Render deployment config (static site)
├── .claude/
│   └── launch.json                     ← Local dev server config (python3, port 4500)
├── assets/                             ← Growisto logo + icon
├── amazon-listing-generator/           ← Claude Plugin how-to page
├── amazon-review-scrapper/             ← Python desktop app + installer scripts
├── amazon-review-sentiment-analysis/   ← Claude Plugin how-to page
├── asin-performance-analyser/          ← Pre-built React/Vite app (built assets)
├── bsr-scrapper/                       ← Python desktop app + installer scripts
├── fba-fees-calculator/                ← Pure HTML/JS tool
└── search-term-harvest-and-negate-tool/ ← Pre-built React/Vite app (built assets)
```

---

## Running Locally

```bash
cd growisto-marketplaces-ai-suite
python3 -m http.server 4500
```

Then open `http://localhost:4500` in your browser.

**Why python3?** The suite is static HTML — a local server is needed so internal links between pages work correctly. Direct file:// opening breaks navigation.

> ⚠️ The `.claude/launch.json` uses `python3` — correct for Mac. If you ever work on Windows, change it to `python`. Change it back when returning to Mac.

---

## Deployment

- **Platform:** Render (static site)
- **Config:** `render.yaml` in root
- **Trigger:** Every push to `main` branch auto-deploys
- **Cache:** `Cache-Control: no-cache` set on all routes so users always get the latest version
- **No build step** — it's a static site, Render just serves the files directly

**To deploy a change:** commit and push to `main` → Render picks it up automatically.

---

## Usage Tracking

Tracking is fully wired up and **live**. Every time a teammate opens the suite or clicks a tool, it logs to a Google Sheet.

**How it works:**
1. Entry gate asks for **Name** + **Project** before entering
2. On entry, fires `Session Started` event to Google Apps Script webhook
3. While active: **Heartbeat** every 60 seconds
4. On inactivity (10 min): logs `Idle`
5. On return: logs `Resumed`
6. On tool click: logs `Tool Clicked` with tool name
7. On close: logs `Closed`

**Tracking webhook URL** (in `index.html` and all tool pages):
```
https://script.google.com/macros/s/AKfycbxf8LQkBGNWOZ7eVYoOvKpcejcbii-ULFaTEsnviP-s4CPxjIFmo7jmXjiTl5JgOLbz/exec
```

**Google Sheet:** Find it in your Google Drive — created when the Apps Script was set up. Search for the sheet linked to this Apps Script at script.google.com.

> ⚠️ Important: The last commit (`cda9fd5`) fixed a bug where the tracking guard condition was always returning early, silently blocking all events. Tracking is now working correctly.

---

## Entry Gate

The suite has a login gate at `index.html` — users must select their **Name** and **Project** before accessing tools. This data is stored in `sessionStorage` and attached to all tracking events.

The name and project lists are hardcoded in `index.html` — update them there if team members or projects change.

---

## The React Tools (ASIN Analyser + Search Term Tool)

These two tools are **pre-built** — the compiled assets are already in the repo:
- `asin-performance-analyser/assets/`
- `search-term-harvest-and-negate-tool/assets/`

**To use them:** They just work — no build needed, they're served as static files.

**To modify them:** You'll need Node.js installed and the original source code. The source is NOT in this repo — only the built output is committed. Contact the original developer if source is needed.

---

## Desktop App Tools (BSR Scrapper + Review Scrapper)

These run as local Python desktop apps on the user's machine:
- `bsr-scrapper/install_mac.sh` — Mac installer
- `bsr-scrapper/install_windows.bat` — Windows installer
- `amazon-review-scrapper/install-mac.command` — Mac installer
- `amazon-review-scrapper/install-windows.bat` — Windows installer

Teammates download and run the installer once, then use the local app.

---

## Claude Plugins Created from This Project

Two skills built from this project were packaged as Claude plugins and submitted to the org plugin registry (`nishantpandey-growisto/claude-plugins`):

| Plugin | Folder Name | PR |
|--------|-------------|-----|
| Amazon Audit (Without Access) | `amazon-audit-without-access` | PR #36 |
| Amazon Audit (With Access) - L1 | `amazon-audit-with-access-l1` | PR #37 |

Both PRs were merged — plugins are live and auto-distributed to all 29 org members.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | HTML, CSS, JavaScript (vanilla) |
| React tools | React + Vite (pre-built, source not in repo) |
| Desktop apps | Python (Flask + Selenium) |
| Hosting | Render (static site) |
| Deployment | GitHub → Render auto-deploy |
| Tracking | Google Apps Script webhook → Google Sheet |
| Local dev | Python HTTP server (port 4500) |

---

## What NOT to Change

- `render.yaml` — leave as-is, it's what makes the live site work
- The tracking webhook URL — changing it will break all usage logging
- The pre-built React assets (`assets/` folders) — don't delete or modify these manually
- `Cache-Control: no-cache` header in `render.yaml` — needed so teammates always get fresh deploys

---

## Git History Reference

| Commit | What it did |
|--------|-------------|
| `cda9fd5` | Fixed tracking guard condition — was silently blocking all events |
| `eaa6d66` | Switched tracking to image beacon (GET) to fix CORS issues |
| `df17df8` | Switched to sendBeacon with text/plain for CORS |
| `27a67aa` | Added no-cors mode to fetch calls |
| `75d83c9` | Wired tracking URL across all 8 pages |
| `b5ce73e` | Added entry gate, tracking, rebuilt React tools |
