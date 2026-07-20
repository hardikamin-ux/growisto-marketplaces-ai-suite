import json, time, sys, os, shutil, random
from datetime import datetime
from urllib.parse import quote_plus

# ── Virtual display (Linux/Render only) ───────────────────────────────────────
# On Render (Linux), we use Xvfb so Chrome runs with a real virtual screen —
# Amazon's Intersection Observer fires and SB/SBV ads render, but nothing is
# ever visible to any user.  On Mac (local dev) this block is simply skipped.
_VIRTUAL_DISPLAY = None
if sys.platform.startswith("linux"):
    try:
        from pyvirtualdisplay import Display
        _VIRTUAL_DISPLAY = Display(visible=False, size=(1440, 900))
        _VIRTUAL_DISPLAY.start()
        print("Virtual display started (Xvfb)")
    except Exception as _vd_err:
        print(f"pyvirtualdisplay not available, running without virtual display: {_vd_err}")

BASE          = os.path.dirname(os.path.abspath(__file__))
# Per-user workspace: app.py passes a session directory as argv[1] so multiple
# people can scrape simultaneously without sharing config/progress/results.
WORKSPACE     = sys.argv[1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]) else BASE
PROGRESS_FILE = os.path.join(WORKSPACE, "progress.json")

def _fatal(msg):
    """Write error to progress.json and exit — called before full imports succeed."""
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump({"status": "error", "message": msg}, f)
    except Exception:
        pass
    print("FATAL:", msg, file=sys.stderr)
    sys.exit(1)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        StaleElementReferenceException, NoSuchElementException, TimeoutException
    )
    from selenium_stealth import stealth
    from webdriver_manager.chrome import ChromeDriverManager
except ModuleNotFoundError as e:
    _fatal(f"Missing package: {e}. Run: python3 -m pip install selenium selenium-stealth webdriver-manager")

DATA_FILE   = os.path.join(WORKSPACE, "serp_data.json")
CONFIG_FILE  = os.path.join(WORKSPACE, "config.json")
HISTORY_DIR  = os.path.join(WORKSPACE, "history", "data")

# Longer timeouts on Linux/Render (slower server), shorter on Mac (local dev)
WAIT_TIMEOUT = 30 if sys.platform.startswith("linux") else 15
SCROLL_WAIT  = 3.5 if sys.platform.startswith("linux") else 2.5

# ── File I/O ──────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def write_progress(status, geo="", keyword="", keyword_index=0,
                   total_keywords=0, sp=0, organic=0, sb=0, sbv=0,
                   skipped=0, message="", sub_message=""):
    payload = {
        "status":         status,
        "geo":            geo,
        "keyword":        keyword,
        "keyword_index":  keyword_index,
        "total_keywords": total_keywords,
        "sp":             sp,
        "organic":        organic,
        "sb":             sb,
        "sbv":            sbv,
        "skipped":        skipped,
        "message":        message,
        "sub_message":    sub_message,
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(payload, f)

def archive_data():
    """Copy current serp_data.json to history/data/ with today's timestamp."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        return
    ts   = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest = os.path.join(HISTORY_DIR, f"serp_data_{ts}.json")
    shutil.copy2(DATA_FILE, dest)
    print(f"  Archived previous data → {dest}")

# ── Browser ───────────────────────────────────────────────────────────────────

def create_driver():
    opts = Options()
    # Amazon's SB banner system (Aetheris/CSA) uses Intersection Observer — it only
    # renders ad creatives when the container is visible in the viewport.
    # --headless=new and off-screen (-32000,-32000) both cause the IO to never fire,
    # so banners stay empty.  Solution: run Chrome normally but immediately move the
    # window off the bottom-right of the screen so it's out of the way.
    # The window is still "alive" to the OS so ads render normally.
    opts.add_argument("--window-size=1440,900")
    # Incognito — no cookies, no personalisation
    opts.add_argument("--incognito")
    # Fresh throwaway profile per run — guarantees a never-signed-in, zero-history
    # browser even if incognito behaviour differs across Chrome versions. Nothing
    # can persist between scrapes, so results carry no personalisation bias.
    import tempfile
    opts.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='serp_profile_')}")
    opts.add_argument("--disable-sync")
    # Anti-detection / stability
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-plugins")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # Keep background tabs rendering (prevents timer/IO throttling)
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    # On Linux (Railway/Docker): google-chrome-stable is installed via Dockerfile .deb
    # webdriver-manager auto-downloads the matching ChromeDriver version
    if sys.platform.startswith("linux"):
        chrome_bin = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome-stable")
        if not os.path.exists(chrome_bin):
            chrome_bin = "/usr/bin/google-chrome"
        opts.binary_location = chrome_bin
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=opts)

    # On Mac (local dev): minimize window so it disappears to the dock instantly
    # On Linux (Render): Xvfb handles this — no real screen exists, skip positioning
    if not sys.platform.startswith("linux"):
        try:
            driver.minimize_window()
        except Exception:
            pass

    # selenium-stealth hides all JS-level automation fingerprints from Amazon
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    return driver

def set_pincode(driver, domain, pincode):
    driver.get(f"https://www.{domain}/")
    time.sleep(4)
    try:
        loc_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "nav-global-location-popover-link"))
        )
        loc_btn.click()
        time.sleep(2)
        inp = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput"))
        )
        inp.clear()
        inp.send_keys(pincode)
        time.sleep(1)
        try:
            apply_btn = driver.find_element(By.CSS_SELECTOR, "#GLUXZipUpdate input[type='submit']")
            apply_btn.click()
        except Exception:
            apply_btn = driver.find_element(By.CSS_SELECTOR, "#GLUXZipUpdate .a-button-input")
            apply_btn.click()
        time.sleep(2)
        try:
            done = driver.find_element(By.CSS_SELECTOR,
                "button[name='glowDoneButton'], .a-popover-footer .a-button-primary input")
            done.click()
        except Exception:
            pass
        time.sleep(1)
        print(f"  Pincode set to {pincode}")
    except Exception as e:
        print(f"  Warning: Could not set pincode ({type(e).__name__}), continuing anyway")

# ── SP / Organic extraction ───────────────────────────────────────────────────

JS_EXTRACT_PRODUCTS = """
var items = document.querySelectorAll('div[data-component-type="s-search-result"]');
var results = [];
items.forEach(function(item) {
    var asin = item.getAttribute('data-asin');
    if (!asin) return;

    var titleEl = item.querySelector('h2 a span, h2 span');
    var title = titleEl ? titleEl.textContent.trim() : '';
    if (!title) return;

    var sponsored = false;

    // PRIMARY: Amazon's own embedded metadata — every result card carries a JSON
    // payload with searchProductType:"SPONSORED"/"ORGANIC" and an isSponsored flag.
    // This is ground truth from Amazon itself: language-independent, layout-
    // independent, immune to label redesigns. (Appears HTML-escaped in innerHTML.)
    var ihtml = item.innerHTML;
    if (/searchProductType(&quot;|")\s*:\s*(&quot;|")SPONSORED/i.test(ihtml)) {
        sponsored = true;
    }
    if (!sponsored && /(&quot;|")isSponsored(&quot;|")\s*:\s*(&quot;|")?(true|1)/i.test(ihtml)) {
        sponsored = true;
    }

    // FALLBACKS: visible label detection — covers renders without the metadata payload
    var spSelectors = [
        'span.a-color-secondary',
        'span.puis-label-popover-default span',
        '.a-badge-text',
        '.puis-sponsored-label-text',
        '[class*="sponsored-label"]',
        '[class*="sp-label"]',
        '[data-component-type="sp-sponsored-result"]',
        'span[aria-label]'
    ];
    for (var si = 0; si < spSelectors.length && !sponsored; si++) {
        var spEls = item.querySelectorAll(spSelectors[si]);
        for (var sj = 0; sj < spEls.length && !sponsored; sj++) {
            var stxt = (spEls[sj].textContent || '').toLowerCase();
            var saria = (spEls[sj].getAttribute('aria-label') || '').toLowerCase();
            if (stxt.indexOf('sponsored') >= 0 || stxt.indexOf('प्रायोजित') >= 0 ||
                saria.indexOf('sponsored') >= 0) {
                sponsored = true;
            }
        }
    }
    // Fallback: check data-component-type on the item itself
    if (!sponsored) {
        var ct = item.getAttribute('data-component-type') || '';
        if (ct.toLowerCase().indexOf('sponsored') >= 0) sponsored = true;
    }
    // Fallback: check aria-label on the item itself
    if (!sponsored) {
        var itemAria = (item.getAttribute('aria-label') || '').toLowerCase();
        if (itemAria.indexOf('sponsored') >= 0) sponsored = true;
    }
    // Nuclear fallback: XPath to find any element whose direct text is EXACTLY "Sponsored"
    // This catches Reebok-style inline SP ads where the label uses an unknown CSS class
    if (!sponsored) {
        try {
            var xpResult = document.evaluate(
                './/*[normalize-space(.)="Sponsored" or normalize-space(.)="प्रायोजित"]',
                item, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
            ).singleNodeValue;
            if (xpResult) sponsored = true;
        } catch(e) {}
    }

    var brand = '';
    var brandSels = [
        'h5.s-line-clamp-1 span.a-size-base',
        'span.a-size-base-plus.a-color-base',
        '.a-row.a-size-base .a-link-normal',
        '.s-line-clamp-1 .a-size-base'
    ];
    for (var j = 0; j < brandSels.length; j++) {
        var bEl = item.querySelector(brandSels[j]);
        if (bEl) {
            var bTxt = bEl.textContent.trim();
            if (bTxt && bTxt.length < 60 && bTxt.toLowerCase() !== 'sponsored') {
                brand = bTxt;
                break;
            }
        }
    }

    // Reject price strings
    if (brand && brand.trim().startsWith('₹')) brand = '';

    // Sanity-check: if byline brand doesn't appear anywhere in the title,
    // and the title's first word is capitalised and short, prefer the title word.
    // This catches cases like byline="Jockey" but product is actually Reebok.
    if (brand && title) {
        var brandLower = brand.toLowerCase();
        var titleLower = title.toLowerCase();
        if (titleLower.indexOf(brandLower) < 0) {
            var firstWord = title.split(/\s+/)[0];
            if (firstWord && firstWord.length > 1 && firstWord.length < 25 &&
                firstWord[0] === firstWord[0].toUpperCase() &&
                !firstWord.startsWith('₹') && !firstWord.startsWith('$')) {
                brand = firstWord;
            }
        }
    }

    // If brand still empty, fall back to first word of title
    if (!brand && title) {
        var fw = title.split(/\s+/)[0];
        if (fw && fw.length > 1 && !fw.startsWith('₹') && !fw.startsWith('$')) {
            brand = fw;
        }
    }

    // Price — Amazon renders the full price in a screen-reader-only span.
    var price = '';
    var priceEl = item.querySelector('.a-price .a-offscreen');
    if (priceEl) price = priceEl.textContent.trim();

    var r0 = item.getBoundingClientRect();
    results.push({asin: asin, title: title, brand: brand, sponsored: sponsored, price: price,
                  y: Math.round(r0.top + window.scrollY), x: Math.round(r0.left)});
});

// ── Sponsored carousel/grid cards ──────────────────────────────────────────
// Amazon also serves SP as carousel or grid units OUTSIDE the standard result
// list (the "Add to cart" rows). Count every card that Amazon's own metadata
// marks sponsored — but skip cards inside SB/SBV banner units.
var seenAsins = {};
results.forEach(function (r) { seenAsins[r.asin] = 1; });
var cards = document.querySelectorAll('div[data-asin]:not([data-asin=""])');
for (var ci = 0; ci < cards.length; ci++) {
    var card = cards[ci];
    var casin = card.getAttribute('data-asin');
    if (!casin || seenAsins[casin]) continue;
    var cih = card.innerHTML;
    if (!/searchProductType(&quot;|")\s*:\s*(&quot;|")SPONSORED/i.test(cih) &&
        !/(&quot;|")isSponsored(&quot;|")\s*:\s*(&quot;|")?(true|1)/i.test(cih)) continue;
    // not part of a video/banner ad unit (those are SB/SBV, not SP)
    if (card.closest('[data-cel-widget*="VIDEO"]') ||
        card.closest('[data-cel-widget*="SPONSORED_BRANDS"]') ||
        card.closest('[data-cel-widget*="MULTI_ASIN"]')) continue;
    // not a nested node of an already-counted result item
    var host = card.closest('div[data-component-type="s-search-result"]');
    if (host && host.getAttribute('data-asin') !== casin) continue;
    var tEl = card.querySelector('h2 a span, h2 span, .a-size-base-plus, .a-size-medium, a.a-link-normal span');
    var ctitle = tEl ? (tEl.textContent || '').trim() : '';
    if (!ctitle) {
        var imgEl = card.querySelector('img[alt]');
        if (imgEl) ctitle = (imgEl.getAttribute('alt') || '').trim();
    }
    if (!ctitle || ctitle.length < 5) continue;
    seenAsins[casin] = 1;
    var cPriceEl = card.querySelector('.a-price .a-offscreen');
    var r1 = card.getBoundingClientRect();
    results.push({asin: casin, title: ctitle, brand: '', sponsored: true,
                  price: cPriceEl ? cPriceEl.textContent.trim() : '',
                  y: Math.round(r1.top + window.scrollY), x: Math.round(r1.left)});
}

// ── Label-based sweep (independent of JSON metadata) ──────────────────────
// Some renders carry the visible "Sponsored" label but no metadata payload.
// Catch any product card whose label text is exactly "Sponsored".
for (var li = 0; li < cards.length; li++) {
    var lcard = cards[li];
    var lasin = lcard.getAttribute('data-asin');
    if (!lasin || seenAsins[lasin]) continue;
    if (lcard.closest('[data-cel-widget*="VIDEO"]') ||
        lcard.closest('[data-cel-widget*="SPONSORED_BRANDS"]') ||
        lcard.closest('[data-cel-widget*="MULTI_ASIN"]')) continue;
    var lhost = lcard.closest('div[data-component-type="s-search-result"]');
    if (lhost && lhost.getAttribute('data-asin') !== lasin) continue;
    var hasLabel = false;
    var spans = lcard.querySelectorAll('span, a');
    for (var sk = 0; sk < spans.length && !hasLabel; sk++) {
        var st = (spans[sk].textContent || '').trim();
        if (st === 'Sponsored' || st === 'प्रायोजित') hasLabel = true;
    }
    if (!hasLabel) continue;
    var lEl = lcard.querySelector('h2 a span, h2 span, .a-size-base-plus, .a-size-medium, a.a-link-normal span');
    var ltitle = lEl ? (lEl.textContent || '').trim() : '';
    if (!ltitle) {
        var lImg = lcard.querySelector('img[alt]');
        if (lImg) ltitle = (lImg.getAttribute('alt') || '').trim();
    }
    if (!ltitle || ltitle.length < 5) continue;
    seenAsins[lasin] = 1;
    var lPriceEl = lcard.querySelector('.a-price .a-offscreen');
    var r2 = lcard.getBoundingClientRect();
    results.push({asin: lasin, title: ltitle, brand: '', sponsored: true,
                  price: lPriceEl ? lPriceEl.textContent.trim() : '',
                  y: Math.round(r2.top + window.scrollY), x: Math.round(r2.left)});
}

// Restore TRUE on-page order: sort every captured item by its position on the
// page (top-to-bottom, then left-to-right within a row). Without this, items
// found by the carousel/label sweeps would be appended at the end and get
// wrong rank positions.
results.sort(function (a, b) { return (a.y - b.y) || (a.x - b.x); });
return results;
"""

# ── SB / SBV extraction ───────────────────────────────────────────────────────
# Uses Selenium's native find_elements() — no JavaScript injection, no IIFE issues.

import re as _re

def _get_brand(container):
    """Extract brand name from a banner WebElement using Selenium attribute reads."""
    import urllib.parse
    try:
        # 1. /stores/BrandName/ URL — most reliable signal
        for a in container.find_elements(By.TAG_NAME, 'a'):
            href = a.get_attribute('href') or ''
            # Direct match
            m = _re.search(r'/stores/([^/?&#]+)', href)
            if m:
                brand = urllib.parse.unquote(m.group(1)).replace('+', ' ').strip()
                if brand.lower() not in ('page', 'ref') and len(brand) > 1:
                    return brand
            # Encoded redirect URL (aax-eu-zaz.amazon.in style)
            if 'stores' in href:
                decoded = urllib.parse.unquote(href)
                m = _re.search(r'/stores/([^/?&#]+)', decoded)
                if m:
                    brand = decoded_brand = m.group(1).replace('+', ' ').strip()
                    if brand.lower() not in ('page', 'ref') and len(brand) > 1:
                        return brand

        # 2. "Shop BRAND >" or "Shop the BRAND Store" link text
        for a in container.find_elements(By.TAG_NAME, 'a'):
            txt = (a.text or '').strip()
            m = _re.match(r'^(?:Shop|Visit)\s+(?:the\s+)?(.+?)(?:\s+(?:Store|Brand))?\s*[>›»]?\s*$', txt, _re.I)
            if m:
                brand = m.group(1).strip().rstrip('>').strip()
                if 1 < len(brand) < 40:
                    return brand

        # 3. Brand logo — short single-word img alt text (logo images have
        #    concise alt = brand name; product image alts usually have spaces)
        skip_alt = {'star', 'video', 'sponsored', 'amazon', 'prime',
                    'rating', 'banner', 'play', 'button', 'image', 'photo',
                    'product', 'sale', 'deal', 'offer', 'new', 'best'}
        for img in container.find_elements(By.CSS_SELECTOR, 'img[alt]'):
            alt = (img.get_attribute('alt') or '').strip()
            # Logo images usually have short clean alt text with no spaces (2–20 chars)
            if 2 < len(alt) <= 20 and ' ' not in alt and not any(w in alt.lower() for w in skip_alt):
                return alt

        # 4. Img alt fallback — allow up to 2 words, but never price strings
        for img in container.find_elements(By.CSS_SELECTOR, 'img[alt]'):
            alt = (img.get_attribute('alt') or '').strip()
            words = alt.split()
            if 1 <= len(words) <= 2 and 2 < len(alt) < 40 and not any(w in alt.lower() for w in skip_alt) and not alt.startswith('₹'):
                return alt

    except Exception:
        pass
    return 'Unknown'


def _get_sbv_brand(container):
    """Extract brand specifically from SBV video ad containers.

    The brand of an SBV ad is the company that paid for it — NOT the product
    names shown in the carousel cards. Priority order:
      1. /stores/BrandName/ URL in any anchor href (gold standard)
      2. "Shop BRAND" / "Visit BRAND Store" link text
      3. Logo image alt text (skipping product card images)
      4. Short heading (1–3 words) that looks like a brand name
      5. Fall back to the SB-style extractor _get_brand()
    """
    import urllib.parse
    try:
        # 1. /stores/BrandName/ URL — most reliable signal of the advertiser
        for a in container.find_elements(By.TAG_NAME, 'a'):
            href = a.get_attribute('href') or ''
            # Direct match
            m = _re.search(r'/stores/([^/?&#]+)', href)
            if m:
                brand = urllib.parse.unquote(m.group(1)).replace('+', ' ').strip()
                if brand.lower() not in ('page', 'ref') and len(brand) > 1:
                    return brand
            # Encoded redirect URL (aax-eu-zaz.amazon.in style)
            if 'stores' in href:
                decoded = urllib.parse.unquote(href)
                m = _re.search(r'/stores/([^/?&#]+)', decoded)
                if m:
                    brand = m.group(1).replace('+', ' ').strip()
                    if brand.lower() not in ('page', 'ref') and len(brand) > 1:
                        return brand

        # 2. "Shop BRAND >" or "Visit BRAND Store" link text
        for a in container.find_elements(By.TAG_NAME, 'a'):
            txt = (a.text or '').strip()
            m = _re.match(r'^(?:Shop|Visit)\s+(?:the\s+)?(.+?)(?:\s+(?:Store|Brand))?\s*[>›»]?\s*$', txt, _re.I)
            if m:
                brand = m.group(1).strip().rstrip('>').strip()
                if 1 < len(brand) < 40:
                    return brand

        # 2.5 Single-product video ads: the advertised product's title starts
        #     with the advertiser's brand ("Boldfit Running Shoes…" → Boldfit,
        #     "PROSHARX Premium Compression…" → PROSHARX). Very reliable for
        #     sbv-video-single-product units — the product IS the ad.
        try:
            title_txt = container.parent.execute_script(
                "var el=arguments[0];"
                "var card=el.querySelector('[data-asin]:not([data-asin=\\'\\'])');"
                "if(!card)return '';"
                "var t=card.querySelector('h2 span,h2,.a-size-base-plus,.a-size-medium,"
                "a.a-link-normal span,.a-truncate-full');"
                "return t?(t.textContent||'').trim():(card.textContent||'').trim().substring(0,120);",
                container) or ''
        except Exception:
            title_txt = ''
        if len(title_txt) > 8:
            fw = title_txt.split()[0].strip('.,:;()[]')
            if (2 < len(fw) <= 20 and fw[0].isalpha() and fw[0].isupper()
                    and not fw.startswith(('₹', '$', '€', '£'))):
                return fw

        # 2.6 Product image alt — video single-product ads carry the FULL product
        #     title as the image alt ("Boldfit Running Shoes for Man…"). The
        #     first word is the advertiser's brand. (Confirmed via forensics.)
        for img in container.find_elements(By.CSS_SELECTOR, 'img[alt]'):
            alt = (img.get_attribute('alt') or '').strip()
            if len(alt) > 15:
                fw = alt.split()[0].strip('.,:;()[]')
                if 2 < len(fw) <= 20 and fw[0].isalpha() and fw[0].isupper():
                    return fw

        # 3. Logo image alt text — skip images inside [data-asin] product cards
        skip = {'star', 'video', 'sponsored', 'amazon', 'prime', 'play', 'pause',
                'mute', 'rating', 'product', 'sale', 'deal', 'offer', 'new', 'best'}
        product_imgs = set()
        for card in container.find_elements(By.CSS_SELECTOR, '[data-asin]:not([data-asin=""])'):
            for img in card.find_elements(By.CSS_SELECTOR, 'img[alt]'):
                product_imgs.add(img.id)
        for img in container.find_elements(By.CSS_SELECTOR, 'img[alt]'):
            if img.id in product_imgs:
                continue
            alt = (img.get_attribute('alt') or '').strip()
            if 2 <= len(alt) <= 25 and not any(w in alt.lower() for w in skip) and not alt.startswith('₹'):
                return alt

        # 4. Short heading (1–3 words) that looks like a brand name
        for h in container.find_elements(By.CSS_SELECTOR, 'h1,h2,h3,h4'):
            text = (h.text or '').strip()
            words = text.split()
            if 1 <= len(words) <= 3:
                skip_words = {'shop', 'visit', 'the', 'buy', 'new', 'best', 'our', 'your'}
                if (words and words[0][0].isupper() and len(text) < 35 and
                        not any(w.lower() in skip_words for w in words)):
                    return text

        # 5. Fall back to the SB-style extractor (store URL / Shop link)
        return _get_brand(container)

    except Exception:
        pass
    return 'Unknown'


def _overlaps_scraped(driver, el):
    """True if el (or an ancestor/descendant) was already captured by an earlier sweep.

    Sweeps find the same ad via different DOM nodes (AdHolder vs nested widget),
    so element-id dedup alone misses duplicates. We mark processed containers
    with a data attribute and check the whole ancestor/descendant chain.
    """
    try:
        return driver.execute_script(
            "return arguments[0].closest('[data-serp-scraped]')!==null"
            "||arguments[0].querySelector('[data-serp-scraped]')!==null;", el)
    except Exception:
        return False


def _mark_scraped(driver, el):
    try:
        driver.execute_script("arguments[0].setAttribute('data-serp-scraped','1');", el)
    except Exception:
        pass


# Any one of these inside a banner container means the creative is a video ad.
# Multiple signals because Amazon renders SBV differently per region/experiment:
# the <video> tag itself, the sbv component wrapper, video-js player classes,
# data-video-url attributes, or the mute/unmute control that ships with the player.
_VIDEO_SIGNALS_JS = (
    "var el=arguments[0];"
    "return !!("
    "  el.querySelector('video')"
    "||el.querySelector('[data-component-type*=\"video\" i]')"
    "||el.querySelector('[data-video-url],[data-videourl]')"
    "||el.querySelector('.video-js,[class*=\"vjs-\"]')"
    "||el.querySelector('[aria-label*=\"mute\" i],[aria-label*=\"video\" i]')"
    "||el.querySelector('[data-csa-c-content-type*=\"video\" i]')"
    ");"
)

def _is_video_ad(driver, el, timeout=None):
    """Poll for lazy-loaded video signals inside a banner container.

    Amazon inserts the <video> element only after the ad has been visible in
    the viewport — a fixed sleep misses it on slow servers. Poll every 0.4s
    up to `timeout` and return as soon as any video signal appears.
    """
    if timeout is None:
        timeout = 5.0 if sys.platform.startswith("linux") else 2.5
    deadline = time.time() + timeout
    while True:
        try:
            if driver.execute_script(_VIDEO_SIGNALS_JS, el):
                return True
        except Exception:
            return False
        if time.time() >= deadline:
            return False
        time.sleep(0.4)


def extract_banners(driver):
    """
    Unified single-pass SB/SBV extraction.

    The old design ran three separate sweeps (AdHolders, sbv components, raw
    <video> tags) and deduped afterwards. The same physical ad seen through
    different DOM nodes produced BOTH an SB and an SBV entry — or an "Unknown"
    brand — because each sweep classified with only partial knowledge.

    This version works the way the page actually works:
      1. Collect every ad signal on the page.
      2. Resolve each signal to its OUTERMOST ad-unit container (canonical).
      3. Dedupe by canonical container — one entry per physical ad.
      4. Classify once with ALL signals: if any signal says video, it's SBV.
    A container found via an sbv component or a <video> tag is SBV by
    construction — no lazy-load race can misclassify it as SB.
    """
    placements = []

    _CANONICAL_JS = (
        "var cur=arguments[0],top=null;"
        "while(cur&&cur!==document.body&&cur.nodeType===1){"
        "  var cls=(cur.className||'').toString();"
        "  var cel=cur.getAttribute('data-cel-widget')||'';"
        "  if(cls.indexOf('AdHolder')>=0||cls.indexOf('s-widget-container')>=0||"
        "     cel.indexOf('VIDEO')>=0||cel.indexOf('SPONSORED_BRANDS')>=0)top=cur;"
        "  cur=cur.parentElement;"
        "}"
        "return top;"
    )

    # 1. Gather every ad signal. Each entry: (element, video_known)
    candidates = []
    try:
        for el in driver.find_elements(By.CSS_SELECTOR, '.AdHolder[data-asin=""]'):
            candidates.append((el, False))
        for el in driver.find_elements(By.CSS_SELECTOR,
                '[data-component-type="sbv-video-single-product"],'
                '[data-component-type*="video-single-product"]'):
            candidates.append((el, True))   # sbv component ⇒ video ad by definition
        for el in driver.find_elements(By.TAG_NAME, 'video'):
            candidates.append((el, True))   # a <video> tag ⇒ video ad by definition
    except Exception as e:
        print(f"    Banner candidate collection failed: {e}")

    # 2 + 3. Canonicalize and dedupe — one unit per physical ad.
    units = {}   # canonical element id → {'el': element, 'video': bool}
    for el, video_known in candidates:
        try:
            canon = driver.execute_script(_CANONICAL_JS, el)
        except Exception:
            canon = None
        if canon is None:
            continue
        try:
            cel_widget = (canon.get_attribute('data-cel-widget') or '').lower()
            el_id      = (canon.get_attribute('id') or '').lower()
        except Exception:
            continue
        # Known false-positive slots (display ads, sidebar, footer)
        if ('loom' in cel_widget or 'loom' in el_id or
                'auto-left-advertising' in el_id or 'footer' in cel_widget):
            continue
        unit = units.setdefault(canon.id, {'el': canon, 'video': False, 'y': None})
        unit['video'] = unit['video'] or video_known

    # Read document positions, then order units top-to-bottom
    for unit in units.values():
        try:
            unit['y'] = unit['el'].location.get('y', 0)
        except Exception:
            unit['y'] = 0
    ordered = sorted(units.values(), key=lambda u: u['y'])

    # Pre-pass: bring every unit into view once so lazy video creatives start
    # loading in parallel — classification below then needs only a short poll.
    for unit in ordered:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", unit['el'])
            time.sleep(0.5)
        except Exception:
            pass

    # 4. Classify once per unit, with every signal available.
    for unit in ordered:
        el = unit['el']
        placement_pos = 'TOS' if unit['y'] < 600 else 'ROS'
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        is_video = unit['video'] or _is_video_ad(driver, el, timeout=2.5)
        banner_type = 'SBV' if is_video else 'SB'
        brand = _get_sbv_brand(el) if is_video else _get_brand(el)
        print(f"    Banner: {banner_type} ({placement_pos}) — {brand}")
        if brand == 'Unknown' and banner_type == 'SBV':
            # Forensics: print what's actually inside so brand extraction can be
            # fixed against evidence instead of guesses.
            try:
                info = driver.execute_script(
                    "var el=arguments[0],out={};"
                    "out.cel=el.getAttribute('data-cel-widget');"
                    "out.links=Array.from(el.querySelectorAll('a')).slice(0,5)"
                    ".map(function(a){return (a.href||'').substring(0,110);});"
                    "out.alts=Array.from(el.querySelectorAll('img[alt]')).slice(0,5)"
                    ".map(function(i){return i.getAttribute('alt');});"
                    "var card=el.querySelector('[data-asin]');"
                    "out.card=card?(card.textContent||'').trim().substring(0,150):null;"
                    "out.text=(el.textContent||'').trim().substring(0,150);"
                    "return JSON.stringify(out);", el)
                print(f"      SBV-Unknown forensics: {info[:700]}")
            except Exception:
                pass
        placements.append({
            'position':  len(placements) + 1,
            'type':      banner_type,
            'brand':     brand,
            'placement': placement_pos,
        })

    # Drop Unknown SB entries — these are false positives (sidebar/footer display ads).
    # Unknown SBV entries are kept — real video ads where brand extraction just failed.
    placements = [p for p in placements if not (p['type'] == 'SB' and p['brand'] == 'Unknown')]

    # Final dedup: identical (brand, type, placement) = same campaign counted twice
    unique = []
    seen_keys = set()
    for p in placements:
        key = (p['brand'].lower(), p['type'], p.get('placement', ''))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(p)
    placements = unique

    # Re-sequence positions after filtering
    for i, p in enumerate(placements):
        p['position'] = i + 1

    # Restore scroll position (sweep 1 scrolls containers into view)
    try:
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass

    return placements

def extract_brand_from_title(title):
    if not title:
        return "Unknown"
    return title.split()[0] if title.split() else "Unknown"

def scrape_keyword(driver, domain, keyword, cap, pages=None, max_retries=2):
    """
    Scrape one keyword across up to 5 pages.
    Returns (results, sb_placements).
    Retries up to max_retries times on page-level failures.
    """
    results = []
    sb_placements = []
    page = 1

    def _organic_count():
        return sum(1 for r in results if r["type"] == "ORGANIC")

    # Depth: 'pages' mode scrapes N whole pages (every ad + organic on them);
    # 'positions' mode (cap) limits ORGANIC depth only — sponsored results are
    # ALWAYS captured on every visited page, they never consume the cap.
    hard_page_limit = pages if pages else 5
    while page <= hard_page_limit and (pages or _organic_count() < cap):
        # Heartbeat: touch the progress file so the server knows this scrape is
        # alive even when a single keyword takes many minutes.
        try:
            os.utime(PROGRESS_FILE, None)
        except OSError:
            pass
        url = f"https://www.{domain}/s?k={quote_plus(keyword)}&page={page}"
        print(f"    Page {page}: fetching…")

        page_ok = False
        for attempt in range(max_retries + 1):
            try:
                driver.get(url)
                # Random delay between pages: 1.5–3 s (first attempt) or 3–6 s (retry)
                sleep_secs = random.uniform(3, 6) if attempt > 0 else random.uniform(1.5, 3)
                time.sleep(sleep_secs)

                WebDriverWait(driver, WAIT_TIMEOUT).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                )
                time.sleep(random.uniform(0.8, 1.5))
                page_ok = True
                break
            except TimeoutException:
                if attempt < max_retries:
                    print(f"    Page {page} timeout, retrying ({attempt+1}/{max_retries})…")
                    time.sleep(random.uniform(4, 7))
                else:
                    print(f"    Page {page}: no results after {max_retries} retries, stopping")

        if not page_ok:
            break

        # ── EVERY page: scroll to trigger lazy ads, then extract banners ──
        # Each results page carries its own SB/SBV slots. TOS only exists on
        # page 1 — every banner on later pages is ROS by definition.
        # Extra wait — off-screen Chrome needs a moment for ad creatives to render
        time.sleep(random.uniform(1.5, 2.5))
        try:
            # 4-stop scroll: triggers lazy-load for TOS banners AND mid/lower ROS SBV slots
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.0)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.25);")
            time.sleep(1.4)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.50);")
            time.sleep(1.4)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.75);")
            time.sleep(2.0)
        except Exception as e:
            print(f"    Scroll failed: {e}")

        try:
            page_banners = extract_banners(driver)
            for b in page_banners:
                if page > 1:
                    b['placement'] = 'ROS'
                b['page'] = page
            sb_placements.extend(page_banners)
            print(f"    Page {page} banners: {len(page_banners)} (SB/SBV)")
        except Exception as e:
            print(f"    Banner extraction failed: {e}")

        # ── Extract SP / Organic products ──────────────────────────────────────
        # Amazon runs a FRESH ad auction on every page load, and datacenter IPs
        # often receive a zero-ad render. When our extraction finds 0 sponsored
        # AND Amazon's own metadata confirms zero were served, one reload almost
        # always comes back with ads. Retry once per page (pages 1–2 only).
        js_failed = False
        page_items = []
        for sp_try in range(3):
            try:
                page_items = driver.execute_script(JS_EXTRACT_PRODUCTS)
            except Exception as e:
                print(f"    JS product extraction failed on page {page}: {e}")
                js_failed = True
                break
            max_reloads = 2 if page == 1 else 1
            if (sp_try < max_reloads and page <= 2 and page_items
                    and not any(it["sponsored"] for it in page_items)):
                meta_sp = 0
                try:
                    meta_sp = driver.execute_script(
                        "return (document.documentElement.innerHTML.match("
                        "/searchProductType(&quot;|\")\\s*:\\s*(&quot;|\")SPONSORED/gi)||[]).length;")
                except Exception:
                    pass
                if meta_sp == 0:
                    print(f"    Page {page}: Amazon served 0 SP ads this render — "
                          f"reloading for a fresh ad auction…")
                    try:
                        if page == 1 and sp_try == 1:
                            # Second retry: search via the search box like a human
                            # would — a different referrer often gets a fuller
                            # ad auction than a direct URL hit.
                            try:
                                box = driver.find_element(By.ID, 'twotabsearchtextbox')
                                box.clear()
                                box.send_keys(keyword)
                                box.submit()
                            except Exception:
                                driver.get(url)
                        else:
                            driver.get(url)
                        time.sleep(random.uniform(2.5, 4.0))
                        WebDriverWait(driver, WAIT_TIMEOUT).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "div[data-component-type='s-search-result']")))
                        time.sleep(random.uniform(0.8, 1.5))
                        continue
                    except Exception:
                        break
            break
        if js_failed:
            page += 1
            time.sleep(random.uniform(2, 4))
            continue

        if not page_items:
            print(f"    No product items on page {page}")
            if page == 1:
                try:
                    html = driver.execute_script("return document.documentElement.outerHTML")
                    debug_path = os.path.join(BASE, "debug_render_page.html")
                    with open(debug_path, 'w', encoding='utf-8') as f:
                        f.write(html[:50000])
                    print(f"    DEBUG: Saved page HTML to {debug_path} (0 items found)")
                except Exception:
                    pass
            break

        # DEBUG: if page 1 found items but ZERO sponsored, dump the first few
        # result items' raw HTML so we can see what the SP badge looks like here
        if page == 1 and not any(it["sponsored"] for it in page_items):
            # Decisive check: Amazon's own metadata verdict for the whole page.
            # metadata SPONSORED > 0 here would mean our extraction missed them (bug);
            # metadata SPONSORED = 0 means Amazon truly served no SP ads this session.
            try:
                # Definitive forensics, independent of the JSON metadata:
                # count "Sponsored" labels INSIDE product cards only (banners,
                # video units and display-ad slots excluded). If this is > 0
                # while extraction found 0, we are missing real SP cards and
                # the first offenders' HTML is dumped for evidence.
                probe = driver.execute_script(
                    'var hits=[];'
                    'var cards=document.querySelectorAll("div[data-asin]");'
                    'for(var k=0;k<cards.length;k++){'
                    '  var c=cards[k];'
                    '  var asin=c.getAttribute("data-asin");'
                    '  if(!asin)continue;'
                    '  if(c.closest("[data-cel-widget*=VIDEO],[data-cel-widget*=SPONSORED_BRANDS],[data-cel-widget*=MULTI_ASIN]"))continue;'
                    '  var idl=(c.id||"").toLowerCase();'
                    '  if(idl.indexOf("loom")>=0)continue;'
                    '  var s=c.querySelectorAll("span,a");'
                    '  for(var i=0;i<s.length;i++){'
                    '    var t=(s[i].textContent||"").trim();'
                    '    if(t==="Sponsored"){hits.push({asin:asin,html:c.outerHTML.substring(0,9000)});break;}'
                    '  }'
                    '}'
                    'return hits;')
                print(f"    DEBUG: 'Sponsored'-labelled PRODUCT CARDS on page: {len(probe)}")
                if probe:
                    print(f"    DEBUG: >>> EXTRACTION MISSED {len(probe)} labelled cards! "
                          f"ASINs: {[h['asin'] for h in probe][:6]}")
                    with open(os.path.join(WORKSPACE, "debug_missed_sp.html"), "w",
                              encoding="utf-8") as f:
                        for h in probe[:3]:
                            f.write(f"<!-- ASIN {h['asin']} -->\n{h['html']}\n\n")
                # Full-page screenshot via CDP (beyond the viewport)
                import base64 as _b64
                shot = driver.execute_cdp_cmd('Page.captureScreenshot',
                                              {'captureBeyondViewport': True, 'format': 'png'})
                with open(os.path.join(WORKSPACE, "debug_screenshot.png"), "wb") as f:
                    f.write(_b64.b64decode(shot['data']))
                print(f"    DEBUG: saved FULL-PAGE screenshot to workspace")
            except Exception as e:
                print(f"    DEBUG forensics failed: {e}")
            try:
                meta_counts = driver.execute_script(
                    "var h=document.documentElement.innerHTML;"
                    "var sp=(h.match(/searchProductType(&quot;|\")\\s*:\\s*(&quot;|\")SPONSORED/gi)||[]).length;"
                    "var org=(h.match(/searchProductType(&quot;|\")\\s*:\\s*(&quot;|\")ORGANIC/gi)||[]).length;"
                    "return [sp, org];"
                )
                print(f"    DEBUG: Amazon metadata says {meta_counts[0]} SPONSORED / "
                      f"{meta_counts[1]} ORGANIC on this page — "
                      f"{'EXTRACTION BUG' if meta_counts[0] > 0 else 'Amazon served zero SP ads (not a bug)'}")
            except Exception:
                pass
            try:
                sample_html = driver.execute_script(
                    "var els=document.querySelectorAll("
                    "'div[data-component-type=\"s-search-result\"]');"
                    "var out=[];"
                    "for(var i=0;i<Math.min(els.length,4);i++){"
                    "  out.push('<!-- ITEM '+i+' asin='+els[i].getAttribute('data-asin')+' -->');"
                    "  out.push(els[i].outerHTML.substring(0,12000));"
                    "}"
                    "return out.join('\\n\\n');"
                )
                debug_path = os.path.join(BASE, "debug_render_page.html")
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(sample_html or "EMPTY")
                print(f"    DEBUG: 0 sponsored on page 1 — saved {len(sample_html or '')} chars "
                      f"of item HTML to {debug_path}")
            except Exception as e:
                print(f"    DEBUG item-dump failed: {e}")

        new_on_page = 0
        for item in page_items:
            # cap limits organic depth only — sponsored items are the point of
            # this tool and are always captured on every visited page
            if not pages and not item["sponsored"] and _organic_count() >= cap:
                continue
            asin  = item["asin"]
            title = item["title"]
            brand = item["brand"] or extract_brand_from_title(title)
            rtype = "SPONSORED" if item["sponsored"] else "ORGANIC"

            results.append({
                "position": len(results) + 1,
                "asin":     asin,
                "title":    title,
                "brand":    brand,
                "type":     rtype,
                "price":    item.get("price", ""),
                "url":      f"https://www.{domain}/dp/{asin}"
            })
            new_on_page += 1

        print(f"    Page {page}: {new_on_page} products (total: {len(results)})")

        if new_on_page == 0:
            break

        page += 1
        time.sleep(random.uniform(1.5, 3))

    for i, p in enumerate(sb_placements):
        p['position'] = i + 1
    return results, sb_placements

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    config = load_config()

    # Archive existing data before overwriting
    print("Archiving previous serp_data.json…")
    archive_data()

    # Start fresh data dict
    data = {}

    # Count total keywords across all geos for the progress bar
    total_kw = sum(
        len(gc.get("keywords", []))
        for gc in config.get("geographies", {}).values()
    )
    kw_done  = 0
    skipped  = 0

    # Running totals across all geos (shown in final summary)
    grand_sp = grand_org = grand_sb = grand_sbv = 0

    write_progress("running", message="Starting scrape…", total_keywords=total_kw)

    driver = None
    try:
        driver = create_driver()

        for geo, geo_config in config.get("geographies", {}).items():
            domain   = geo_config["domain"]
            pincode  = str(geo_config.get("pincode", ""))
            cap      = int(geo_config.get("cap", 40))
            keywords = geo_config.get("keywords", [])

            print(f"\n{'='*60}")
            print(f"Geography: {geo} ({domain}, pincode: {pincode}, cap: {cap})")
            print(f"{'='*60}")

            data[geo] = {}

            # Geo-level running counters
            geo_sp = geo_org = geo_sb = geo_sbv = geo_skipped = 0

            # Set pincode for this geo
            write_progress(
                "running",
                geo=geo, keyword="",
                keyword_index=kw_done,
                total_keywords=total_kw,
                sp=geo_sp, organic=geo_org,
                sb=geo_sb, sbv=geo_sbv,
                skipped=skipped,
                message=f"Setting location for {geo}…",
                sub_message=f"Pincode: {pincode}" if pincode else "No pincode",
            )
            set_pincode(driver, domain, pincode)

            for i, keyword in enumerate(keywords):
                kw_done += 1
                msg = f"Scraping: {geo} → {keyword} ({kw_done}/{total_kw})"
                print(f"\n  [{kw_done}/{total_kw}] Keyword: '{keyword}'")

                write_progress(
                    "running",
                    geo=geo, keyword=keyword,
                    keyword_index=kw_done - 1,
                    total_keywords=total_kw,
                    sp=geo_sp, organic=geo_org,
                    sb=geo_sb, sbv=geo_sbv,
                    skipped=skipped,
                    message=msg,
                    sub_message="",
                )

                try:
                    results, sb_placements = scrape_keyword(
                        driver, domain, keyword, cap,
                        pages=geo_config.get("pages"))

                    if not results:
                        raise ValueError("Zero results returned")

                    data[geo][keyword] = {
                        "results":       results,
                        "sb_placements": sb_placements,
                    }
                    save_data(data)

                    # Update running counters
                    kw_sp  = sum(1 for r in results if r["type"] == "SPONSORED")
                    kw_org = sum(1 for r in results if r["type"] == "ORGANIC")
                    kw_sb  = sum(1 for p in sb_placements if p["type"] == "SB")
                    kw_sbv = sum(1 for p in sb_placements if p["type"] == "SBV")

                    geo_sp  += kw_sp
                    geo_org += kw_org
                    geo_sb  += kw_sb
                    geo_sbv += kw_sbv

                    print(f"    → {len(results)} results "
                          f"({kw_sp} SP, {kw_org} organic, {kw_sb} SB, {kw_sbv} SBV)")

                    write_progress(
                        "running",
                        geo=geo, keyword=keyword,
                        keyword_index=kw_done,
                        total_keywords=total_kw,
                        sp=geo_sp, organic=geo_org,
                        sb=geo_sb, sbv=geo_sbv,
                        skipped=skipped,
                        message=f"Done: {geo} → {keyword} ({kw_done}/{total_kw})",
                        sub_message=f"{len(results)} results · {kw_sp} SP · {kw_org} organic · {kw_sb} SB · {kw_sbv} SBV",
                    )

                except Exception as e:
                    skipped      += 1
                    geo_skipped  += 1
                    err_short = str(e)[:120]
                    print(f"  ⚠ Skipping '{keyword}': {err_short}")

                    # Save empty entry so downstream knows it was attempted
                    data[geo][keyword] = {"results": [], "sb_placements": [], "error": err_short}
                    save_data(data)

                    write_progress(
                        "running",
                        geo=geo, keyword=keyword,
                        keyword_index=kw_done,
                        total_keywords=total_kw,
                        sp=geo_sp, organic=geo_org,
                        sb=geo_sb, sbv=geo_sbv,
                        skipped=skipped,
                        message=f"⚠ Skipped '{keyword}' ({kw_done}/{total_kw})",
                        sub_message=f"Error: {err_short}",
                    )

                # Random delay between keywords (3–7 s)
                if i < len(keywords) - 1:
                    delay = random.uniform(3, 7)
                    print(f"  Sleeping {delay:.1f}s before next keyword…")
                    time.sleep(delay)

            # Geo completion message
            grand_sp  += geo_sp
            grand_org += geo_org
            grand_sb  += geo_sb
            grand_sbv += geo_sbv

            print(f"\n  ✓ {geo} complete: {geo_sp} SP, {geo_org} organic, "
                  f"{geo_sb} SB, {geo_sbv} SBV, {geo_skipped} skipped")

            write_progress(
                "running",
                geo=geo, keyword="",
                keyword_index=kw_done,
                total_keywords=total_kw,
                sp=geo_sp, organic=geo_org,
                sb=geo_sb, sbv=geo_sbv,
                skipped=skipped,
                message=f"✓ {geo} complete ({kw_done}/{total_kw} keywords)",
                sub_message=f"{geo_sp} SP · {geo_org} organic · {geo_sb} SB · {geo_sbv} SBV · {geo_skipped} skipped",
            )

    except Exception as e:
        write_progress("error", message=str(e))
        raise
    finally:
        if driver:
            driver.quit()

    final_msg = (
        f"Scrape complete! "
        f"{grand_sp} SP · {grand_org} organic · {grand_sb} SB · {grand_sbv} SBV"
        + (f" · {skipped} skipped" if skipped else "")
    )
    write_progress(
        "done",
        keyword_index=total_kw,
        total_keywords=total_kw,
        sp=grand_sp, organic=grand_org,
        sb=grand_sb, sbv=grand_sbv,
        skipped=skipped,
        message=final_msg,
        sub_message="",
    )
    print(f"\nDone! Data saved to {DATA_FILE}")

if __name__ == "__main__":
    main()
