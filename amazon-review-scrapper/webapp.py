"""
Amazon India Review Scraper — Web UI (V1)
Run with:  streamlit run webapp.py
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
SCRAPER     = SCRIPT_DIR / "scraper.py"
EXPORTS_DIR = SCRIPT_DIR / "exports"
PROFILE_DIR = SCRIPT_DIR / ".browser_profile"

STAR_OPTIONS = {
    "All stars"          : "all",
    "⭐⭐⭐⭐⭐  5 stars": "5",
    "⭐⭐⭐⭐    4 stars": "4",
    "⭐⭐⭐      3 stars": "3",
    "⭐⭐        2 stars": "2",
    "⭐          1 star" : "1",
}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Amazon India Review Scraper",
    page_icon="🛒",
    layout="centered",
)

# ── Growisto Brand CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');

/* ── Base: Poppins everywhere, Cultured background ── */
html, body, [class*="css"], .stApp {
    font-family: 'Poppins', sans-serif !important;
    background-color: #F6F6F4 !important;
}
.block-container {
    padding-top: 1.5rem !important;
    background-color: #F6F6F4 !important;
}

/* ── Typography ── */
h1, h2, h3, h4 {
    font-family: 'Poppins', sans-serif !important;
    color: #1D1D20 !important;
}
p, li, span, label, div {
    font-family: 'Poppins', sans-serif !important;
}

/* ── Sidebar: Teal Blue ── */
section[data-testid="stSidebar"] {
    background-color: #367588 !important;
}
section[data-testid="stSidebar"] > div {
    background-color: #367588 !important;
}
section[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
    font-family: 'Poppins', sans-serif !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(184,219,217,0.35) !important;
}
section[data-testid="stSidebar"] .stSelectbox > div > div {
    background-color: rgba(255,255,255,0.15) !important;
    border-color: rgba(184,219,217,0.5) !important;
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] .stCheckbox > label {
    color: #FFFFFF !important;
}
/* Sidebar success/warning override */
section[data-testid="stSidebar"] .stAlert {
    background-color: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(184,219,217,0.4) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent !important;
    border-bottom: 2px solid #B8DBD9 !important;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.95rem !important;
    color: #1D1D20 !important;
    padding: 0.6rem 1.2rem !important;
    border-radius: 6px 6px 0 0 !important;
    background-color: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover {
    background-color: rgba(54,117,136,0.07) !important;
    color: #367588 !important;
}
.stTabs [aria-selected="true"] {
    font-weight: 700 !important;
    color: #367588 !important;
    border-bottom: 3px solid #367588 !important;
    background-color: rgba(54,117,136,0.08) !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background-color: #F6F6F4 !important;
    padding-top: 1.5rem !important;
}

/* ── Primary buttons: Flame ── */
.stButton > button,
.stDownloadButton > button {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
.stButton > button[data-testid*="primary"],
.stDownloadButton > button[data-testid*="primary"] {
    background-color: #E35D34 !important;
    color: #FFFFFF !important;
    border: none !important;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {
    background-color: #c94f2a !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(227,93,52,0.3) !important;
}
/* Secondary / default buttons */
.stButton > button:not([kind="primary"]),
.stDownloadButton > button:not([kind="primary"]) {
    background-color: #FFFFFF !important;
    color: #367588 !important;
    border: 1.5px solid #B8DBD9 !important;
}
.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:not([kind="primary"]):hover {
    border-color: #367588 !important;
    background-color: rgba(54,117,136,0.05) !important;
}

/* ── Text input ── */
.stTextInput > div > div > input {
    font-family: 'Poppins', sans-serif !important;
    color: #1D1D20 !important;
    border-color: #B8DBD9 !important;
    border-radius: 8px !important;
    background-color: #FFFFFF !important;
}
.stTextInput > div > div > input:focus {
    border-color: #367588 !important;
    box-shadow: 0 0 0 2px rgba(54,117,136,0.18) !important;
}

/* ── Select box ── */
.stSelectbox > div > div {
    border-color: #B8DBD9 !important;
    border-radius: 8px !important;
    background-color: #FFFFFF !important;
    color: #1D1D20 !important;
    font-family: 'Poppins', sans-serif !important;
}

/* ── Divider ── */
hr {
    border-color: #B8DBD9 !important;
}

/* ── Alerts ── */
div[data-testid="stAlert"][data-baseweb*="notification"] {
    border-radius: 8px !important;
    font-family: 'Poppins', sans-serif !important;
}

/* ── Expander (FAQ) ── */
.streamlit-expanderHeader, details > summary {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 600 !important;
    color: #367588 !important;
    background-color: #FFFFFF !important;
    border: 1px solid #B8DBD9 !important;
    border-radius: 8px !important;
}
.streamlit-expanderContent, details > div {
    background-color: #FFFFFF !important;
    border: 1px solid #B8DBD9 !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    padding: 0.8rem 1rem !important;
}

/* ── Captions / small text ── */
.stCaption, small {
    color: rgba(29,29,32,0.6) !important;
    font-family: 'Poppins', sans-serif !important;
}

/* ── Code blocks ── */
code {
    background-color: rgba(54,117,136,0.1) !important;
    color: #367588 !important;
    border-radius: 4px !important;
    padding: 0.1rem 0.3rem !important;
    font-size: 0.88em !important;
}
pre code {
    background-color: #1D1D20 !important;
    color: #B8DBD9 !important;
}

/* ── Log box ── */
.log-box {
    background: #1D1D20;
    color: #B8DBD9;
    font-family: 'Courier New', monospace !important;
    font-size: 13px;
    padding: 1rem;
    border-radius: 8px;
    max-height: 340px;
    overflow-y: auto;
    white-space: pre-wrap;
    border: 1px solid #367588;
}

/* ── Brand info cards ── */
.do-box {
    background: #eaf4f3;
    border-left: 4px solid #367588;
    padding: 0.75rem 1rem;
    border-radius: 0 8px 8px 0;
    margin-bottom: 0.5rem;
    color: #1D1D20 !important;
    font-family: 'Poppins', sans-serif !important;
    font-size: 0.88rem;
}
.dont-box {
    background: #fce9e2;
    border-left: 4px solid #E35D34;
    padding: 0.75rem 1rem;
    border-radius: 0 8px 8px 0;
    margin-bottom: 0.5rem;
    color: #1D1D20 !important;
    font-family: 'Poppins', sans-serif !important;
    font-size: 0.88rem;
}
.step-box {
    background: #FFFFFF;
    border-left: 4px solid #367588;
    padding: 0.75rem 1rem;
    border-radius: 0 8px 8px 0;
    margin-bottom: 0.5rem;
    color: #1D1D20 !important;
    font-family: 'Poppins', sans-serif !important;
    font-size: 0.88rem;
    box-shadow: 0 1px 4px rgba(54,117,136,0.08);
}
.info-box {
    background: #B8DBD9;
    border-left: 4px solid #367588;
    padding: 0.75rem 1rem;
    border-radius: 0 8px 8px 0;
    margin-bottom: 0.5rem;
    color: #1D1D20 !important;
    font-family: 'Poppins', sans-serif !important;
    font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)

# ── Branded Header ────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    background: linear-gradient(135deg, #367588 0%, #2a5d6e 100%);
    padding: 1.4rem 1.8rem;
    border-radius: 12px;
    margin-bottom: 1.2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
">
    <div style="font-size:2rem;">🛒</div>
    <div>
        <div style="color:#FFFFFF;font-family:Poppins,sans-serif;font-size:1.4rem;
                    font-weight:800;line-height:1.2;margin-bottom:0.2rem;">
            Amazon India Review Scraper
        </div>
        <div style="color:#B8DBD9;font-family:Poppins,sans-serif;font-size:0.82rem;font-weight:500;">
            V1 &nbsp;·&nbsp; Amazon India only &nbsp;·&nbsp; Scrapes all written reviews for any product ASIN
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='font-family:Poppins,sans-serif;font-size:1rem;"
        "font-weight:700;color:#FFFFFF;margin-bottom:0.8rem;'>⚙️ Settings</div>",
        unsafe_allow_html=True,
    )

    star_label = st.selectbox("Star filter", list(STAR_OPTIONS.keys()), index=0)
    headless   = st.checkbox(
        "Headless mode (hide Chrome)",
        value=False,
        help="Tick this only after you have signed in at least once. "
             "First run must have Chrome visible so you can sign in."
    )

    st.divider()

    profile_exists = PROFILE_DIR.is_dir()
    if profile_exists:
        st.success("✅ Session saved\nNo sign-in needed for this run.")
    else:
        st.warning(
            "⚠️ No saved session\n\n"
            "Chrome will open when you scrape.\n"
            "Sign in with your burner amazon.in account — saves automatically."
        )

    st.divider()
    st.markdown(
        "<div style='font-weight:600;color:#FFFFFF;font-family:Poppins,sans-serif;"
        "margin-bottom:0.4rem;'>How to find an ASIN</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "Open any Amazon India product page.\n\n"
        "The ASIN is the **10-character code** after `/dp/` in the URL.\n\n"
        "Example:\n`amazon.in/dp/`**`B0FJY1CKMG`**"
    )
    st.divider()
    st.caption("V1 — India marketplace · Growisto Internal Tool")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_scraper, tab_guide = st.tabs(["🔍 Scraper", "📖 Guide"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scraper:

    col1, col2 = st.columns([3, 1])
    with col1:
        asin = st.text_input(
            "Product ASIN",
            placeholder="e.g. B0FJY1CKMG",
            max_chars=10,
            label_visibility="collapsed",
        ).strip().upper()
    with col2:
        scrape_btn = st.button("🔍 Scrape", type="primary", use_container_width=True)

    if asin and len(asin) != 10:
        st.caption(f"⚠️ ASIN must be exactly 10 characters — you've entered {len(asin)}")

    st.divider()

    if scrape_btn:
        if not asin or len(asin) != 10:
            st.error("Please enter a valid 10-character ASIN before scraping.")
            st.stop()

        star_value = STAR_OPTIONS[star_label]
        cmd = [sys.executable, str(SCRAPER), asin, "--stars", star_value]
        if headless:
            cmd.append("--headless")

        st.subheader(f"Scraping: `{asin}`")

        log_placeholder = st.empty()
        output_lines    = []
        success         = False

        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SCRIPT_DIR),
        ) as proc:
            for raw_line in proc.stdout:
                line = raw_line.rstrip()
                if line:
                    output_lines.append(line)
                    log_placeholder.markdown(
                        "<div class='log-box'>" +
                        "\n".join(output_lines[-30:]).replace("<", "&lt;") +
                        "</div>",
                        unsafe_allow_html=True,
                    )
            proc.wait()
            success = proc.returncode == 0

        if success:
            output_file = EXPORTS_DIR / f"reviews_{asin}_in.xlsx"
            if output_file.exists():
                st.success(f"✅ Done! All reviews scraped for **{asin}**.")
                with open(output_file, "rb") as f:
                    st.download_button(
                        label="📥 Download Excel",
                        data=f.read(),
                        file_name=output_file.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True,
                    )
            else:
                st.warning("Scraper finished but the output file wasn't found. Try again.")
        else:
            st.error("❌ Scraping failed or no reviews were found. Check the log above.")

    # Past scrapes
    EXPORTS_DIR.mkdir(exist_ok=True)
    past_files = sorted(
        [f for f in EXPORTS_DIR.glob("reviews_*_in.xlsx")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if past_files:
        st.markdown(
            "<div style='font-size:1rem;font-weight:700;color:#1D1D20;"
            "font-family:Poppins,sans-serif;margin-bottom:0.8rem;'>📂 Previous Scrapes</div>",
            unsafe_allow_html=True,
        )
        for xlsx in past_files[:10]:
            asin_part = xlsx.stem.split("_")[1] if "_" in xlsx.stem else xlsx.stem
            mod_time  = datetime.fromtimestamp(xlsx.stat().st_mtime).strftime("%d %b %Y, %I:%M %p")
            size_kb   = round(xlsx.stat().st_size / 1024, 1)

            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(
                    f"<div style='font-family:Poppins,sans-serif;font-size:0.88rem;"
                    f"color:#1D1D20;padding:0.4rem 0;'>"
                    f"<strong style='color:#367588;'>{asin_part}</strong>"
                    f" &nbsp;·&nbsp; {mod_time} &nbsp;·&nbsp; {size_kb} KB</div>",
                    unsafe_allow_html=True,
                )
            with col_b:
                with open(xlsx, "rb") as f:
                    st.download_button(
                        label="Download",
                        data=f.read(),
                        file_name=xlsx.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=str(xlsx),
                        use_container_width=True,
                    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — GUIDE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_guide:

    # ── What is this tool ──────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.1rem;font-weight:700;color:#367588;"
        "font-family:Poppins,sans-serif;margin-bottom:0.6rem;'>📌 What is this tool?</div>",
        unsafe_allow_html=True,
    )
    st.markdown("""
This is an **internal Growisto tool** that scrapes all written customer reviews from
any Amazon India product and exports them into an Excel file.

It works by logging into a dedicated burner Amazon account, navigating to the product's
review pages across all star ratings, and collecting every written review —
all automatically, in the background.

**What you get in the Excel file:**
- Reviewer name
- Star rating (1–5)
- Review title
- Review date
- Full review text
- Verified Purchase status
- Helpful votes count
""")

    st.divider()

    # ── Dos and Don'ts ─────────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.1rem;font-weight:700;color:#367588;"
        "font-family:Poppins,sans-serif;margin-bottom:0.6rem;'>✅ Dos and ❌ Don'ts</div>",
        unsafe_allow_html=True,
    )

    col_do, col_dont = st.columns(2)

    with col_do:
        st.markdown(
            "<div style='font-weight:600;color:#367588;font-family:Poppins,sans-serif;"
            "margin-bottom:0.5rem;'>✅ Do this</div>",
            unsafe_allow_html=True,
        )
        for item in [
            "Use a dedicated burner amazon.in account — never your personal account",
            "Create a fresh Gmail address for each burner Amazon account",
            "Sign in once and let the session save — reuse it for all future scrapes",
            "Scrape one ASIN at a time for reliable results",
            "Close the Excel file before re-scraping the same ASIN",
            "Use headless mode (hide Chrome) after your first successful sign-in",
            "If Amazon asks for OTP or passkey setup — complete it or dismiss it in the Chrome window",
            "Run the tool during normal working hours for best results",
        ]:
            st.markdown(f"<div class='do-box'>✅ {item}</div>", unsafe_allow_html=True)

    with col_dont:
        st.markdown(
            "<div style='font-weight:600;color:#E35D34;font-family:Poppins,sans-serif;"
            "margin-bottom:0.5rem;'>❌ Don't do this</div>",
            unsafe_allow_html=True,
        )
        for item in [
            "Never use your personal Amazon account — use only burner accounts",
            "Don't add a credit card or real address to the burner account",
            "Don't share your burner account credentials with anyone else",
            "Don't run multiple scrapes simultaneously — do them one at a time",
            "Don't close the Chrome window while it is signing in",
            "Don't delete the .browser_profile folder — it stores your session",
            "Don't use the same burner account across multiple team members",
            "Don't scrape more than 50–60 ASINs per day from one account",
        ]:
            st.markdown(f"<div class='dont-box'>❌ {item}</div>", unsafe_allow_html=True)

    st.divider()

    # ── Burner account setup ───────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.1rem;font-weight:700;color:#367588;"
        "font-family:Poppins,sans-serif;margin-bottom:0.6rem;'>📧 How to create a burner Amazon.in account</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>⚠️ <strong>Important:</strong> Each team member must have their own "
        "separate burner account. Never share accounts.</div>",
        unsafe_allow_html=True,
    )

    for i, step in enumerate([
        ("Create a new email address",
         "Go to Gmail or Outlook and create a fresh email — something like <code>scraper.work.yourname@gmail.com</code>. "
         "Do NOT use your work or personal email."),
        ("Go to amazon.in/register",
         "Open amazon.in in your browser and click <strong>Create your Amazon account</strong>."),
        ("Fill in the details",
         "Use your new email, a made-up name, and create a password. Write these down in your password manager."),
        ("Verify with OTP",
         "Amazon will send an OTP to your email. Enter it to complete registration."),
        ("Skip everything else",
         "Do NOT add a phone number, credit card, address, or any other information. "
         "Close any prompts asking for these."),
        ("You're done",
         "Your burner account is ready. Use it only for this scraper tool."),
    ], 1):
        title, detail = step
        st.markdown(
            f"<div class='step-box'><strong>Step {i}: {title}</strong><br>{detail}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── How to find an ASIN ────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.1rem;font-weight:700;color:#367588;"
        "font-family:Poppins,sans-serif;margin-bottom:0.6rem;'>🔍 How to find an ASIN</div>",
        unsafe_allow_html=True,
    )
    st.markdown("""
An **ASIN** (Amazon Standard Identification Number) is a unique 10-character code
for every product on Amazon. It's always in the product page URL.

**Method 1 — From the URL:**
```
https://www.amazon.in/dp/B0FJY1CKMG
                          ^^^^^^^^^^
                          This is the ASIN
```

**Method 2 — From the product page:**
Scroll down to the **Product Information** section on any Amazon product page.
You'll see "ASIN" listed as a field with the 10-character code next to it.

**Rules:**
- Always exactly 10 characters
- Starts with `B0` for most products
- Mix of letters and numbers (e.g. `B0FJY1CKMG`)
""")

    st.divider()

    # ── How to install ────────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.1rem;font-weight:700;color:#367588;"
        "font-family:Poppins,sans-serif;margin-bottom:0.6rem;'>💻 How to install and run on your machine</div>",
        unsafe_allow_html=True,
    )

    install_mac, install_win = st.tabs(["🍎 Mac", "🪟 Windows"])

    with install_mac:
        st.markdown(
            "<div style='font-weight:600;font-family:Poppins,sans-serif;"
            "margin-bottom:0.6rem;'>One-time setup (takes ~5 minutes):</div>",
            unsafe_allow_html=True,
        )
        for i, step in enumerate([
            ("Download the installer",
             "Visit the download page shared by your admin. Click <strong>Download for Mac</strong> "
             "to get the zip file."),
            ("Extract the zip",
             "Double-click the downloaded zip to extract the folder."),
            ("Run the installer",
             "Open Terminal. Drag <code>install-mac.command</code> from the extracted folder "
             "into the Terminal window, then press Enter. "
             "If blocked by macOS: System Settings → Privacy & Security → click <strong>Open Anyway</strong>."),
            ("Wait for setup to complete",
             "A terminal window installs everything automatically "
             "(Python packages, Chrome). Takes 3–5 minutes. Don't close it."),
            ("Launch the app",
             "Double-click <strong>Amazon Scraper</strong> on your Desktop → "
             "your browser opens at <code>http://localhost:8501</code> with this exact page."),
        ], 1):
            title, detail = step
            st.markdown(
                f"<div class='step-box'><strong>Step {i}: {title}</strong><br>{detail}</div>",
                unsafe_allow_html=True,
            )

    with install_win:
        st.markdown(
            "<div style='font-weight:600;font-family:Poppins,sans-serif;"
            "margin-bottom:0.6rem;'>One-time setup (takes ~5 minutes):</div>",
            unsafe_allow_html=True,
        )
        for i, step in enumerate([
            ("Download the installer",
             "Visit the download page shared by your admin. Click <strong>Download for Windows</strong> "
             "to get the zip file."),
            ("Extract the zip",
             "Right-click the downloaded zip → <strong>Extract All</strong> → choose a folder."),
            ("Run the installer",
             "Inside the extracted folder, right-click <code>install-windows.bat</code> → "
             "<strong>Run as administrator</strong>. "
             "If Windows Defender shows a warning, click <strong>More info → Run anyway</strong>."),
            ("Wait for setup to complete",
             "A terminal window installs everything automatically. "
             "Takes 3–5 minutes. Don't close it."),
            ("Launch the app",
             "Double-click <strong>Amazon Scraper</strong> on your Desktop → "
             "your browser opens at <code>http://localhost:8501</code> with this exact page."),
        ], 1):
            title, detail = step
            st.markdown(
                f"<div class='step-box'><strong>Step {i}: {title}</strong><br>{detail}</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── How to use ────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.1rem;font-weight:700;color:#367588;"
        "font-family:Poppins,sans-serif;margin-bottom:0.6rem;'>🚀 How to use the scraper</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='font-weight:600;font-family:Poppins,sans-serif;margin-bottom:0.5rem;'>"
        "First time only — Sign in to Amazon:</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='info-box'>The first time you scrape, Chrome will open automatically "
        "and show the Amazon sign-in page. Sign in with your burner amazon.in account. "
        "The session saves automatically — you will never need to sign in again "
        "unless Amazon logs you out (which happens every few weeks).</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='font-weight:600;font-family:Poppins,sans-serif;"
        "margin:0.8rem 0 0.5rem;'>Every time — Scraping reviews:</div>",
        unsafe_allow_html=True,
    )
    for i, step in enumerate([
        ("Find the ASIN", "Go to the Amazon India product page and copy the ASIN from the URL (see above)."),
        ("Open the scraper", "Double-click the Amazon Scraper shortcut on your Desktop."),
        ("Enter the ASIN", "Paste the ASIN into the input box on the Scraper tab."),
        ("Choose a star filter", "Leave it on 'All stars' to get every review, or pick a specific rating."),
        ("Click Scrape", "Hit the 🔍 Scrape button. Progress appears live on screen."),
        ("Download the file", "When done, click 📥 Download Excel to save the file to your computer."),
    ], 1):
        title, detail = step
        st.markdown(
            f"<div class='step-box'><strong>Step {i}: {title}</strong><br>{detail}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── FAQs ──────────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.1rem;font-weight:700;color:#367588;"
        "font-family:Poppins,sans-serif;margin-bottom:0.8rem;'>❓ FAQs</div>",
        unsafe_allow_html=True,
    )

    faqs = [
        ("How many reviews can I get per product?",
         "You get all written reviews available on Amazon India for that product across all star ratings. "
         "Note: not all ratings have written text — some customers just click a star without writing anything. "
         "Those are not included."),
        ("Why does Chrome open when I scrape?",
         "The first time, Chrome needs to open so you can sign into your burner Amazon account. "
         "After that, tick 'Headless mode' in the sidebar and Chrome will run invisibly in the background."),
        ("Amazon is asking me to sign in again — what do I do?",
         "Amazon sessions expire every few weeks. When this happens, uncheck 'Headless mode', "
         "run a scrape, and sign in again in the Chrome window that opens. "
         "Your session will be saved again automatically."),
        ("Why is it showing a passkey setup / OTP screen?",
         "Amazon occasionally asks for extra verification. Complete or dismiss the prompt in "
         "the Chrome window — the scraper will wait up to 5 minutes for you to finish."),
        ("The Excel file has fewer reviews than shown on Amazon — why?",
         "Amazon shows a 'ratings' count (people who clicked a star) and a 'reviews' count "
         "(people who wrote text). This tool only collects written reviews. "
         "The gap between the two numbers is normal."),
        ("Can I scrape multiple ASINs at the same time?",
         "No — do them one at a time. Running multiple scrapes simultaneously increases "
         "the chance of Amazon flagging your account."),
        ("My previous scrape file got overwritten — how do I avoid this?",
         "Close the Excel file before starting a new scrape for the same ASIN. "
         "You can also find older files in the Previous Scrapes section at the bottom of the Scraper tab."),
        ("Can I use this for Amazon US or UK products?",
         "Not in V1 — this tool is India-only. International marketplace support is planned for V2."),
    ]

    for q, a in faqs:
        with st.expander(f"❓ {q}"):
            st.markdown(a)

    st.divider()
    st.markdown(
        "<div style='text-align:center;font-size:0.78rem;color:rgba(29,29,32,0.5);"
        "font-family:Poppins,sans-serif;padding:0.5rem 0;'>"
        "Amazon India Review Scraper · V1 · Internal Growisto Tool · Do not share outside the team"
        "</div>",
        unsafe_allow_html=True,
    )
