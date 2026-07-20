import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))

# All MUTABLE data (profiles, sessions, results, history) lives under DATA_ROOT.
# On Railway, DATA_DIR=/data points at a persistent volume so saves and deletes
# survive restarts and redeploys. Locally it defaults to the project folder.
DATA_ROOT = os.environ.get("DATA_DIR") or BASE
os.makedirs(DATA_ROOT, exist_ok=True)

CONFIG_FILE   = os.path.join(DATA_ROOT, "config.json")
PROFILES_FILE = os.path.join(DATA_ROOT, "profiles.json")
DATA_FILE     = os.path.join(DATA_ROOT, "serp_data.json")
PROGRESS_FILE = os.path.join(DATA_ROOT, "progress.json")
HISTORY_DIR   = os.path.join(DATA_ROOT, "history", "data")
TEMPLATES_DIR = os.path.join(BASE, "templates")
SESSIONS_DIR  = os.path.join(DATA_ROOT, "sessions")

# ── per-user workspaces ───────────────────────────────────────────────────────
# Each browser sends a ?sid=<id> with every API call. Every sid gets its own
# folder for config/progress/results/history so concurrent users never collide.
# Profiles stay global (shared across the team) by design.

def _workspace():
    sid = re.sub(r"[^A-Za-z0-9_-]", "", request.args.get("sid", ""))[:32]
    if not sid or sid == "default":
        return DATA_ROOT                 # legacy shared workspace
    ws = os.path.join(SESSIONS_DIR, sid)
    os.makedirs(os.path.join(ws, "history", "data"), exist_ok=True)
    return ws

def _ws_path(name):
    return os.path.join(_workspace(), name)

app = Flask(__name__, template_folder=TEMPLATES_DIR)

# ── helpers ──────────────────────────────────────────────────────────────────

def read_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── static / UI ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(TEMPLATES_DIR, "index.html")

# ── config ────────────────────────────────────────────────────────────────────

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(read_json(_ws_path("config.json"), {}))

@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.get_json(force=True)
    write_json(_ws_path("config.json"), data)
    return jsonify({"ok": True})

# ── profiles ──────────────────────────────────────────────────────────────────

@app.route("/api/profiles", methods=["GET"])
def get_profiles():
    return jsonify(read_json(PROFILES_FILE, {}))

@app.route("/api/profiles", methods=["POST"])
def save_profile():
    payload = request.get_json(force=True)
    # payload: { "name": "...", "profile": { project, geographies } }
    name    = payload.get("name", "").strip()
    profile = payload.get("profile", {})
    if not name:
        return jsonify({"ok": False, "error": "Profile name is required"}), 400
    profiles = read_json(PROFILES_FILE, {})
    profiles[name] = profile
    write_json(PROFILES_FILE, profiles)
    return jsonify({"ok": True})

@app.route("/api/profiles/<path:name>", methods=["DELETE"])
def delete_profile(name):
    profiles = read_json(PROFILES_FILE, {})
    if name not in profiles:
        return jsonify({"ok": False, "error": "Profile not found"}), 404
    del profiles[name]
    write_json(PROFILES_FILE, profiles)
    return jsonify({"ok": True})

# ── scrape ────────────────────────────────────────────────────────────────────

STALE_AFTER_SECONDS = 600   # a live scrape heartbeats the progress file every page;
                            # 10 min of silence means the process died

def _progress_is_stale(ws):
    """True if progress says 'running' but the file hasn't been touched in ages —
    i.e. the scrape process died without cleaning up."""
    path = os.path.join(ws, "progress.json")
    try:
        return (time.time() - os.path.getmtime(path)) > STALE_AFTER_SECONDS
    except OSError:
        return True

@app.route("/api/scrape", methods=["POST"])
def start_scrape():
    ws = _workspace()
    # Guard: this workspace already has a scrape running — unless it's a stale
    # leftover from a crashed run, in which case we self-heal and start fresh.
    prog = read_json(os.path.join(ws, "progress.json"), {})
    if prog.get("status") == "running" and not _progress_is_stale(ws):
        return jsonify({"ok": False, "message": "A scrape is already running for your session"}), 409
    # Write initial progress so the UI shows "starting" immediately
    write_json(os.path.join(ws, "progress.json"), {
        "status": "running",
        "geo": "",
        "keyword": "",
        "keyword_index": 0,
        "total_keywords": 0,
        "sp": 0,
        "organic": 0,
        "sb": 0,
        "sbv": 0,
        "message": "Starting scrape…"
    })

    # Fire scrape.py as a detached background process, bound to this workspace
    python = sys.executable
    scrape_script = os.path.join(BASE, "scrape.py")
    subprocess.Popen(
        [python, scrape_script, ws],
        cwd=BASE,
        stdout=open(os.path.join(ws, "scrape.log"), "w"),
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    return jsonify({"ok": True, "message": "Scrape started"})

# ── progress ──────────────────────────────────────────────────────────────────

@app.route("/api/progress", methods=["GET"])
def get_progress():
    ws = _workspace()
    prog = read_json(os.path.join(ws, "progress.json"), {
        "status": "idle",
        "message": "No scrape running"
    })
    # Self-heal: a scrape that stopped writing progress is dead, not running.
    if prog.get("status") == "running" and _progress_is_stale(ws):
        prog = {"status": "error",
                "message": "Scrape stopped unexpectedly — check the log and press Start to retry"}
        write_json(os.path.join(ws, "progress.json"), prog)
    return jsonify(prog)

@app.route("/api/debug-screenshot", methods=["GET"])
def debug_screenshot():
    """Screenshot of the page render captured when a scrape found zero SP."""
    ws = _workspace()
    path = os.path.join(ws, "debug_screenshot.png")
    if not os.path.exists(path):
        return jsonify({"error": "No screenshot yet"}), 404
    return send_from_directory(ws, "debug_screenshot.png")

@app.route("/api/debug-missed-sp", methods=["GET"])
def debug_missed_sp():
    """HTML of Sponsored-labelled product cards the extractor failed to catch."""
    path = os.path.join(_workspace(), "debug_missed_sp.html")
    if not os.path.exists(path):
        return jsonify({"exists": False, "content": ""})
    with open(path, encoding="utf-8", errors="ignore") as f:
        return jsonify({"exists": True, "content": f.read()[:30000]})

@app.route("/api/scrape-log", methods=["GET"])
def scrape_log():
    """Tail of this workspace's scrape.log — lets us see WHY a scrape died."""
    path = os.path.join(_workspace(), "scrape.log")
    if not os.path.exists(path):
        return jsonify({"log": "", "exists": False})
    with open(path, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return jsonify({"log": content[-8000:], "exists": True})

# ── data ──────────────────────────────────────────────────────────────────────

@app.route("/api/data", methods=["GET"])
def get_data():
    return jsonify(read_json(_ws_path("serp_data.json"), {}))

# ── history ───────────────────────────────────────────────────────────────────

@app.route("/api/history", methods=["GET"])
def list_history():
    hist = os.path.join(_workspace(), "history", "data")
    os.makedirs(hist, exist_ok=True)
    files = sorted(
        [f for f in os.listdir(hist) if f.endswith(".json")],
        reverse=True
    )
    return jsonify(files)

# ── insights: share-of-voice + trends (pure math, zero API) ──────────────────

def _valid_brand(brand):
    """Filter junk brand values (price strings, empties) from old scrapes."""
    if not brand or brand == "Unknown":
        return False
    if brand[0] in "$₹€£0123456789.":
        return False
    return True

def _sov_for_dataset(data):
    """Position-weighted share of voice over the scraped SERPs.

    Every placement on the page joins ONE visibility pool, weighted by where
    it sits (all weights computable from scraped data alone — nothing external):

        TOS banner (SB/SBV)      3.0   first thing seen, full width
        SP in top 4 page slots   2.0   above the fold
        ROS banner               1.5   full width, mid page
        SP below top 4           1.0   visible on scroll
        Organic at rank r        1/log2(r+1)   DCG decay: #1=1.0, #5≈0.39, #10≈0.29

    overall = brand's weight / total weight on the page  (sums to 100%)
    paid / organic = same math restricted to paid / organic slots only
    counts = raw slot tallies so every % is verifiable
    """
    import math
    out = {}
    for geo, keywords in (data or {}).items():
        out[geo] = {}
        for kw, payload in keywords.items():
            results = payload.get("results", [])
            banners = payload.get("sb_placements", [])
            pool, paid, org = {}, {}, {}
            counts = {}
            org_rank = 0
            for r in results:
                brand = (r.get("brand") or "Unknown").strip()
                is_sp = r.get("type") in ("SP", "SPONSORED")
                if not is_sp:
                    org_rank += 1          # rank among organic results, in page order
                if not _valid_brand(brand):
                    continue
                c = counts.setdefault(brand, {"sp": 0, "org": 0, "ban": 0})
                if is_sp:
                    w = 2.0 if r.get("position", 99) <= 4 else 1.0
                    paid[brand] = paid.get(brand, 0) + w
                    c["sp"] += 1
                else:
                    w = 1.0 / math.log2(org_rank + 1)
                    org[brand] = org.get(brand, 0) + w
                    c["org"] += 1
                pool[brand] = pool.get(brand, 0) + w
            for b in banners:
                brand = (b.get("brand") or "Unknown").strip()
                if not _valid_brand(brand):
                    continue
                w = 3.0 if b.get("placement") == "TOS" else 1.5
                paid[brand] = paid.get(brand, 0) + w
                pool[brand] = pool.get(brand, 0) + w
                counts.setdefault(brand, {"sp": 0, "org": 0, "ban": 0})["ban"] += 1
            pool_total = sum(pool.values())
            paid_total = sum(paid.values())
            org_total  = sum(org.values())
            scores = {}
            for brand in pool:
                scores[brand] = {
                    "overall": round(pool.get(brand, 0) / pool_total * 100, 1) if pool_total else 0,
                    "paid":    round(paid.get(brand, 0) / paid_total * 100, 1) if paid_total else 0,
                    "organic": round(org.get(brand, 0)  / org_total  * 100, 1) if org_total  else 0,
                    "counts":  counts.get(brand, {"sp": 0, "org": 0, "ban": 0}),
                }
            out[geo][kw] = scores
    return out

@app.route("/api/insights", methods=["GET"])
def insights():
    ws = _workspace()
    hist_dir = os.path.join(ws, "history", "data")
    current = _sov_for_dataset(read_json(os.path.join(ws, "serp_data.json"), {}))

    # Trends: blended SOV per brand over every archived scrape
    trends = {}  # {geo: {kw: {date: {brand: blended}}}}
    os.makedirs(hist_dir, exist_ok=True)
    for fname in sorted(os.listdir(hist_dir)):
        if not fname.endswith(".json") or "backup" in fname:
            continue
        # serp_data_2026-05-19_135524.json → 2026-05-19
        date = fname.replace("serp_data_", "").replace(".json", "")[:10]
        try:
            snap = _sov_for_dataset(read_json(os.path.join(hist_dir, fname), {}))
        except Exception:
            continue
        for geo, kws in snap.items():
            for kw, scores in kws.items():
                trends.setdefault(geo, {}).setdefault(kw, {})[date] = {
                    b: s["overall"] for b, s in scores.items()
                }
    return jsonify({"current": current, "trends": trends})

# ── compare: current run vs any archived run (pure math, zero API) ───────────

def _brand_state(payload):
    """Summarise one keyword's page into per-brand facts we can diff."""
    state = {}
    org_rank = 0
    for r in payload.get("results", []):
        brand = (r.get("brand") or "").strip()
        is_sp = r.get("type") in ("SP", "SPONSORED")
        if not is_sp:
            org_rank += 1
        if not _valid_brand(brand):
            continue
        s = state.setdefault(brand, {"sp": 0, "best_org": None, "tos_banner": 0, "ros_banner": 0, "sbv": 0})
        if is_sp:
            s["sp"] += 1
        elif s["best_org"] is None or org_rank < s["best_org"]:
            s["best_org"] = org_rank
    for b in payload.get("sb_placements", []):
        brand = (b.get("brand") or "").strip()
        if not _valid_brand(brand):
            continue
        s = state.setdefault(brand, {"sp": 0, "best_org": None, "tos_banner": 0, "ros_banner": 0, "sbv": 0})
        if b.get("placement") == "TOS":
            s["tos_banner"] += 1
        else:
            s["ros_banner"] += 1
        if b.get("type") == "SBV":
            s["sbv"] += 1
    return state

def _pretty_run_date(fname):
    # serp_data_2026-07-10_093015.json → "2026-07-10 09:30"
    stem = fname.replace("serp_data_", "").replace(".json", "")
    if "_" in stem and len(stem) >= 16:
        d, t = stem.split("_", 1)
        return f"{d} {t[:2]}:{t[2:4]}"
    return stem[:10]

@app.route("/api/compare", methods=["GET"])
def compare():
    ws = _workspace()
    fname = os.path.basename(request.args.get("file", ""))
    hist_path = os.path.join(ws, "history", "data", fname)
    if not fname or not os.path.exists(hist_path):
        return jsonify({"error": "History run not found"}), 404
    past    = read_json(hist_path, {})
    current = read_json(os.path.join(ws, "serp_data.json"), {})
    my_brand = (read_json(os.path.join(ws, "config.json"), {}).get("brand") or "").strip().lower()

    out = {}
    for geo, keywords in current.items():
        for kw, payload in keywords.items():
            past_payload = (past.get(geo) or {}).get(kw)
            if not past_payload:
                continue
            then = _brand_state(past_payload)
            now  = _brand_state(payload)
            rows, suggestions = [], []
            for brand in sorted(set(then) | set(now)):
                t = then.get(brand)
                n = now.get(brand)
                if t and not n:
                    status = "exited"
                elif n and not t:
                    status = "new"
                else:
                    gained = (n["sp"] > t["sp"]) or (n["tos_banner"] > t["tos_banner"]) or \
                             (t["best_org"] and n["best_org"] and n["best_org"] < t["best_org"])
                    lost   = (n["sp"] < t["sp"]) or (n["tos_banner"] < t["tos_banner"]) or \
                             (t["best_org"] and n["best_org"] and n["best_org"] > t["best_org"])
                    status = "gained" if gained and not lost else ("declined" if lost and not gained else "stable")
                rows.append({"brand": brand, "then": t, "now": n, "status": status})

                is_mine = my_brand and my_brand in brand.lower()
                nn = n or {"sp": 0, "best_org": None, "tos_banner": 0, "ros_banner": 0, "sbv": 0}
                tt = t or {"sp": 0, "best_org": None, "tos_banner": 0, "ros_banner": 0, "sbv": 0}
                # rule-based observations — plain counting, no AI anywhere
                if nn["tos_banner"] > tt["tos_banner"] and not is_mine:
                    suggestions.append(f"{brand} took a TOS banner on “{kw}” — if this is your keyword, consider defending with SB bids.")
                if is_mine and nn["sp"] < tt["sp"]:
                    suggestions.append(f"Your SP presence on “{kw}” dropped from {tt['sp']} to {nn['sp']} slots — check campaign budgets/bids.")
                if is_mine and tt["best_org"] and nn["best_org"] and nn["best_org"] < tt["best_org"]:
                    suggestions.append(f"Your best organic rank on “{kw}” improved #{tt['best_org']} → #{nn['best_org']} — keep the momentum.")
                if not is_mine and nn["sp"] >= tt["sp"] + 2:
                    suggestions.append(f"{brand} ramped up SP ads on “{kw}” ({tt['sp']} → {nn['sp']} slots) — increased competition for this term.")
            out.setdefault(geo, {})[kw] = {"brands": rows, "suggestions": suggestions}

    return jsonify({
        "compared_to": _pretty_run_date(fname),
        "file": fname,
        "geos": out,
    })

# ── changes feed: diff latest scrape vs previous ─────────────────────────────

def _brand_sets(payload):
    tos = {(b.get("brand") or "").strip() for b in payload.get("sb_placements", [])
           if b.get("placement") == "TOS"}
    sp  = {(r.get("brand") or "").strip() for r in payload.get("results", [])
           if r.get("type") in ("SP", "SPONSORED")}
    return tos, sp

@app.route("/api/changes", methods=["GET"])
def changes():
    ws = _workspace()
    hist_dir = os.path.join(ws, "history", "data")
    current = read_json(os.path.join(ws, "serp_data.json"), {})
    os.makedirs(hist_dir, exist_ok=True)
    hist_files = sorted(f for f in os.listdir(hist_dir)
                        if f.endswith(".json") and "backup" not in f)
    if not hist_files:
        return jsonify({"changes": [], "compared_to": None})
    prev_file = hist_files[-1]
    previous  = read_json(os.path.join(hist_dir, prev_file), {})
    prev_date = prev_file.replace("serp_data_", "").replace(".json", "")[:10]

    feed = []
    for geo, keywords in current.items():
        for kw, payload in keywords.items():
            prev_payload = (previous.get(geo) or {}).get(kw)
            if not prev_payload:
                continue
            cur_tos, cur_sp = _brand_sets(payload)
            old_tos, old_sp = _brand_sets(prev_payload)
            for b in sorted(cur_tos - old_tos):
                if b: feed.append({"geo": geo, "keyword": kw, "kind": "entered_tos",
                                   "brand": b, "text": f"{b} entered TOS banner on “{kw}”"})
            for b in sorted(old_tos - cur_tos):
                if b: feed.append({"geo": geo, "keyword": kw, "kind": "left_tos",
                                   "brand": b, "text": f"{b} lost its TOS banner on “{kw}”"})
            for b in sorted(cur_sp - old_sp):
                if b and b != "Unknown":
                    feed.append({"geo": geo, "keyword": kw, "kind": "new_sp",
                                 "brand": b, "text": f"{b} started running SP ads on “{kw}”"})
            for b in sorted(old_sp - cur_sp):
                if b and b != "Unknown":
                    feed.append({"geo": geo, "keyword": kw, "kind": "stopped_sp",
                                 "brand": b, "text": f"{b} stopped SP ads on “{kw}”"})
    return jsonify({"changes": feed, "compared_to": prev_date})

# ── scheduler: daily auto-scrape (runs on the server, zero API) ───────────────

@app.route("/api/schedule", methods=["GET"])
def get_schedule():
    return jsonify(read_json(_ws_path("schedule.json"), {"enabled": False, "time": "09:00", "last_run": None}))

@app.route("/api/schedule", methods=["POST"])
def save_schedule():
    payload = request.get_json(force=True)
    sched = read_json(_ws_path("schedule.json"), {"enabled": False, "time": "09:00", "last_run": None})
    sched["enabled"] = bool(payload.get("enabled", False))
    t = str(payload.get("time", "09:00"))
    try:
        hh, mm = t.split(":")
        assert 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
        sched["time"] = f"{int(hh):02d}:{int(mm):02d}"
    except Exception:
        return jsonify({"ok": False, "error": "Time must be HH:MM"}), 400
    write_json(_ws_path("schedule.json"), sched)
    return jsonify({"ok": True, "schedule": sched})

def _launch_scrape(ws):
    python = sys.executable
    scrape_script = os.path.join(BASE, "scrape.py")
    subprocess.Popen(
        [python, scrape_script, ws],
        cwd=BASE,
        stdout=open(os.path.join(ws, "scrape.log"), "w"),
        stderr=subprocess.STDOUT,
        close_fds=True,
    )

def watch_schedule():
    """Fire each workspace's scrape once a day at its configured time. Runs on
    the server — the user's laptop is irrelevant, no external service involved."""
    while True:
        try:
            # every workspace: legacy root + each sessions/<sid> folder
            workspaces = [DATA_ROOT]
            if os.path.isdir(SESSIONS_DIR):
                workspaces += [os.path.join(SESSIONS_DIR, d)
                               for d in os.listdir(SESSIONS_DIR)
                               if os.path.isdir(os.path.join(SESSIONS_DIR, d))]
            now   = datetime.now()
            today = now.strftime("%Y-%m-%d")
            for ws in workspaces:
                sched_path = os.path.join(ws, "schedule.json")
                sched = read_json(sched_path, {})
                if not sched.get("enabled"):
                    continue
                if sched.get("last_run") != today and now.strftime("%H:%M") >= sched.get("time", "09:00"):
                    progress = read_json(os.path.join(ws, "progress.json"), {})
                    if progress.get("status") != "running":
                        sched["last_run"] = today
                        write_json(sched_path, sched)
                        _launch_scrape(ws)
                        print(f"Scheduler: launched daily scrape for {os.path.basename(ws)} at {now.strftime('%H:%M')}")
        except Exception as e:
            print(f"Scheduler error: {e}")
        time.sleep(30)

schedule_thread = threading.Thread(target=watch_schedule, daemon=True)
schedule_thread.start()

# ── debug ─────────────────────────────────────────────────────────────────────

@app.route("/api/debug-page", methods=["GET"])
def debug_page():
    debug_path = os.path.join(BASE, "debug_render_page.html")
    if not os.path.exists(debug_path):
        return jsonify({"error": "No debug file yet — run a scrape first"})
    start  = int(request.args.get("start", 0))
    length = min(int(request.args.get("len", 3000)), 20000)
    with open(debug_path, encoding="utf-8", errors="ignore") as f:
        full = f.read()
    return jsonify({
        "content":    full[start:start + length],
        "total_size": len(full),
        "start":      start,
    })

# ── File-based trigger watcher (for Cowork/plugin use) ───────────────────────

def watch_for_trigger():
    """Watch for trigger.json — allows Cowork plugin to start scrapes without HTTP."""
    TRIGGER_FILE = os.path.join(BASE, "trigger.json")
    while True:
        try:
            if os.path.exists(TRIGGER_FILE):
                os.remove(TRIGGER_FILE)
                python = sys.executable
                scrape_script = os.path.join(BASE, "scrape.py")
                subprocess.Popen(
                    [python, scrape_script],
                    cwd=BASE,
                    stdout=open(os.path.join(BASE, "scrape.log"), "w"),
                    stderr=subprocess.STDOUT,
                    close_fds=True,
                )
        except Exception as e:
            print(f"Trigger watcher error: {e}")
        time.sleep(2)

trigger_thread = threading.Thread(target=watch_for_trigger, daemon=True)
trigger_thread.start()

# ── run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(HISTORY_DIR, exist_ok=True)
    # Create empty profiles.json if it doesn't exist yet
    if not os.path.exists(PROFILES_FILE):
        write_json(PROFILES_FILE, {})
    # Create empty progress.json if missing
    if not os.path.exists(PROGRESS_FILE):
        write_json(PROGRESS_FILE, {"status": "idle", "message": "No scrape running"})
    port = int(os.environ.get("PORT", 8765))
    print(f"Starting Amazon SERP Scraper at http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
