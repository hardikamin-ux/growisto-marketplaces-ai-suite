"""
Amazon P&L Tool — server
Serves the single-file dashboard and stores per-project month data so the team
shares one source of truth instead of each person's browser localStorage.

Storage layout (all under DATA_ROOT):
  projects/<slug>.json   { "name": "<display name>", "months": {...}, "cogs": {...} }

On Railway, set DATA_DIR=/data and mount a persistent volume there so data
survives restarts and redeploys. Locally it falls back to ./data.
"""

import json
import os
import re
import tempfile
import threading

from flask import Flask, jsonify, request, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.environ.get("DATA_DIR") or os.path.join(BASE, "data")
PROJECTS_DIR = os.path.join(DATA_ROOT, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

# Serialise writes — monthly uploads are low-frequency, but two people saving at
# once must not interleave and corrupt a project file.
_LOCK = threading.Lock()

app = Flask(__name__, static_folder=None)


def slugify(name):
    s = re.sub(r"[^A-Za-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s[:60]


def project_path(slug):
    return os.path.join(PROJECTS_DIR, slug + ".json")


def read_project(slug):
    p = project_path(slug)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_project(slug, payload):
    """Atomic write — a crash mid-save must not leave a truncated project file."""
    p = project_path(slug)
    fd, tmp = tempfile.mkstemp(dir=PROJECTS_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/projects", methods=["GET"])
def list_projects():
    """All projects with their month labels — drives the project picker."""
    out = []
    for fn in sorted(os.listdir(PROJECTS_DIR)):
        if not fn.endswith(".json"):
            continue
        slug = fn[:-5]
        d = read_project(slug) or {}
        months = d.get("months") or {}
        out.append({
            "slug": slug,
            "name": d.get("name") or slug,
            "months": sorted(months.keys()),
            "month_count": len(months),
        })
    return jsonify(out)


@app.route("/api/projects/<slug>", methods=["GET"])
def get_project(slug):
    d = read_project(slugify(slug))
    if d is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(d)


@app.route("/api/projects/<slug>", methods=["DELETE"])
def delete_project(slug):
    slug = slugify(slug)
    with _LOCK:
        p = project_path(slug)
        if not os.path.exists(p):
            return jsonify({"error": "not found"}), 404
        os.unlink(p)
    return jsonify({"ok": True})


@app.route("/api/projects/<slug>/months", methods=["POST"])
def put_months(slug):
    """Merge uploaded months into a project. Existing months with the same label
    are overwritten (re-uploading a corrected report should replace it); every
    other month already stored is left untouched."""
    slug = slugify(slug)
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or slug).strip()
    incoming = payload.get("months") or {}
    if not isinstance(incoming, dict) or not incoming:
        return jsonify({"error": "no months supplied"}), 400

    # Excel uploads carry a project's whole history, so they replace the stored
    # set; a single-month CSV merges. Without this the UI could show fewer months
    # than the server holds and the "replaced" months would reappear on reload.
    replace = bool(payload.get("replace"))

    with _LOCK:
        d = read_project(slug) or {"name": name, "months": {}, "cogs": {}}
        d["name"] = name or d.get("name") or slug
        d.setdefault("months", {})
        if replace:
            d["months"] = incoming
        else:
            d["months"].update(incoming)
        write_project(slug, d)
        stored = sorted(d["months"].keys())
    return jsonify({"ok": True, "slug": slug, "months": stored})


@app.route("/api/projects/<slug>/months/<path:label>", methods=["DELETE"])
def delete_month(slug, label):
    slug = slugify(slug)
    with _LOCK:
        d = read_project(slug)
        if d is None:
            return jsonify({"error": "not found"}), 404
        if label not in (d.get("months") or {}):
            return jsonify({"error": "month not found"}), 404
        del d["months"][label]
        write_project(slug, d)
        stored = sorted(d["months"].keys())
    return jsonify({"ok": True, "months": stored})


@app.route("/api/projects/<slug>/cogs", methods=["POST"])
def put_cogs(slug):
    """COGS assumptions are part of the project, so the whole team sees the same
    margin picture rather than each person's private guess."""
    slug = slugify(slug)
    payload = request.get_json(silent=True) or {}
    with _LOCK:
        d = read_project(slug)
        if d is None:
            return jsonify({"error": "not found"}), 404
        d["cogs"] = payload.get("cogs") or {}
        write_project(slug, d)
    return jsonify({"ok": True})


# ── static ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(BASE, "index.html")


@app.route("/<path:fn>")
def asset(fn):
    return send_from_directory(BASE, fn)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8770))
    print(f"Amazon P&L Tool on http://0.0.0.0:{port}  (data: {DATA_ROOT})")
    app.run(host="0.0.0.0", port=port, debug=False)
