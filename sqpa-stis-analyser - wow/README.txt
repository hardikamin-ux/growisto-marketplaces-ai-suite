========================================
  Growisto — Keyword-Level Organic Tracker
========================================


WHAT IS THIS TOOL?
------------------
The Keyword-Level Organic Tracker is an internal Growisto dashboard that
combines two Amazon data sources — Search Query Performance Analytics (SQPA)
from Brand Analytics and the Search Term Impression Share (STIS) report from
the Ads Console — into a single keyword intelligence view. It shows how your
brand is performing organically (search visibility, click share, purchase
share, ATC) alongside paid ad metrics (spend, sales, ACOS) for every keyword your
customers are searching. Keywords are automatically classified into four
actionable categories — Working, Wasted Spend, Opportunity, and Inefficient —
based on thresholds you set, so your team can immediately see where to
increase investment, where to cut spend, and where untapped growth exists.


========================================
  HOW TO USE THE TOOL
========================================

STEP 1 — SET UP (first time only)
----------------------------------
1. Make sure Python is installed on your machine.
   Download from: https://www.python.org/downloads/
   During install, tick "Add Python to PATH".

2. Open Command Prompt (press Win + R, type cmd, press Enter).

3. Navigate to this folder:
   cd "%USERPROFILE%\Desktop\Organic Tracker"

4. Install the required packages:
   pip install -r requirements.txt


STEP 2 — DOWNLOAD YOUR REPORTS FROM AMAZON
--------------------------------------------
You need two CSV reports. Download these fresh each time you use the tool.

  Report 1: SQPA (monthly)
  → Amazon Seller/Vendor Central
  → Brand Analytics → Search Query Performance
  → Select your brand, choose the month, click Export
  → Save the CSV anywhere on your computer

  Report 2: STIS (your chosen date range)
  → Amazon Ads Console → Reports
  → Search Term Impression Share
  → Set your date range, select "Summary" (not Daily) for cleaner IS data
  → Download as CSV

  TIP: Use "Summary" format for STIS — it gives one clean IS Share
  value per keyword per campaign for the full period, which is more
  accurate than averaging daily rows.


STEP 3 — LAUNCH THE APP
------------------------
1. Open Command Prompt.

2. Navigate to this folder:
   cd "%USERPROFILE%\Desktop\Organic Tracker"

3. Run the app:
   python -m streamlit run app.py

4. Your browser opens automatically at http://localhost:8501
   (If it doesn't, open your browser and go to that address.)


STEP 4 — UPLOAD YOUR REPORTS
------------------------------
1. The app opens with an "Upload Reports" panel at the top.
2. Upload your SQPA CSV on the left.
3. Upload your STIS CSV on the right.
4. The tracker loads automatically — no button to press.


STEP 5 — FILTER BY PORTFOLIO
------------------------------
Use the "Portfolio" filter in the left sidebar to focus on a specific
product line (e.g. Grill Covers, Cushions). All portfolios are selected
by default.


STEP 6 — SET YOUR INSIGHT THRESHOLDS
--------------------------------------
Click the "⚙️ Insight Thresholds" bar above the keyword table to expand it.
Adjust the sliders to define what counts as each keyword status:

  ✅ Working       — Min IS %, Max ACOS %, Min Sales $
                     (keyword is delivering results within target)

  💡 Opportunity   — Min SQV, Max IS %
                     (high search volume but your brand is underrepresented)

  ⚠️ Inefficient   — Min ACOS %, Min Spend $
                     (generating sales but costs are too high)

  💸 Wasted Spend  — Min Spend $
                     (spending money with zero sales to show for it)

The table updates instantly as you move the sliders.


STEP 7 — EXPLORE THE KEYWORD TABS
------------------------------------
The keywords are split into five tabs:

  All Keywords    — every keyword in the dataset
  ✅ Working      — performing well, keep investing
  💸 Wasted Spend — spending with no return, review or pause
  💡 Opportunity  — high search volume, low brand presence, grow here
  ⚠️ Inefficient  — converting but above cost target, optimise bids

Each tab shows the same columns:
  Keyword · Portfolio · SQV · Brand Impr. Share · Brand Click Share ·
  Brand ATC Share · Brand Purch. Share · Spend · Sales · ACOS · Status

Refer to the "📖 Column Guide" bar above the table for definitions.


STEP 8 — DRILL INTO A KEYWORD
--------------------------------
Click any keyword row to see the campaign-level breakdown below the table.
This shows which of your ad campaigns are running on that keyword, along
with Impressions, IS Share, Clicks, CTR, CPC, Spend, Sales, ACOS, CVR,
and Orders for each campaign.

  NOTE ON IS SHARE IN THE CAMPAIGN TABLE:
  IS Share (Search Term Impression Share) is a keyword-level metric from
  Amazon — it measures your brand's total impression share for that search
  term. If you see different IS values per campaign, it is because each
  campaign was active on different days within the report period, giving
  slightly different time-weighted averages. Using a Summary STIS report
  (Step 2) minimises this variation.


STEP 9 — EXPORT DATA
----------------------
- Click "⬇ Export" (top right of the keyword table) to download the
  current tab's keywords as a CSV.
- Click "⬇ Export campaigns" (below the campaign table) to download
  the campaign breakdown for the selected keyword.


STEP 10 — SAVE RAW DATA TO GOOGLE SHEETS (optional)
-----------------------------------------------------
The sidebar has a "💾 Save to Google Sheets" section that saves the raw
uploaded reports into a Google Sheet (tabs: SQPA Current, STIS Current,
and — if previous-period files are uploaded — SQPA Previous, STIS Previous).
Each save overwrites the tabs with the latest uploaded data.

To save to YOUR OWN Google Sheet:
1. Make sure the file "growisto-sheets-key.json" is in the app folder
   (it ships with this folder — don't share it outside Growisto).
2. Create a new Google Sheet.
3. Click Share on the sheet and add the service account email shown in
   the app sidebar (it looks like ...@...iam.gserviceaccount.com) as
   an EDITOR.
4. Paste your sheet's URL into the "Google Sheet URL or ID" box in the
   sidebar and click "Save uploaded data".


========================================
  COLUMNS EXPLAINED
========================================

From SQPA (Amazon Brand Analytics — monthly):
  SQV                 Search Query Volume — total monthly searches
  Brand Impr. Share   Your brand impressions ÷ total impressions (%)
  Brand Click Share   Your brand clicks ÷ total clicks (%)
  Brand ATC Share     Your brand add-to-carts ÷ total add-to-carts (%)
  Brand Purch. Share  Your brand purchases ÷ total purchases (%)

From STIS (Amazon Ads — selected period):
  Spend               Total ad spend for this keyword
  Sales               Total ad-attributed sales
  ACOS                Advertising Cost of Sales (Spend ÷ Sales × 100)
  IS Share            Search Term Impression Share per campaign


========================================
  QUESTIONS OR ISSUES?
========================================
Contact the Growisto team.
