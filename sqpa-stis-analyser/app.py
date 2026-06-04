"""
Keyword-Level Organic Tracker
Combines SQPA (Brand Analytics) + STIS (Ads Impression Share) reports.
"""

import base64
import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
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
    try:
        year  = str(raw.iloc[0, 2]).replace('Select year=["', "").replace('"]', "").strip()
        month = str(raw.iloc[0, 3]).replace('Select month=["', "").replace('"]', "").strip()
        period = f"{month} {year}"
    except Exception:
        period = str(raw.iloc[0, 0]) if not raw.empty else ""

    return df[["Keyword", "SQV", "IS", "CS", "ATC", "PS"]].copy(), period


@st.cache_data(show_spinner=False)
def load_stis(file_bytes: bytes):
    df = pd.read_csv(io.BytesIO(file_bytes))
    df.columns = df.columns.str.strip()

    def strip_dollar(s):
        return pd.to_numeric(
            s.astype(str).str.replace("$", "", regex=False)
                          .str.replace(",", "", regex=False).str.strip(),
            errors="coerce",
        )

    df["Spend"]       = strip_dollar(df["Spend"])
    df["Sales"]       = strip_dollar(df["7 Day Total Sales"])
    df["Clicks"]      = pd.to_numeric(df["Clicks"], errors="coerce")
    df["Impressions"] = pd.to_numeric(df["Impressions"], errors="coerce")
    df["Orders"]      = pd.to_numeric(df["7 Day Total Orders (#)"], errors="coerce")
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

    return kw_agg, camp_agg


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
    d["Spend"]              = d["Spend"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "–")
    d["Sales"]              = d["Sales"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "–")
    d["ACOS"]               = d["ACOS"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "–")
    d["Status"]             = d["Status"].map(STATUS_LABEL)
    return d[["Keyword", "Portfolio", "SQV",
              "Brand Impr. Share", "Brand Click Share", "Brand ATC Share", "Brand Purch. Share",
              "Spend", "Sales", "ACOS", "Status"]]


def _fmt_camp(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["Spend"]                = d["Spend"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "–")
    d["Sales"]                = d["Sales"].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "–")
    d["ACOS"]                 = d["ACOS"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "–")
    d["Impressions"]          = d["Impressions"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "–")
    d["Clicks"]               = d["Clicks"].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "–")
    d["CTR"]                  = d["CTR"].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "–")
    d["CPC"]                  = d["CPC"].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "–")
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
        ("Total Spend",       f"${r['Spend']:,.2f}"  if pd.notna(r['Spend']) else "–"),
        ("Total Sales",       f"${r['Sales']:,.2f}"  if pd.notna(r['Sales']) else "–"),
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
    u1, u2 = st.columns(2)
    with u1:
        st.markdown("**SQPA Report** — Brand Analytics → Search Query Performance")
        sqpa_file = st.file_uploader("SQPA CSV", type=["csv"], label_visibility="collapsed", key="sqpa")
    with u2:
        st.markdown("**STIS Report** — Ads Console → Search Term Impression Share")
        stis_file = st.file_uploader("STIS CSV", type=["csv"], label_visibility="collapsed", key="stis")

if sqpa_file is None or stis_file is None:
    st.info("Upload both reports above to activate the tracker.", icon="ℹ️")
    st.stop()

# ─── Load data ────────────────────────────────────────────────────────────────
with st.spinner("Processing reports…"):
    sqpa_df, sqpa_period = load_sqpa(sqpa_file.read())
    kw_agg, camp_agg     = load_stis(stis_file.read())

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
        work_min_sales = st.slider("Min Sales ($)", 0.0, 500.0,  0.0, 5.0, key="w_sales",
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
        ineff_min_spend = st.slider("Min Spend ($)", 0.0, 200.0,  5.0, 1.0, key="i_spend",
                                     help="Only flag if spending at least this amount")

    with t4:
        st.markdown(
            f"<p style='font-family:Poppins,sans-serif;font-size:12px;font-weight:700;"
            f"color:{TEAL_BLUE};margin-bottom:6px;'>💸 Wasted Spend</p>",
            unsafe_allow_html=True,
        )
        waste_min_spend = st.slider("Min Spend ($)", 0.0, 200.0, 5.0, 1.0, key="ws_spend",
                                     help="Flag keywords spending this with $0 in sales")

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
    ("Total Spend",     f"${total_spend:,.0f}",            TEAL_BLUE),
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
tab_all, tab_work, tab_waste, tab_opp, tab_ineff = st.tabs([
    f"All Keywords ({len(filtered):,})",
    f"✅ Working ({working})",
    f"💸 Wasted Spend ({wasted})",
    f"💡 Opportunity ({opportunity})",
    f"⚠️ Inefficient ({inefficient})",
])

with tab_all:
    show_kw_table(filtered, camp_agg, tab_key="all")

with tab_work:
    show_kw_table(
        filtered[filtered["Status"] == "Working"].sort_values("Sales", ascending=False),
        camp_agg, tab_key="working",
    )

with tab_waste:
    st.caption(f"Spend ≥ ${waste_min_spend:.0f} with $0 sales — review bids or pause.")
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
        f"Sales > $0, ACOS > {ineff_min_acos:.0f}%, Spend ≥ ${ineff_min_spend:.0f} — "
        f"converting but above target; optimise bids."
    )
    show_kw_table(
        filtered[filtered["Status"] == "Inefficient"].sort_values("ACOS", ascending=False),
        camp_agg, tab_key="inefficient",
    )
