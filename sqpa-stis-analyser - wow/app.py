"""
Keyword-Level Organic Tracker
Combines SQPA (Brand Analytics) + STIS (Ads Impression Share) reports.
"""

import base64
import io
import re
from pathlib import Path

import gspread
import numpy as np
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from PIL import Image

_LOGO_PATH = Path(__file__).parent / "s-blob-v1-IMAGE-aPpwLZpDbS4.png"


@st.cache_resource
def _growisto_icon():
    """PIL Image for the browser-tab favicon."""
    return Image.open(_LOGO_PATH)


@st.cache_data
def _logo_b64() -> str:
    """Base64-encoded logo for inline HTML use."""
    return base64.b64encode(_LOGO_PATH.read_bytes()).decode()


# ─── Google Sheets config ─────────────────────────────────────────────────────
SHEET_ID = "1anicRRSilrThqZ9ZzOAtNvJwdhIDs-DMJ9__CbPKPqA"
_KEY_FILE = Path(__file__).parent / "growisto-sheets-key.json"
_GS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@st.cache_resource(show_spinner=False)
def _get_gc():
    creds = Credentials.from_service_account_file(str(_KEY_FILE), scopes=_GS_SCOPES)
    return gspread.authorize(creds)


def _extract_sheet_id(text: str) -> str:
    """Accepts a full Google Sheets URL or a bare sheet ID."""
    text = str(text).strip()
    m = re.search(r"/d/([a-zA-Z0-9\-_]+)", text)
    return m.group(1) if m else text


def _service_account_email() -> str:
    """Email of the service account, for sheet-sharing instructions."""
    try:
        import json
        return json.loads(_KEY_FILE.read_text())["client_email"]
    except Exception:
        return "(key file not found)"


def save_to_sheets(sheet_id: str, sqpa_bytes: bytes, stis_bytes: bytes,
                   sqpa_prev_bytes: bytes = None, stis_prev_bytes: bytes = None):
    gc = _get_gc()
    sh = gc.open_by_key(sheet_id)
    ts = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")

    def _write_tab(title: str, df: pd.DataFrame, min_rows: int):
        try:
            ws = sh.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title, rows=max(len(df) + 10, min_rows), cols=len(df.columns) + 2)
        ws.clear()
        clean = df.fillna("")
        ws.update([clean.columns.tolist()], value_input_option="USER_ENTERED")
        if not clean.empty:
            ws.append_rows(clean.values.tolist(), value_input_option="USER_ENTERED")

    def _read_sqpa_raw(b: bytes) -> pd.DataFrame:
        d = pd.read_csv(io.BytesIO(b), skiprows=1, encoding="utf-8-sig")
        d.columns = d.columns.str.strip()
        return d

    def _read_stis_raw(b: bytes) -> pd.DataFrame:
        d = pd.read_csv(io.BytesIO(b))
        d.columns = d.columns.str.strip()
        return d

    saved = []
    _write_tab("SQPA Current", _read_sqpa_raw(sqpa_bytes), 500)
    saved.append("SQPA Current")
    _write_tab("STIS Current", _read_stis_raw(stis_bytes), 2000)
    saved.append("STIS Current")
    if sqpa_prev_bytes is not None:
        _write_tab("SQPA Previous", _read_sqpa_raw(sqpa_prev_bytes), 500)
        saved.append("SQPA Previous")
    if stis_prev_bytes is not None:
        _write_tab("STIS Previous", _read_stis_raw(stis_prev_bytes), 2000)
        saved.append("STIS Previous")

    return ts, saved


# ─── Currency handling (multi-geography) ──────────────────────────────────────
_CURRENCY_SYMBOLS = {
    "USD": "$", "INR": "₹", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CAD": "C$", "AUD": "A$", "MXN": "MX$", "BRL": "R$", "SGD": "S$",
    "AED": "AED ", "SAR": "SAR ", "SEK": "kr ", "PLN": "zł ", "TRY": "₺",
}
CUR = "$"  # display symbol — updated after the STIS report is loaded

# ─── Growisto brand tokens ────────────────────────────────────────────────────
TEAL_BLUE    = "#367588"
POWDER_BLUE  = "#B8DBD9"
FLAME        = "#E35D34"
RAISIN_BLACK = "#1D1D20"
CULTURED     = "#F6F6F4"
TEAL_HOVER   = "#2A5A6A"

st.set_page_config(
    page_title="Organic Tracker | Growisto",
    page_icon=_growisto_icon(),
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Poppins', sans-serif !important;
    background-color: #F6F6F4;
}
[data-testid="stSidebar"] { background-color: #367588 !important; }
[data-testid="stSidebar"] * { color: #FFFFFF !important; font-family: 'Poppins', sans-serif !important; }
[data-testid="stSidebar"] .stSlider label,
[data-testid="stSidebar"] .stMultiSelect label { color: #B8DBD9 !important; font-weight: 600; font-size: 12px; }
[data-testid="stSidebar"] hr { border-color: #2A5A6A !important; }
[data-testid="stSidebar"] code {
    background-color: #B8DBD9 !important;
    color: #1D1D20 !important;
    padding: 1px 5px; border-radius: 4px;
    font-size: 11px; word-break: break-all;
}
[data-testid="stSidebar"] .streamlit-expanderHeader {
    background-color: #2A5A6A !important; color: #FFFFFF !important;
    font-weight: 600 !important; border-radius: 4px;
}
[data-testid="stSidebar"] .streamlit-expanderContent {
    background-color: #2A5A6A !important; border-radius: 0 0 4px 4px;
}
[data-testid="stMetric"] {
    background: #B8DBD9; border-left: 4px solid #367588;
    padding: 12px 16px; border-radius: 0 8px 8px 0;
}
[data-testid="stMetricValue"] {
    color: #367588 !important; font-family: 'Poppins', sans-serif !important; font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: #1D1D20 !important; font-family: 'Poppins', sans-serif !important; font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #B8DBD9; }
.stTabs [data-baseweb="tab"] { font-family: 'Poppins', sans-serif !important; font-weight: 600; color: #1D1D20; }
.stTabs [aria-selected="true"] { color: #367588 !important; border-bottom: 2px solid #367588 !important; }
.streamlit-expanderHeader {
    background-color: #B8DBD9 !important; color: #1D1D20 !important;
    font-family: 'Poppins', sans-serif !important; font-weight: 600 !important; border-radius: 6px;
}
.stButton > button {
    background-color: #367588 !important; color: #FFFFFF !important;
    font-family: 'Poppins', sans-serif !important; font-weight: 600 !important;
    border: none !important; border-radius: 4px !important;
}
.stButton > button:hover { background-color: #2A5A6A !important; }
.stDataFrame { border: 1px solid #B8DBD9; border-radius: 8px; overflow: hidden; }
.stAlert {
    background-color: #B8DBD9 !important; border-left: 4px solid #367588 !important;
    color: #1D1D20 !important; font-family: 'Poppins', sans-serif !important;
}
.stCaption, small { color: #1D1D20 !important; font-family: 'Poppins', sans-serif !important; }
.stSpinner > div { border-top-color: #367588 !important; }
hr { border-color: #B8DBD9 !important; }
</style>
""", unsafe_allow_html=True)


# ─── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_sqpa(file_bytes: bytes):
    df = pd.read_csv(io.BytesIO(file_bytes), skiprows=1, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        "Search Query": "Keyword",
        "Search Query Volume": "SQV",
        "Impressions: Brand Share %": "IS",
        "Clicks: Brand Share %": "CS",
        "Cart Adds: Brand Share %": "ATC",        # SQPA column name
        "Add to Cart: Brand Share %": "ATC",      # alternative name in some exports
        "Purchases: Brand Share %": "PS",
    })
    for col in ["SQV", "IS", "CS", "PS"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "ATC" in df.columns:
        df["ATC"] = pd.to_numeric(df["ATC"], errors="coerce")
    else:
        df["ATC"] = np.nan
    df["Keyword"] = df["Keyword"].astype(str).str.strip().str.lower()

    raw = pd.read_csv(io.BytesIO(file_bytes), nrows=1, header=None, encoding="utf-8-sig")
    meta = ",".join(str(v) for v in raw.iloc[0].tolist()) if not raw.empty else ""
    import re as _re
    _m_week = _re.search(r'Select week=\["([^"]+)"\]', meta)
    _m_year = _re.search(r'Select year=\["([^"]+)"\]', meta)
    _m_month = _re.search(r'Select month=\["([^"]+)"\]', meta)
    if _m_week:
        period = _m_week.group(1)
    elif _m_year and _m_month:
        period = f"{_m_month.group(1)} {_m_year.group(1)}"
    else:
        period = str(raw.iloc[0, 0]) if not raw.empty else ""

    return df[["Keyword", "SQV", "IS", "CS", "ATC", "PS"]].copy(), period


@st.cache_data(show_spinner=False)
def load_stis(file_bytes: bytes):
    df = pd.read_csv(io.BytesIO(file_bytes))
    df.columns = df.columns.str.strip()

    def strip_dollar(s):
        # Strip any currency symbol ($, ₹, €, commas, spaces) — keep digits, dot, minus
        return pd.to_numeric(
            s.astype(str).str.replace(r"[^0-9.\-]", "", regex=True),
            errors="coerce",
        )

    # Sales / orders column names vary by marketplace & attribution window
    # (e.g. "7 Day Total Sales" in US, "14-day total sales" in IN)
    _sales_col  = next((c for c in df.columns if "total sales" in c.lower() and "acos" not in c.lower()), None)
    _orders_col = next((c for c in df.columns if "total orders" in c.lower()), None)
    if _sales_col is None or _orders_col is None:
        raise ValueError(
            "Could not find total sales / total orders columns in the STIS report. "
            f"Columns found: {list(df.columns)}"
        )

    # Detect display currency: Currency column if present, else sniff a symbol from Spend
    cur = "$"
    if "Currency" in df.columns and df["Currency"].notna().any():
        _code = str(df["Currency"].dropna().mode().iloc[0]).strip().upper()
        cur = _CURRENCY_SYMBOLS.get(_code, _code + " ")
    elif "Spend" in df.columns and len(df):
        _m_sym = re.search(r"[^\d\s.,\-]+", str(df["Spend"].dropna().astype(str).iloc[0]))
        if _m_sym:
            cur = _m_sym.group(0)

    df["Spend"]       = strip_dollar(df["Spend"])
    df["Sales"]       = strip_dollar(df[_sales_col])
    df["Clicks"]      = pd.to_numeric(df["Clicks"], errors="coerce")
    df["Impressions"] = pd.to_numeric(df["Impressions"], errors="coerce")
    df["Orders"]      = pd.to_numeric(df[_orders_col], errors="coerce")
    df["Keyword"]     = df["Customer Search Term"].astype(str).str.strip().str.lower()
    df["Date_parsed"] = pd.to_datetime(df["Date"], errors="coerce")

    # ── Parse Search Term Impression Share ────────────────────────────────────
    _is_col = next((c for c in df.columns if "impression share" in c.lower()), None)
    if _is_col:
        df["STIS_IS"] = pd.to_numeric(
            df[_is_col].astype(str).str.replace("%", "", regex=False).str.strip(),
            errors="coerce",
        )
        _max_is = df["STIS_IS"].dropna().max()
        if pd.notna(_max_is) and _max_is <= 1.0:
            df["STIS_IS"] = df["STIS_IS"] * 100
    else:
        df["STIS_IS"] = np.nan

    # ── Campaign-level aggregation (keyword × campaign × portfolio) ──────────
    camp_agg = (
        df.groupby(["Keyword", "Campaign Name", "Portfolio name"])
        .agg(
            Spend=("Spend", "sum"),
            Sales=("Sales", "sum"),
            Impressions=("Impressions", "sum"),
            Clicks=("Clicks", "sum"),
            Orders=("Orders", "sum"),
        )
        .reset_index()
        .rename(columns={"Campaign Name": "Campaign", "Portfolio name": "Portfolio"})
    )

    # Weighted-average STIS_IS per campaign (weight = impressions)
    _valid_df = df[df["STIS_IS"].notna() & (df["Impressions"] > 0)].copy()
    if not _valid_df.empty:
        _valid_df["_IS_x_I"] = _valid_df["STIS_IS"] * _valid_df["Impressions"]
        _camp_is = (
            _valid_df.groupby(["Keyword", "Campaign Name", "Portfolio name"])[["_IS_x_I", "Impressions"]]
            .sum()
            .reset_index()
        )
        _camp_is["STIS_IS"] = _camp_is["_IS_x_I"] / _camp_is["Impressions"]
        _camp_is = _camp_is.rename(columns={"Campaign Name": "Campaign", "Portfolio name": "Portfolio"})
        camp_agg = camp_agg.merge(
            _camp_is[["Keyword", "Campaign", "Portfolio", "STIS_IS"]],
            on=["Keyword", "Campaign", "Portfolio"], how="left",
        )
    else:
        camp_agg["STIS_IS"] = np.nan

    camp_agg["ACOS"] = camp_agg.apply(
        lambda r: r["Spend"] / r["Sales"] * 100 if r["Sales"] > 0 else np.nan, axis=1)
    camp_agg["CTR"]  = camp_agg.apply(
        lambda r: r["Clicks"] / r["Impressions"] * 100 if r["Impressions"] > 0 else np.nan, axis=1)
    camp_agg["CPC"]  = camp_agg.apply(
        lambda r: r["Spend"] / r["Clicks"] if r["Clicks"] > 0 else np.nan, axis=1)
    camp_agg["CVR"]  = camp_agg.apply(
        lambda r: r["Orders"] / r["Clicks"] * 100 if r["Clicks"] > 0 else np.nan, axis=1)

    # ── Keyword-level aggregation ────────────────────────────────────────────
    date_rng = (
        df.groupby("Keyword")
        .agg(Date_min=("Date_parsed", "min"), Date_max=("Date_parsed", "max"))
        .reset_index()
    )
    kw_agg = (
        camp_agg.groupby("Keyword")
        .agg(
            Spend=("Spend", "sum"),
            Sales=("Sales", "sum"),
            Impressions=("Impressions", "sum"),
            Clicks=("Clicks", "sum"),
            Orders=("Orders", "sum"),
            Portfolio=("Portfolio", lambda x: x.mode().iloc[0] if len(x) else "No Portfolio"),
        )
        .reset_index()
    )

    _kw_is_src = camp_agg[camp_agg["STIS_IS"].notna() & (camp_agg["Impressions"] > 0)].copy()
    if not _kw_is_src.empty:
        _kw_is_src["_IS_x_I"] = _kw_is_src["STIS_IS"] * _kw_is_src["Impressions"]
        _kw_is = (
            _kw_is_src.groupby("Keyword")[["_IS_x_I", "Impressions"]]
            .sum()
            .reset_index()
        )
        _kw_is["Weighted_STIS_IS"] = _kw_is["_IS_x_I"] / _kw_is["Impressions"]
        kw_agg = kw_agg.merge(_kw_is[["Keyword", "Weighted_STIS_IS"]], on="Keyword", how="left")
    else:
        kw_agg["Weighted_STIS_IS"] = np.nan

    kw_agg["ACOS"] = kw_agg.apply(
        lambda r: r["Spend"] / r["Sales"] * 100 if r["Sales"] > 0 else np.nan, axis=1)
    kw_agg["CTR"]  = kw_agg.apply(
        lambda r: r["Clicks"] / r["Impressions"] * 100 if r["Impressions"] > 0 else np.nan, axis=1)
    kw_agg["CPC"]  = kw_agg.apply(
        lambda r: r["Spend"] / r["Clicks"] if r["Clicks"] > 0 else np.nan, axis=1)
    kw_agg["CVR"]  = kw_agg.apply(
        lambda r: r["Orders"] / r["Clicks"] * 100 if r["Clicks"] > 0 else np.nan, axis=1)
    kw_agg = kw_agg.merge(date_rng, on="Keyword", how="left")

    return kw_agg, camp_agg, cur


# ─── Insight classification ────────────────────────────────────────────────────
def classify(row, t: dict) -> str:
    spend = row["Spend"] if pd.notna(row["Spend"]) else 0.0
    sales = row["Sales"] if pd.notna(row["Sales"]) else 0.0
    acos  = row["ACOS"]  if pd.notna(row["ACOS"])  else None
    is_v  = row["IS"]    if pd.notna(row["IS"])    else 0.0
    sqv   = row["SQV"]   if pd.notna(row["SQV"])   else 0.0

    if spend >= t["waste_min_spend"] and sales == 0:
        return "Wasted Spend"
    if (is_v >= t["work_min_is"]
            and sales >= t["work_min_sales"]
            and acos is not None
            and acos <= t["work_max_acos"]):
        return "Working"
    if acos is not None and acos > t["ineff_min_acos"] and spend >= t["ineff_min_spend"] and sales > 0:
        return "Inefficient"
    if sqv >= t["opp_min_sqv"] and is_v < t["opp_max_is"]:
        return "Opportunity"
    return "No Signal"


STATUS_ORDER = {"Wasted Spend": 0, "Inefficient": 1, "Opportunity": 2, "Working": 3, "No Signal": 4}
STATUS_LABEL = {
    "Working":      "✅ Working",
    "Wasted Spend": "💸 Wasted Spend",
    "Opportunity":  "💡 Opportunity",
    "Inefficient":  "⚠️ Inefficient",
    "No Signal":    "➖ No Signal",
}


# ─── Display helpers ───────────────────────────────────────────────────────────
def _fmt_kw(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["Keyword"]     = d["Keyword"].str.title()
    d["SQV"]         = d["SQV"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "–")
    d["Brand Impr. Share"]  = d["IS"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "–")
    d["Brand Click Share"]  = d["CS"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "–")
    d["Brand ATC Share"]    = d["ATC"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "–")
    d["Brand Purch. Share"] = d["PS"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "–")
    d["Spend"]              = d["Spend"].apply(lambda x: f"{CUR}{x:,.2f}" if pd.notna(x) else "–")
    d["Sales"]              = d["Sales"].apply(lambda x: f"{CUR}{x:,.2f}" if pd.notna(x) else "–")
    d["ACOS"]               = d["ACOS"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "–")
    d["Status"]             = d["Status"].map(STATUS_LABEL)
    return d[["Keyword", "Portfolio", "SQV",
              "Brand Impr. Share", "Brand Click Share", "Brand ATC Share", "Brand Purch. Share",
              "Spend", "Sales", "ACOS", "Status"]]


def _fmt_camp(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["Spend"]                = d["Spend"].apply(lambda x: f"{CUR}{x:,.2f}" if pd.notna(x) else "–")
    d["Sales"]                = d["Sales"].apply(lambda x: f"{CUR}{x:,.2f}" if pd.notna(x) else "–")
    d["ACOS"]                 = d["ACOS"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "–")
    d["Impressions"]          = d["Impressions"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "–")
    d["Clicks"]               = d["Clicks"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "–")
    d["CTR"]                  = d["CTR"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "–")
    d["CPC"]                  = d["CPC"].apply(lambda x: f"{CUR}{x:.2f}" if pd.notna(x) else "–")
    d["CVR"]                  = d["CVR"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "–")
    d["Orders"]   = d["Orders"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "–")
    d["IS Share"] = d["STIS_IS"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "–")
    return d[["Campaign", "Portfolio", "Impressions", "IS Share",
              "Clicks", "CTR", "CPC", "Spend", "Sales", "ACOS", "CVR", "Orders"]]


def show_kw_table(df: pd.DataFrame, camp_agg: pd.DataFrame, height: int = 520, tab_key: str = "all"):
    if df.empty:
        st.info("No keywords match this filter.")
        return

    # ── Metric legend bar ────────────────────────────────────────────────────
    _legend_items = [
        ("SQV",               "Search Query Volume",       "Total monthly searches for this keyword on Amazon (from SQPA)"),
        ("Brand Impr. Share", "Brand Impression Share",    "Brand impressions ÷ total impressions for this query (SQPA)"),
        ("Brand Click Share", "Brand Click Share",         "Brand clicks ÷ total clicks for this query (SQPA)"),
        ("Brand ATC Share",   "Brand Add-to-Cart Share",   "Brand add-to-cart events ÷ total ATCs for this query (SQPA)"),
        ("Brand Purch. Share","Brand Purchase Share",      "Brand purchases ÷ total purchases for this query (SQPA)"),
    ]
    _legend_cells = "".join(
        f"<div style='flex:1;padding:7px 12px;"
        f"{'border-right:1px solid #D1E8E7;' if i < len(_legend_items) - 1 else ''}'>"
        f"<div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:700;"
        f"color:{TEAL_BLUE};margin-bottom:2px;'>{abbr}</div>"
        f"<div style='font-family:Poppins,sans-serif;font-size:11px;font-weight:600;"
        f"color:{RAISIN_BLACK};margin-bottom:1px;'>{full}</div>"
        f"<div style='font-family:Poppins,sans-serif;font-size:10px;color:#6B7280;"
        f"line-height:1.3;'>{formula}</div>"
        f"</div>"
        for i, (abbr, full, formula) in enumerate(_legend_items)
    )
    st.markdown(
        f"<div style='display:flex;background:#F0F7F8;border:1px solid {POWDER_BLUE};"
        f"border-radius:8px;overflow:hidden;margin-bottom:10px;'>"
        f"<div style='padding:7px 12px;background:{TEAL_BLUE};display:flex;align-items:center;"
        f"min-width:fit-content;'>"
        f"<span style='font-family:Poppins,sans-serif;font-size:10px;font-weight:700;"
        f"color:#FFFFFF;writing-mode:horizontal-tb;white-space:nowrap;'>📖 Column Guide</span>"
        f"</div>"
        f"{_legend_cells}</div>",
        unsafe_allow_html=True,
    )

    event = st.dataframe(
        _fmt_kw(df),
        use_container_width=True,
        hide_index=True,
        height=height,
        on_select="rerun",
        selection_mode="single-row",
    )

    cap_col, btn_col = st.columns([6, 1])
    with cap_col:
        st.caption(f"{len(df):,} keywords · Click a row to see campaign breakdown")
    with btn_col:
        st.download_button(
            label="⬇ Export",
            data=_fmt_kw(df).to_csv(index=False).encode("utf-8"),
            file_name=f"keywords_{tab_key}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"dl_kw_{tab_key}",
        )

    if not event.selection.rows:
        return

    sel_idx = event.selection.rows[0]
    sel_kw  = df.iloc[sel_idx]["Keyword"]
    r       = df.iloc[sel_idx]

    st.markdown(
        f"<div style='margin-top:16px;padding:12px 16px;background:{POWDER_BLUE};"
        f"border-left:4px solid {TEAL_BLUE};border-radius:0 8px 8px 0;'>"
        f"<span style='font-family:Poppins,sans-serif;font-weight:700;color:{TEAL_BLUE};"
        f"font-size:14px;'>📋 {sel_kw.title()}</span>"
        f"<span style='font-family:Poppins,sans-serif;color:{RAISIN_BLACK};font-size:12px;"
        f"margin-left:8px;'>— campaign breakdown</span></div>",
        unsafe_allow_html=True,
    )

    # Mini KPI strip
    _kpis = [
        ("SQV",               f"{int(r['SQV']):,}"  if pd.notna(r['SQV'])   else "–"),
        ("Brand Impr. Share", f"{r['IS']:.2f}%"     if pd.notna(r['IS'])    else "–"),
        ("Total Spend",       f"{CUR}{r['Spend']:,.2f}"  if pd.notna(r['Spend']) else "–"),
        ("Total Sales",       f"{CUR}{r['Sales']:,.2f}"  if pd.notna(r['Sales']) else "–"),
        ("ACOS",              f"{r['ACOS']:.1f}%"    if pd.notna(r['ACOS'])  else "–"),
        ("Status",            STATUS_LABEL.get(r["Status"], r["Status"])),
    ]
    _cells = "".join(
        f"<div style='flex:1;text-align:center;padding:6px 10px;"
        f"{'border-right:1px solid ' + POWDER_BLUE + ';' if i < len(_kpis) - 1 else ''}'>"
        f"<div style='font-family:Poppins,sans-serif;font-size:10px;font-weight:600;"
        f"color:#6B7280;text-transform:uppercase;letter-spacing:0.4px;"
        f"margin-bottom:2px;'>{lbl}</div>"
        f"<div style='font-family:Poppins,sans-serif;font-size:13px;font-weight:700;"
        f"color:{TEAL_BLUE};line-height:1.2;'>{val}</div>"
        f"</div>"
        for i, (lbl, val) in enumerate(_kpis)
    )
    st.markdown(
        f"<div style='display:flex;align-items:stretch;background:#FFFFFF;"
        f"border:1px solid {POWDER_BLUE};border-radius:0 0 8px 8px;"
        f"overflow:hidden;margin-bottom:12px;'>{_cells}</div>",
        unsafe_allow_html=True,
    )

    kw_camps = camp_agg[camp_agg["Keyword"] == sel_kw]
    if kw_camps.empty:
        st.info("No campaign data found for this keyword in the uploaded STIS report.")
    else:
        st.dataframe(_fmt_camp(kw_camps), use_container_width=True, hide_index=True)
        st.download_button(
            label="⬇ Export campaigns",
            data=_fmt_camp(kw_camps).to_csv(index=False).encode("utf-8"),
            file_name=f"campaigns_{sel_kw.replace(' ', '_')}.csv",
            mime="text/csv",
        )


# ─── Week-on-Week helpers ─────────────────────────────────────────────────────
def build_wow_df(curr_df: pd.DataFrame, prev_df: pd.DataFrame) -> pd.DataFrame:
    """Outer-merge current and previous period, compute per-keyword deltas."""
    _cols = ["Keyword", "Portfolio", "Status",
             "SQV", "IS", "CS", "ATC", "PS",
             "Spend", "Sales", "ACOS", "Impressions", "Clicks", "Orders"]
    curr = curr_df[[c for c in _cols if c in curr_df.columns]].copy()
    prev = prev_df[[c for c in _cols if c in prev_df.columns]].copy()
    prev = prev.rename(columns={c: f"{c}_prev" for c in prev.columns if c != "Keyword"})

    wow = curr.merge(prev, on="Keyword", how="outer")
    wow["Portfolio"]   = wow["Portfolio"].fillna("–")
    wow["Status"]      = wow["Status"].fillna("No Signal")
    if "Status_prev" not in wow.columns:
        wow["Status_prev"] = "No Signal"
    else:
        wow["Status_prev"] = wow["Status_prev"].fillna("No Signal")

    def _pct(a, b):
        if pd.isna(a) or pd.isna(b) or b == 0:
            return np.nan
        return (a - b) / abs(b) * 100

    def _pp(a, b):
        if pd.isna(a) or pd.isna(b):
            return np.nan
        return a - b

    for _c in ["Spend", "Sales", "Impressions", "Clicks", "Orders", "SQV"]:
        _cp = f"{_c}_prev"
        wow[f"{_c}_delta"] = wow.apply(
            lambda r, c=_c, cp=_cp: _pct(r.get(c, np.nan), r.get(cp, np.nan)), axis=1
        )
    for _c in ["ACOS", "IS", "CS", "ATC", "PS"]:
        _cp = f"{_c}_prev"
        wow[f"{_c}_delta"] = wow.apply(
            lambda r, c=_c, cp=_cp: _pp(r.get(c, np.nan), r.get(cp, np.nan)), axis=1
        )

    wow["Status_changed"] = wow["Status"] != wow["Status_prev"]
    wow["_in_curr"] = wow["Keyword"].isin(curr_df["Keyword"].values)
    wow["_in_prev"] = wow["Keyword"].isin(prev_df["Keyword"].values)
    return wow


def _export_wow(df: pd.DataFrame) -> pd.DataFrame:
    """Flat string-formatted version of the WoW df for CSV export."""
    d = df.copy()
    d["Keyword"] = d["Keyword"].str.title()
    d["Status Change"] = d.apply(
        lambda r: (
            f'{STATUS_LABEL.get(r["Status_prev"], r["Status_prev"])} → '
            f'{STATUS_LABEL.get(r["Status"], r["Status"])}'
        ) if r["Status_changed"] else "–",
        axis=1,
    )
    d["Status"] = d["Status"].map(STATUS_LABEL)

    def _fp(v, dp=1):
        if pd.isna(v): return "–"
        return f"{'+' if v > 0 else ''}{v:.{dp}f}%"

    def _fpp(v, dp=2):
        if pd.isna(v): return "–"
        return f"{'+' if v > 0 else ''}{v:.{dp}f}pp"

    rn = {
        "SQV_prev": "SQV (Prev)", "SQV": "SQV (Curr)",
        "IS_prev": "Brand IS% (Prev)", "IS": "Brand IS% (Curr)",
        "CS_prev": "Click Share% (Prev)", "CS": "Click Share% (Curr)",
        "ATC_prev": "ATC Share% (Prev)", "ATC": "ATC Share% (Curr)",
        "PS_prev": "Purch. Share% (Prev)", "PS": "Purch. Share% (Curr)",
        "Spend_prev": "Spend (Prev)", "Spend": "Spend (Curr)",
        "Sales_prev": "Sales (Prev)", "Sales": "Sales (Curr)",
        "ACOS_prev": "ACOS (Prev)", "ACOS": "ACOS (Curr)",
        "Orders_prev": "Orders (Prev)", "Orders": "Orders (Curr)",
        "SQV_delta": "SQV Δ%", "IS_delta": "IS Δ (pp)", "CS_delta": "Click Δ (pp)",
        "ATC_delta": "ATC Δ (pp)", "PS_delta": "Purch. Δ (pp)",
        "Spend_delta": "Spend Δ%", "Sales_delta": "Sales Δ%",
        "ACOS_delta": "ACOS Δ (pp)", "Orders_delta": "Orders Δ%",
    }
    d = d.rename(columns=rn)
    for col in ["SQV Δ%", "Spend Δ%", "Sales Δ%", "Orders Δ%"]:
        if col in d.columns:
            d[col] = d[col].apply(_fp)
    for col in ["IS Δ (pp)", "Click Δ (pp)", "ATC Δ (pp)", "Purch. Δ (pp)", "ACOS Δ (pp)"]:
        if col in d.columns:
            d[col] = d[col].apply(_fpp)

    _out_cols = ["Keyword", "Portfolio", "Status", "Status Change",
                 "SQV (Prev)", "SQV (Curr)", "SQV Δ%",
                 "Brand IS% (Prev)", "Brand IS% (Curr)", "IS Δ (pp)",
                 "Click Share% (Prev)", "Click Share% (Curr)", "Click Δ (pp)",
                 "ATC Share% (Prev)", "ATC Share% (Curr)", "ATC Δ (pp)",
                 "Purch. Share% (Prev)", "Purch. Share% (Curr)", "Purch. Δ (pp)",
                 "Spend (Prev)", "Spend (Curr)", "Spend Δ%",
                 "Sales (Prev)", "Sales (Curr)", "Sales Δ%",
                 "ACOS (Prev)", "ACOS (Curr)", "ACOS Δ (pp)",
                 "Orders (Prev)", "Orders (Curr)", "Orders Δ%"]
    return d[[c for c in _out_cols if c in d.columns]]


def show_wow_tab(
    wow_df: pd.DataFrame,
    curr_filtered: pd.DataFrame,
    prev_filtered: pd.DataFrame,
    curr_sqpa_period: str,
    prev_sqpa_period: str,
    curr_stis_range: str,
    prev_stis_range: str,
):
    # ── Period header ─────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-family:Poppins,sans-serif;font-size:13px;padding:10px 16px;"
        f"background:#F0F7F8;border:1px solid {POWDER_BLUE};border-radius:8px;"
        f"margin-bottom:14px;'>"
        f"<b style='color:{TEAL_BLUE};'>◀ Previous</b>&nbsp;"
        f"<span style='color:{RAISIN_BLACK};'>"
        f"SQPA {prev_sqpa_period or '–'} · STIS {prev_stis_range or '–'}"
        f"</span>"
        f"&emsp;→&emsp;"
        f"<b style='color:{TEAL_BLUE};'>▶ Current</b>&nbsp;"
        f"<span style='color:{RAISIN_BLACK};'>"
        f"SQPA {curr_sqpa_period or '–'} · STIS {curr_stis_range or '–'}"
        f"</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Summary KPIs ──────────────────────────────────────────────────────────
    c_spend  = curr_filtered["Spend"].fillna(0).sum()
    p_spend  = prev_filtered["Spend"].fillna(0).sum()
    c_sales  = curr_filtered["Sales"].fillna(0).sum()
    p_sales  = prev_filtered["Sales"].fillna(0).sum()
    c_acos   = c_spend / c_sales * 100 if c_sales > 0 else np.nan
    p_acos   = p_spend / p_sales * 100 if p_sales > 0 else np.nan
    c_orders = int(curr_filtered["Orders"].fillna(0).sum())
    p_orders = int(prev_filtered["Orders"].fillna(0).sum())

    changed_count  = int(wow_df["Status_changed"].sum())
    new_kws_count  = int((~wow_df["_in_prev"]).sum())
    lost_kws_count = int((~wow_df["_in_curr"]).sum())

    def _delta(curr_v, prev_v, is_pp=False, higher_is_good=True):
        """Returns (label_str, color)."""
        if pd.isna(prev_v) or prev_v == 0:
            return "–", "#6B7280"
        if is_pp:
            d = curr_v - prev_v if not (pd.isna(curr_v) or pd.isna(prev_v)) else np.nan
            if pd.isna(d): return "–", "#6B7280"
            s = f"{'+' if d > 0 else ''}{d:.1f}pp"
        else:
            d = (curr_v - prev_v) / abs(prev_v) * 100
            s = f"{'+' if d > 0 else ''}{d:.1f}%"
        color = ("#00A650" if (d > 0) == higher_is_good else "#E53E3E") if abs(d) >= 0.05 else "#6B7280"
        return s, color

    def _card(label, val_str, delta_str, delta_color, border=None):
        bc = border or TEAL_BLUE
        return (
            f"<div style='flex:1;background:{POWDER_BLUE};border-left:4px solid {bc};"
            f"padding:10px 14px;border-radius:0 8px 8px 0;min-width:0;'>"
            f"<div style='font-family:Poppins,sans-serif;font-size:11px;font-weight:600;"
            f"color:{RAISIN_BLACK};white-space:nowrap;margin-bottom:2px;'>{label}</div>"
            f"<div style='font-family:Poppins,sans-serif;font-size:18px;font-weight:700;"
            f"color:{TEAL_BLUE};white-space:nowrap;'>{val_str}</div>"
            f"<div style='font-family:Poppins,sans-serif;font-size:11px;font-weight:600;"
            f"color:{delta_color};line-height:1.4;'>{delta_str}</div>"
            f"</div>"
        )

    sp_d, sp_c = _delta(c_spend, p_spend, higher_is_good=False)   # spend neutral
    sp_c = TEAL_BLUE                                                # always teal (context-dependent)
    sa_d, sa_c = _delta(c_sales, p_sales, higher_is_good=True)
    ac_d, ac_c = _delta(c_acos,  p_acos,  is_pp=True, higher_is_good=False)
    or_d, or_c = _delta(c_orders, p_orders, higher_is_good=True)

    kpi_html = "".join([
        _card("Total Spend",    f"{CUR}{c_spend:,.0f}",  sp_d, sp_c),
        _card("Total Sales",    f"{CUR}{c_sales:,.0f}",  sa_d, sa_c),
        _card("Overall ACOS",   f"{c_acos:.1f}%" if pd.notna(c_acos) else "–", ac_d, ac_c),
        _card("Total Orders",   f"{c_orders:,}",     or_d, or_c),
        _card("Status Changes", f"{changed_count}",  "keywords moved category", "#6B7280", FLAME),
        _card("New Keywords",   f"{new_kws_count}",  "not in previous period",  "#6B7280", "#00A650"),
        _card("Lost Keywords",  f"{lost_kws_count}", "not in current period",   "#6B7280", "#E53E3E"),
    ])
    st.markdown(
        f"<div style='display:flex;gap:8px;margin-bottom:16px;'>{kpi_html}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Filter + export row ───────────────────────────────────────────────────
    fc1, fc2 = st.columns([4, 1])
    with fc1:
        show_changed = st.checkbox(
            "Show only keywords with status changes", value=False, key="wow_changed_only"
        )
    with fc2:
        st.download_button(
            label="⬇ Export WoW",
            data=_export_wow(wow_df).to_csv(index=False).encode("utf-8"),
            file_name="wow_comparison.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # ── Build display df ──────────────────────────────────────────────────────
    disp = wow_df.copy()
    if show_changed:
        disp = disp[disp["Status_changed"]]

    disp["Keyword"] = disp["Keyword"].str.title()
    disp["Status Change"] = disp.apply(
        lambda r: (
            f'{STATUS_LABEL.get(r["Status_prev"], r["Status_prev"])} → '
            f'{STATUS_LABEL.get(r["Status"], r["Status"])}'
        ) if r["Status_changed"] else "–",
        axis=1,
    )
    disp["Status"] = disp["Status"].map(STATUS_LABEL)

    _show_cols = [
        "Keyword", "Portfolio", "Status", "Status Change",
        "SQV_prev", "SQV", "SQV_delta",
        "IS_prev", "IS", "IS_delta",
        "CS_prev", "CS", "CS_delta",
        "ATC_prev", "ATC", "ATC_delta",
        "PS_prev", "PS", "PS_delta",
        "Spend_prev", "Spend", "Spend_delta",
        "Sales_prev", "Sales", "Sales_delta",
        "ACOS_prev", "ACOS", "ACOS_delta",
        "Orders_prev", "Orders", "Orders_delta",
    ]
    _col_cfg = {
        "Keyword":       st.column_config.TextColumn("Keyword"),
        "Portfolio":     st.column_config.TextColumn("Portfolio"),
        "Status":        st.column_config.TextColumn("Status"),
        "Status Change": st.column_config.TextColumn("Status Change", width="medium"),
        "SQV_prev":      st.column_config.NumberColumn("SQV (Prev)",          format="%d"),
        "SQV":           st.column_config.NumberColumn("SQV (Curr)",          format="%d"),
        "SQV_delta":     st.column_config.NumberColumn("SQV Δ%",              format="%.1f%%"),
        "IS_prev":       st.column_config.NumberColumn("Brand IS% (Prev)",    format="%.2f%%"),
        "IS":            st.column_config.NumberColumn("Brand IS% (Curr)",    format="%.2f%%"),
        "IS_delta":      st.column_config.NumberColumn("IS Δ (pp)",           format="%.2f"),
        "CS_prev":       st.column_config.NumberColumn("Click Share% (Prev)", format="%.2f%%"),
        "CS":            st.column_config.NumberColumn("Click Share% (Curr)", format="%.2f%%"),
        "CS_delta":      st.column_config.NumberColumn("Click Δ (pp)",        format="%.2f"),
        "ATC_prev":      st.column_config.NumberColumn("ATC Share% (Prev)",   format="%.2f%%"),
        "ATC":           st.column_config.NumberColumn("ATC Share% (Curr)",   format="%.2f%%"),
        "ATC_delta":     st.column_config.NumberColumn("ATC Δ (pp)",          format="%.2f"),
        "PS_prev":       st.column_config.NumberColumn("Purch. Share% (Prev)", format="%.2f%%"),
        "PS":            st.column_config.NumberColumn("Purch. Share% (Curr)", format="%.2f%%"),
        "PS_delta":      st.column_config.NumberColumn("Purch. Δ (pp)",       format="%.2f"),
        "Spend_prev":    st.column_config.NumberColumn("Spend (Prev)",        format=f"{CUR}%.2f"),
        "Spend":         st.column_config.NumberColumn("Spend (Curr)",        format=f"{CUR}%.2f"),
        "Spend_delta":   st.column_config.NumberColumn("Spend Δ%",            format="%.1f%%"),
        "Sales_prev":    st.column_config.NumberColumn("Sales (Prev)",        format=f"{CUR}%.2f"),
        "Sales":         st.column_config.NumberColumn("Sales (Curr)",        format=f"{CUR}%.2f"),
        "Sales_delta":   st.column_config.NumberColumn("Sales Δ%",            format="%.1f%%"),
        "ACOS_prev":     st.column_config.NumberColumn("ACOS (Prev)",         format="%.1f%%"),
        "ACOS":          st.column_config.NumberColumn("ACOS (Curr)",         format="%.1f%%"),
        "ACOS_delta":    st.column_config.NumberColumn("ACOS Δ (pp)",         format="%.2f"),
        "Orders_prev":   st.column_config.NumberColumn("Orders (Prev)",       format="%d"),
        "Orders":        st.column_config.NumberColumn("Orders (Curr)",       format="%d"),
        "Orders_delta":  st.column_config.NumberColumn("Orders Δ%",           format="%.1f%%"),
    }
    _visible = [c for c in _show_cols if c in disp.columns]
    st.dataframe(
        disp[_visible],
        column_config={k: v for k, v in _col_cfg.items() if k in _visible},
        use_container_width=True,
        hide_index=True,
        height=520,
    )
    st.caption(
        f"{len(disp):,} keywords · Click any column header to sort · "
        f"Δ% = % change · Δ (pp) = percentage-point change vs previous period"
    )


# ─── Page header ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='background:linear-gradient(135deg,{TEAL_BLUE},{TEAL_HOVER});color:#FFFFFF;
     padding:20px 24px;border-radius:8px;margin-bottom:20px;font-family:Poppins,sans-serif;'>
    <h1 style='margin:0;font-size:24px;font-weight:700;font-family:Poppins,sans-serif;display:flex;align-items:center;gap:10px;'>
        <img src='data:image/png;base64,{_logo_b64()}' width='38' height='38' style='flex-shrink:0;border-radius:50%;'/>
        Keyword-Level Organic Tracker
    </h1>
    <p style='margin:4px 0 0 0;color:{POWDER_BLUE};font-size:13px;font-weight:400;font-family:Poppins,sans-serif;'>
        SQPA brand share × STIS paid performance — combined keyword intelligence
    </p>
</div>
<div style='height:4px;background:{FLAME};border-radius:2px;margin:-16px 0 16px 0;'></div>
""", unsafe_allow_html=True)

# ─── File upload ──────────────────────────────────────────────────────────────
with st.expander("📂 Upload Reports", expanded=True):
    st.markdown(
        f"<p style='font-family:Poppins,sans-serif;font-size:12px;font-weight:700;"
        f"color:{TEAL_BLUE};margin:0 0 6px;'>Current Period</p>",
        unsafe_allow_html=True,
    )
    u1, u2 = st.columns(2)
    with u1:
        st.markdown("**SQPA** — Brand Analytics → Search Query Performance")
        sqpa_file = st.file_uploader("SQPA CSV", type=["csv"], label_visibility="collapsed", key="sqpa")
    with u2:
        st.markdown("**STIS** — Ads Console → Search Term Impression Share")
        stis_file = st.file_uploader("STIS CSV", type=["csv"], label_visibility="collapsed", key="stis")

    st.markdown(
        f"<p style='font-family:Poppins,sans-serif;font-size:12px;font-weight:700;"
        f"color:{TEAL_BLUE};margin:14px 0 6px;'>Previous Period "
        f"<span style='font-weight:400;color:#6B7280;font-size:11px;'>"
        f"— optional, upload both to unlock the 📊 Week-on-Week tab</span></p>",
        unsafe_allow_html=True,
    )
    u3, u4 = st.columns(2)
    with u3:
        st.markdown("**SQPA** — Previous Week")
        sqpa_prev_file = st.file_uploader(
            "SQPA Prev CSV", type=["csv"], label_visibility="collapsed", key="sqpa_prev"
        )
    with u4:
        st.markdown("**STIS** — Previous Week")
        stis_prev_file = st.file_uploader(
            "STIS Prev CSV", type=["csv"], label_visibility="collapsed", key="stis_prev"
        )

if sqpa_file is None or stis_file is None:
    st.info("Upload both reports above to activate the tracker.", icon="ℹ️")
    st.stop()

# ─── Load data ────────────────────────────────────────────────────────────────
with st.spinner("Processing reports…"):
    sqpa_bytes           = sqpa_file.read()
    stis_bytes           = stis_file.read()
    sqpa_df, sqpa_period  = load_sqpa(sqpa_bytes)
    kw_agg, camp_agg, CUR = load_stis(stis_bytes)

stis_min   = kw_agg["Date_min"].min()
stis_max   = kw_agg["Date_max"].max()
stis_range = (
    f"{stis_min.strftime('%b %d, %Y')} → {stis_max.strftime('%b %d, %Y')}"
    if pd.notna(stis_min) else "–"
)

merged = sqpa_df.merge(
    kw_agg[["Keyword", "Spend", "Sales", "ACOS", "Portfolio",
            "Impressions", "Clicks", "Orders", "CTR", "CPC", "CVR"]],
    on="Keyword", how="left",
)

# ─── Previous-period data (optional — unlocks WoW tab) ────────────────────────
has_wow = sqpa_prev_file is not None and stis_prev_file is not None
if has_wow:
    with st.spinner("Processing previous-period reports…"):
        sqpa_prev_bytes                = sqpa_prev_file.read()
        stis_prev_bytes                = stis_prev_file.read()
        sqpa_prev_df, sqpa_prev_period = load_sqpa(sqpa_prev_bytes)
        kw_agg_prev, _, _              = load_stis(stis_prev_bytes)
    _pmin = kw_agg_prev["Date_min"].min()
    _pmax = kw_agg_prev["Date_max"].max()
    stis_prev_range = (
        f"{_pmin.strftime('%b %d, %Y')} → {_pmax.strftime('%b %d, %Y')}"
        if pd.notna(_pmin) else "–"
    )
    merged_prev = sqpa_prev_df.merge(
        kw_agg_prev[["Keyword", "Spend", "Sales", "ACOS", "Portfolio",
                     "Impressions", "Clicks", "Orders", "CTR", "CPC", "CVR"]],
        on="Keyword", how="left",
    )
else:
    sqpa_prev_period = stis_prev_range = merged_prev = None
    sqpa_prev_bytes = stis_prev_bytes = None

# ─── Sidebar: portfolio filter ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filters")
    all_portfolios  = sorted(merged["Portfolio"].dropna().unique().tolist())
    selected_portfs = st.multiselect("Portfolio", all_portfolios, default=all_portfolios)

# ─── Inline threshold controls ────────────────────────────────────────────────
with st.expander("⚙️ Insight Thresholds", expanded=False):
    t1, t2, t3, t4 = st.columns(4)

    with t1:
        st.markdown(
            f"<p style='font-family:Poppins,sans-serif;font-size:12px;font-weight:700;"
            f"color:{TEAL_BLUE};margin-bottom:6px;'>✅ Working</p>",
            unsafe_allow_html=True,
        )
        work_min_is    = st.slider("Min IS (%)",    0.0,  50.0,  5.0, 0.5, key="w_is",
                                    help="Brand impression share must be at least this")
        work_max_acos  = st.slider("Max ACOS (%)", 0.0, 150.0, 30.0, 1.0, key="w_acos",
                                    help="ACOS must be at or below this")
        work_min_sales = st.slider(f"Min Sales ({CUR})", 0.0, 500.0,  0.0, 5.0, key="w_sales",
                                    help="Must have generated at least this in sales")

    with t2:
        st.markdown(
            f"<p style='font-family:Poppins,sans-serif;font-size:12px;font-weight:700;"
            f"color:{TEAL_BLUE};margin-bottom:6px;'>💡 Opportunity</p>",
            unsafe_allow_html=True,
        )
        opp_min_sqv = st.slider("Min SQV",     0, 10000,  500, 100, key="o_sqv",
                                 help="Minimum search volume to flag as an opportunity")
        opp_max_is  = st.slider("Max IS (%)", 0.0, 50.0,  5.0, 0.5, key="o_is",
                                 help="Brand IS below this = underrepresented")

    with t3:
        st.markdown(
            f"<p style='font-family:Poppins,sans-serif;font-size:12px;font-weight:700;"
            f"color:{TEAL_BLUE};margin-bottom:6px;'>⚠️ Inefficient</p>",
            unsafe_allow_html=True,
        )
        ineff_min_acos  = st.slider("Min ACOS (%)",  0.0, 150.0, 30.0, 1.0, key="i_acos",
                                     help="ACOS must exceed this to be flagged")
        ineff_min_spend = st.slider(f"Min Spend ({CUR})", 0.0, 200.0,  5.0, 1.0, key="i_spend",
                                     help="Only flag if spending at least this amount")

    with t4:
        st.markdown(
            f"<p style='font-family:Poppins,sans-serif;font-size:12px;font-weight:700;"
            f"color:{TEAL_BLUE};margin-bottom:6px;'>💸 Wasted Spend</p>",
            unsafe_allow_html=True,
        )
        waste_min_spend = st.slider(f"Min Spend ({CUR})", 0.0, 200.0, 5.0, 1.0, key="ws_spend",
                                     help="Flag keywords spending this with zero sales")

thresholds = {
    "work_min_is":     work_min_is,
    "work_max_acos":   work_max_acos,
    "work_min_sales":  work_min_sales,
    "opp_min_sqv":     opp_min_sqv,
    "opp_max_is":      opp_max_is,
    "ineff_min_acos":  ineff_min_acos,
    "ineff_min_spend": ineff_min_spend,
    "waste_min_spend": waste_min_spend,
}

# ─── Filter & classify ────────────────────────────────────────────────────────
filtered = merged[merged["Portfolio"].isin(selected_portfs)].copy() if selected_portfs else merged.copy()
filtered["Status"] = filtered.apply(lambda r: classify(r, thresholds), axis=1)
filtered = filtered.sort_values("Status", key=lambda x: x.map(STATUS_ORDER))

# WoW: classify previous period with same thresholds & portfolio filter
if has_wow:
    filtered_prev = (
        merged_prev[merged_prev["Portfolio"].isin(selected_portfs)].copy()
        if selected_portfs else merged_prev.copy()
    )
    filtered_prev["Status"] = filtered_prev.apply(lambda r: classify(r, thresholds), axis=1)
    wow_df = build_wow_df(filtered, filtered_prev)
else:
    filtered_prev = None
    wow_df = None

# ─── Sidebar: Google Sheets save ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown(
        f"<p style='font-family:Poppins,sans-serif;font-size:12px;font-weight:700;"
        f"color:#B8DBD9;margin-bottom:8px;'>💾 Save to Google Sheets</p>",
        unsafe_allow_html=True,
    )
    _sheet_input = st.text_input(
        "Google Sheet URL or ID",
        value=SHEET_ID,
        key="gs_sheet",
        help="Paste your own Google Sheet URL to save there instead",
    )
    st.caption(
        f"To save to your own sheet: create a Google Sheet, share it as **Editor** with "
        f"`{_service_account_email()}`, then paste the sheet's URL above."
    )
    if st.button("Save uploaded data", use_container_width=True, key="gs_save"):
        if _KEY_FILE.exists():
            with st.spinner("Saving to Google Sheets…"):
                try:
                    _ts, _saved_tabs = save_to_sheets(
                        _extract_sheet_id(_sheet_input),
                        sqpa_bytes, stis_bytes,
                        sqpa_prev_bytes, stis_prev_bytes,
                    )
                    st.success(f"Saved at {_ts} — tabs: {', '.join(_saved_tabs)}")
                except Exception as _e:
                    st.error(f"Save failed: {_e}")
        else:
            st.error("Key file not found. Place growisto-sheets-key.json in the app folder.")

# ─── KPI summary ──────────────────────────────────────────────────────────────
working     = int((filtered["Status"] == "Working").sum())
wasted      = int((filtered["Status"] == "Wasted Spend").sum())
opportunity = int((filtered["Status"] == "Opportunity").sum())
inefficient = int((filtered["Status"] == "Inefficient").sum())
total_spend = filtered["Spend"].sum()
total_sales = filtered["Sales"].sum()
overall_acos = (total_spend / total_sales * 100) if total_sales > 0 else None

st.markdown(
    f"<span style='font-family:Poppins,sans-serif;color:{RAISIN_BLACK};font-size:13px;'>"
    f"<b>SQPA period:</b> {sqpa_period} &nbsp;·&nbsp; "
    f"<b>STIS period:</b> {stis_range} &nbsp;·&nbsp; "
    f"<b>{len(filtered):,}</b> keywords tracked</span>",
    unsafe_allow_html=True,
)
st.markdown("")

_kpi_items = [
    ("Total KWs",       f"{len(filtered):,}",              TEAL_BLUE),
    ("✅ Working",      f"{working:,}",                    "#00A650"),
    ("💸 Wasted Spend", f"{wasted:,}",                     "#E53E3E"),
    ("💡 Opportunity",  f"{opportunity:,}",                "#D4860A"),
    ("⚠️ Inefficient",  f"{inefficient:,}",                FLAME),
    ("Total Spend",     f"{CUR}{total_spend:,.0f}",        TEAL_BLUE),
    ("Overall ACOS",    f"{overall_acos:.1f}%" if overall_acos else "N/A", TEAL_BLUE),
]
_kpi_cards = "".join(
    f"<div style='flex:1;background:{POWDER_BLUE};border-left:4px solid {color};"
    f"padding:10px 14px;border-radius:0 8px 8px 0;min-width:0;'>"
    f"<div style='font-family:Poppins,sans-serif;font-size:11px;font-weight:600;"
    f"color:{RAISIN_BLACK};white-space:nowrap;margin-bottom:3px;'>{label}</div>"
    f"<div style='font-family:Poppins,sans-serif;font-size:20px;font-weight:700;"
    f"color:{color};white-space:nowrap;'>{value}</div>"
    f"</div>"
    for label, value, color in _kpi_items
)
st.markdown(
    f"<div style='display:flex;gap:8px;margin-bottom:4px;'>{_kpi_cards}</div>",
    unsafe_allow_html=True,
)

st.markdown("---")

# ─── Keyword tabs ─────────────────────────────────────────────────────────────
_tab_labels = [
    f"All Keywords ({len(filtered):,})",
    f"✅ Working ({working})",
    f"💸 Wasted Spend ({wasted})",
    f"💡 Opportunity ({opportunity})",
    f"⚠️ Inefficient ({inefficient})",
]
if has_wow:
    _tab_labels.append("📊 Week-on-Week")
_all_tabs = st.tabs(_tab_labels)
tab_all, tab_work, tab_waste, tab_opp, tab_ineff = _all_tabs[:5]

with tab_all:
    show_kw_table(filtered, camp_agg, tab_key="all")

with tab_work:
    show_kw_table(
        filtered[filtered["Status"] == "Working"].sort_values("Sales", ascending=False),
        camp_agg, tab_key="working",
    )

with tab_waste:
    st.caption(f"Spend ≥ {CUR}{waste_min_spend:.0f} with {CUR}0 sales — review bids or pause.")
    show_kw_table(
        filtered[filtered["Status"] == "Wasted Spend"].sort_values("Spend", ascending=False),
        camp_agg, tab_key="wasted",
    )

with tab_opp:
    st.caption(
        f"SQV ≥ {opp_min_sqv:,} and brand IS < {opp_max_is}% — "
        f"brand is underrepresented; increase bids or add to campaigns."
    )
    show_kw_table(
        filtered[filtered["Status"] == "Opportunity"].sort_values("SQV", ascending=False),
        camp_agg, tab_key="opportunity",
    )

with tab_ineff:
    st.caption(
        f"Sales > {CUR}0, ACOS > {ineff_min_acos:.0f}%, Spend ≥ {CUR}{ineff_min_spend:.0f} — "
        f"converting but above target; optimise bids."
    )
    show_kw_table(
        filtered[filtered["Status"] == "Inefficient"].sort_values("ACOS", ascending=False),
        camp_agg, tab_key="inefficient",
    )

if has_wow:
    with _all_tabs[5]:
        show_wow_tab(
            wow_df, filtered, filtered_prev,
            sqpa_period, sqpa_prev_period,
            stis_range, stis_prev_range,
        )
