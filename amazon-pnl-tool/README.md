# Amazon P&L Explorer

A single-file dashboard that turns an Amazon **Unified Transaction** payment report into a
clear, month-on-month P&L — fees, returns, per-SKU profitability, and COGS — for US and India
accounts. Everything runs locally in the browser; no report data leaves the user's computer.

Current version: **v1.2**

## What's in this folder
- `index.html` — the dashboard. This is the whole tool (self-contained, works offline).
- `Deploy_Internal_URL_Guide.md` — how to host it at one internal URL for the team.
- `README.md` — this file.

## How to use it
1. Open `index.html` in a browser (Chrome/Edge/Safari), or visit the hosted URL.
2. Click **+ Upload report (Excel / CSV)** and choose an Amazon Unified Transaction report
   (Seller Central → Payments → Reports Repository → Unified Transaction).
   - You can stack many months in one Excel workbook — the tool splits them automatically.
3. Explore the tabs: **Overview**, **Fee & Returns Explorer**, **Products**,
   **Profitability (COGS)**, **Month-on-Month**.
4. Type a COGS % (blended or per-SKU) on the Profitability tab to see true margin.
5. Click **⬇ Download Excel** for a styled, client-ready workbook of the selected month.

## Marketplaces
Auto-detects the account and currency: **amazon.com ($)** and **amazon.in (₹)** are supported,
with basic handling for other marketplaces. The brand name in the header is auto-detected from
the product titles.

## Where the data lives
Each person's uploads are saved only in their own browser (local storage) — private to that
machine, not shared. The per-brand Excel report remains the source of truth: re-upload the
updated file to refresh, or upload just the new month's CSV to add it.

To make data **shared and permanent across the team and devices** (upload only the new month per
brand, stored centrally), the tool can be connected to a Supabase backend — ask the person who
built this for the integration steps.

## Hosting
It's a static file, so any web host works — Netlify, your own domain/server, an intranet.
Must be served over **HTTPS**. See `Deploy_Internal_URL_Guide.md` for step-by-step options.

## Notes
- Figures are **payout-level** (what Amazon settles), organised by posted/settlement date —
  not order date — so they won't tie exactly to Business Reports "ordered sales".
- India figures include GST inside the payout; a GST-adjusted view is a possible future add.
- To update the tool, replace `index.html` at your host. The version number in the header
  confirms which build everyone is on.
