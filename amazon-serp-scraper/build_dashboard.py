import json, os, base64
from datetime import datetime, timezone
from collections import Counter

PLUGIN_LOGOS = os.path.join(
    os.path.expanduser("~"),
    "Library/Application Support/Claude/local-agent-mode-sessions/"
    "ea750059-ab70-47bc-ad88-9ee75eff1164/e0ff8dad-064d-4f45-8e1f-2f7035b23b5c/"
    "rpm/plugin_01E9F52GCf9BfSmgwvL8zA9r/skills/brand-apply/references/logos"
)

def _b64(fname):
    path = os.path.join(PLUGIN_LOGOS, fname)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

LOGO_WHITE_B64 = _b64("growisto-logo-white.png")
ICON_B64       = _b64("growisto-icon.png")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "serp_data.json")
OUT_FILE = os.path.join(BASE, "amazon_serp_dashboard.html")
CONFIG_FILE = os.path.join(BASE, "config.json")

with open(DATA_FILE) as f:
    data = json.load(f)
with open(CONFIG_FILE) as f:
    config = json.load(f)

project = config.get("project", "Brand")
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# Flatten all results
all_results = []
geos = sorted(data.keys())
all_keywords = set()
for geo in geos:
    for kw, info in data[geo].items():
        all_keywords.add(kw)
        for r in info.get("results", []):
            all_results.append({**r, "geo": geo, "keyword": kw})

keywords = sorted(all_keywords)
total = len(all_results)
sp_count = sum(1 for r in all_results if r["type"] == "SPONSORED")
org_count = sum(1 for r in all_results if r["type"] == "ORGANIC")
sbv_count = sum(1 for r in all_results if r["type"] in ("SB", "SBV"))

# Brand stats
brand_counter = Counter()
brand_sp = Counter()
brand_org = Counter()
for r in all_results:
    b = r["brand"]
    brand_counter[b] += 1
    if r["type"] == "SPONSORED":
        brand_sp[b] += 1
    elif r["type"] == "ORGANIC":
        brand_org[b] += 1

top_brands = brand_counter.most_common(15)
unique_brands = len(brand_counter)
top_brand = top_brands[0][0] if top_brands else "N/A"

# Keyword competitiveness
kw_brand_counts = {}
for r in all_results:
    kw = r["keyword"]
    if kw not in kw_brand_counts:
        kw_brand_counts[kw] = set()
    kw_brand_counts[kw].add(r["brand"])
most_competitive_kw = max(kw_brand_counts, key=lambda k: len(kw_brand_counts[k])) if kw_brand_counts else "N/A"
mc_count = len(kw_brand_counts.get(most_competitive_kw, set()))

# Find project brand appearances
project_lower = project.lower()
project_brand = None
for b in brand_counter:
    if b.lower() == project_lower:
        project_brand = b
        break

# Build insights
insights = []
if project_brand:
    pb_total = brand_counter[project_brand]
    pb_sp = brand_sp[project_brand]
    pb_org = brand_org[project_brand]
    pb_kws = set(r["keyword"] for r in all_results if r["brand"] == project_brand)
    insights.append(f"<b>{project_brand}</b> dominates with {pb_total} total appearances ({pb_sp} sponsored, {pb_org} organic) across {len(pb_kws)} keywords")

insights.append(f"Most competitive keyword: <b>{most_competitive_kw}</b> with {mc_count} unique brands")
insights.append(f"Total results scraped: <b>{total}</b> ({sp_count} sponsored, {org_count} organic)")
insights.append(f"Coverage: <b>{len(geos)}</b> geographies, <b>{len(keywords)}</b> keywords")
insights.append(f"Top brand overall: <b>{top_brand}</b> with {brand_counter[top_brand]} appearances")

if project_brand:
    insights.append(f"<b>{project_brand}</b> (your brand) appears {brand_counter[project_brand]} times — {brand_sp[project_brand]} sponsored, {brand_org[project_brand]} organic")

# Geo tabs HTML
geo_tabs = '<div class="tab active" data-geo="ALL" onclick="filterGeo(\'ALL\')">All</div>'
for g in geos:
    geo_tabs += f'<div class="tab" data-geo="{g}" onclick="filterGeo(\'{g}\')">{g}</div>'

# Keyword tabs HTML
kw_tabs = '<div class="tab active" data-kw="ALL" onclick="filterKw(\'ALL\')">All</div>'
for kw in keywords:
    kw_tabs += f'<div class="tab" data-kw="{kw}" onclick="filterKw(\'{kw}\')">{kw}</div>'

# Insights HTML
insights_html = "".join(f"<li>{ins}</li>" for ins in insights)

data_json = json.dumps(data, ensure_ascii=False)

logo_white_src = f"data:image/png;base64,{LOGO_WHITE_B64}" if LOGO_WHITE_B64 else ""
icon_src = f"data:image/png;base64,{ICON_B64}" if ICON_B64 else ""
favicon_tag = f'<link rel="icon" type="image/png" href="{icon_src}">' if icon_src else ""
logo_img = f'<img src="{logo_white_src}" alt="Growisto" style="height:36px;width:auto;">' if logo_white_src else '<span style="color:#FFFFFF;font-weight:800;font-size:1.1rem;">Growisto</span>'

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Amazon SERP Dashboard — {project.title()}</title>
{favicon_tag}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:       #F6F6F4;   /* Cultured */
    --surface:  #FFFFFF;   /* White cards */
    --surface2: #B8DBD9;   /* Powder Blue hover */
    --primary:  #367588;   /* Teal Blue */
    --accent:   #E35D34;   /* Flame */
    --text:     #1D1D20;   /* Raisin Black */
    --border:   #B8DBD9;   /* Powder Blue */
    --sp-color: #E35D34;   /* Flame – sponsored */
    --org-color:#367588;   /* Teal Blue – organic */
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text); font-family:'Poppins',sans-serif; min-height:100vh; }}

  header {{ background:var(--primary); padding:14px 24px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; }}
  .header-left {{ display:flex; align-items:center; gap:20px; }}
  .header-title {{ font-size:1rem; font-weight:600; color:#FFFFFF; }}
  .header-title span {{ color:#B8DBD9; }}
  .badge {{ background:#FFFFFF; color:var(--primary); font-size:0.7rem; font-weight:700; padding:4px 12px; border-radius:20px; white-space:nowrap; }}

  .container {{ max-width:1400px; margin:0 auto; padding:20px 16px; }}

  .summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-bottom:24px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:20px; }}
  .card h3 {{ font-size:0.7rem; color:var(--primary); font-weight:700; text-transform:uppercase; letter-spacing:.06em; margin-bottom:10px; }}
  .card .val {{ font-size:2rem; font-weight:700; color:var(--primary); }}
  .card .sub {{ font-size:0.8rem; color:var(--text); opacity:.6; margin-top:6px; font-weight:400; }}

  .insights {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:20px; margin-bottom:24px; }}
  .insights h2 {{ font-size:0.95rem; font-weight:700; color:var(--primary); margin-bottom:14px; display:flex; align-items:center; gap:8px; text-transform:uppercase; letter-spacing:.04em; }}
  .insights ul {{ list-style:none; display:flex; flex-direction:column; gap:8px; }}
  .insights li {{ padding:10px 14px; background:var(--bg); border-radius:8px; font-size:0.875rem; line-height:1.5; border-left:3px solid var(--accent); color:var(--text); }}

  .section-label {{ font-size:0.7rem; color:var(--primary); font-weight:700; text-transform:uppercase; letter-spacing:.06em; margin-bottom:8px; }}

  .tabs {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:16px; }}
  .tab {{ padding:7px 16px; border-radius:6px; cursor:pointer; font-size:0.8rem; font-weight:500; border:1.5px solid var(--border); background:var(--surface); color:var(--text); transition:.15s; font-family:'Poppins',sans-serif; }}
  .tab:hover {{ border-color:var(--primary); color:var(--primary); }}
  .tab.active {{ background:var(--primary); color:#FFFFFF; border-color:var(--primary); font-weight:700; }}

  .charts-grid {{ display:grid; grid-template-columns:2fr 1fr; gap:16px; margin-bottom:24px; }}
  @media(max-width:900px){{ .charts-grid {{ grid-template-columns:1fr; }} }}
  .chart-box {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:20px; }}
  .chart-box h3 {{ font-size:0.8rem; font-weight:700; color:var(--primary); text-transform:uppercase; letter-spacing:.04em; margin-bottom:16px; }}

  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:left; font-size:0.7rem; font-weight:700; color:#FFFFFF; text-transform:uppercase; letter-spacing:.05em; padding:11px 12px; background:var(--primary); position:sticky; top:0; }}
  td {{ padding:10px 12px; border-bottom:1px solid var(--border); font-size:0.85rem; vertical-align:middle; color:var(--text); background:var(--bg); }}
  tr:hover td {{ background:rgba(184,219,217,0.35); }}
  .type-badge {{ display:inline-block; padding:3px 9px; border-radius:4px; font-size:0.68rem; font-weight:700; letter-spacing:.02em; }}
  .type-sp  {{ background:rgba(227,93,52,0.12);  color:var(--sp-color); }}
  .type-org {{ background:rgba(54,117,136,0.12); color:var(--org-color); }}
  .brand-chip {{ display:inline-block; padding:2px 9px; background:var(--surface2); border-radius:4px; font-size:0.75rem; color:var(--primary); font-weight:500; }}
  a {{ color:var(--accent); text-decoration:none; }}
  a:hover {{ text-decoration:underline; color:#C94D28; }}
  .table-wrap {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; overflow:auto; max-height:600px; }}

  footer {{ text-align:center; padding:24px; font-size:0.75rem; color:var(--text); opacity:.5; border-top:1px solid var(--border); margin-top:8px; }}
</style>
</head>
<body>
<header>
  <div class="header-left">
    {logo_img}
    <div class="header-title">Amazon SERP Dashboard — <span>{project.title()}</span></div>
  </div>
  <div class="badge">Updated: {now}</div>
</header>

<div class="container">
  <div class="summary-grid">
    <div class="card">
      <h3>Total Results</h3>
      <div class="val" id="kpiTotal">{total}</div>
      <div class="sub" id="kpiTotalSub">{len(geos)} geo(s), {len(keywords)} keywords</div>
    </div>
    <div class="card">
      <h3>Sponsored</h3>
      <div class="val" id="kpiSponsored" style="color:var(--sp-color)">{sp_count}</div>
      <div class="sub" id="kpiSponsoredSub">{sp_count/total*100:.1f}% of all results</div>
    </div>
    <div class="card">
      <h3>Organic</h3>
      <div class="val" id="kpiOrganic" style="color:var(--org-color)">{org_count}</div>
      <div class="sub" id="kpiOrganicSub">{org_count/total*100:.1f}% of all results</div>
    </div>
    <div class="card">
      <h3>Unique Brands</h3>
      <div class="val" id="kpiBrands">{unique_brands}</div>
      <div class="sub" id="kpiBrandsSub">Top: {top_brand}</div>
    </div>
  </div>

  <div class="insights">
    <h2>Key Insights</h2>
    <ul>{insights_html}</ul>
  </div>

  <div class="section-label">Geography</div>
  <div class="tabs" id="geoTabs">{geo_tabs}</div>

  <div class="section-label">Keyword</div>
  <div class="tabs" id="kwTabs">{kw_tabs}</div>

  <div class="charts-grid">
    <div class="chart-box">
      <h3>Brand Presence (Top 15)</h3>
      <canvas id="brandChart"></canvas>
    </div>
    <div class="chart-box">
      <h3>Result Distribution</h3>
      <canvas id="distChart"></canvas>
    </div>
  </div>

  <div class="section-label">Search Results (SP + Organic)</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Geo</th>
          <th>Keyword</th>
          <th>Brand</th>
          <th>Title</th>
          <th>Type</th>
          <th>ASIN</th>
        </tr>
      </thead>
      <tbody id="resultsBody"></tbody>
    </table>
  </div>
</div>

<footer>Amazon SERP Dashboard &middot; {project.title()} &middot; Data scraped {now}</footer>

<script>
const DATA = {data_json};

let curGeo = 'ALL', curKw = 'ALL';
let brandChart = null, distChart = null;

function getFiltered() {{
  let rows = [];
  for (const [geo, kws] of Object.entries(DATA)) {{
    if (curGeo !== 'ALL' && geo !== curGeo) continue;
    for (const [kw, info] of Object.entries(kws)) {{
      if (curKw !== 'ALL' && kw !== curKw) continue;
      for (const r of (info.results || [])) {{
        rows.push({{...r, geo, keyword: kw}});
      }}
    }}
  }}
  return rows;
}}

function updateSummary(rows) {{
  const total = rows.length;
  const sp    = rows.filter(r => r.type === 'SPONSORED').length;
  const org   = rows.filter(r => r.type === 'ORGANIC').length;
  const brandSet = new Set(rows.map(r => r.brand));
  const geoSet   = new Set(rows.map(r => r.geo));
  const kwSet    = new Set(rows.map(r => r.keyword));

  const topBrand = (() => {{
    const cnt = {{}};
    rows.forEach(r => {{ cnt[r.brand] = (cnt[r.brand] || 0) + 1; }});
    return Object.entries(cnt).sort((a,b) => b[1]-a[1])[0]?.[0] || '—';
  }})();

  document.getElementById('kpiTotal').textContent       = total;
  document.getElementById('kpiTotalSub').textContent    = `${{geoSet.size}} geo(s), ${{kwSet.size}} keyword${{kwSet.size !== 1 ? 's' : ''}}`;
  document.getElementById('kpiSponsored').textContent   = sp;
  document.getElementById('kpiSponsoredSub').textContent= total ? (sp/total*100).toFixed(1)+'% of results' : '—';
  document.getElementById('kpiOrganic').textContent     = org;
  document.getElementById('kpiOrganicSub').textContent  = total ? (org/total*100).toFixed(1)+'% of results' : '—';
  document.getElementById('kpiBrands').textContent      = brandSet.size;
  document.getElementById('kpiBrandsSub').textContent   = `Top: ${{topBrand}}`;
}}

function filterGeo(g) {{
  curGeo = g;
  document.querySelectorAll('#geoTabs .tab').forEach(t => t.classList.toggle('active', t.dataset.geo === g));
  const rows = getFiltered();
  updateSummary(rows); renderTable(rows); updateCharts(rows);
}}

function filterKw(k) {{
  curKw = k;
  document.querySelectorAll('#kwTabs .tab').forEach(t => t.classList.toggle('active', t.dataset.kw === k));
  const rows = getFiltered();
  updateSummary(rows); renderTable(rows); updateCharts(rows);
}}

function renderTable(rows) {{
  rows = rows || getFiltered();
  const tbody = document.getElementById('resultsBody');
  tbody.innerHTML = rows.map((r, i) => `<tr>
    <td>${{i+1}}</td>
    <td>${{r.geo}}</td>
    <td>${{r.keyword}}</td>
    <td><span class="brand-chip">${{r.brand}}</span></td>
    <td>${{r.title.length > 80 ? r.title.slice(0,80)+'...' : r.title}}</td>
    <td><span class="type-badge ${{r.type==='SPONSORED'?'type-sp':'type-org'}}">${{r.type}}</span></td>
    <td><a href="${{r.url}}" target="_blank">${{r.asin}}</a></td>
  </tr>`).join('');
}}

function updateCharts(rows) {{
  rows = rows || getFiltered();
  const brandMap = {{}};
  rows.forEach(r => {{
    if (!brandMap[r.brand]) brandMap[r.brand] = {{sp:0, org:0}};
    if (r.type === 'SPONSORED') brandMap[r.brand].sp++;
    else brandMap[r.brand].org++;
  }});
  const sorted = Object.entries(brandMap).sort((a,b) => (b[1].sp+b[1].org) - (a[1].sp+a[1].org)).slice(0,15);
  const labels = sorted.map(s => s[0]);
  const spData = sorted.map(s => s[1].sp);
  const orgData = sorted.map(s => s[1].org);
  const sp = rows.filter(r => r.type==='SPONSORED').length;
  const org = rows.filter(r => r.type==='ORGANIC').length;

  const tickColor  = '#1D1D20';
  const gridColor  = 'rgba(184,219,217,0.5)';
  const spColor    = 'rgba(227,93,52,0.85)';
  const orgColor   = 'rgba(54,117,136,0.85)';
  const legendFont = {{ family: 'Poppins', size: 12 }};

  if (brandChart) brandChart.destroy();
  brandChart = new Chart(document.getElementById('brandChart'), {{
    type: 'bar',
    data: {{
      labels,
      datasets: [
        {{ label: 'Sponsored', data: spData, backgroundColor: spColor,  borderRadius: 3 }},
        {{ label: 'Organic',   data: orgData, backgroundColor: orgColor, borderRadius: 3 }}
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ labels: {{ color: tickColor, font: legendFont }} }} }},
      scales: {{
        x: {{ ticks: {{ color: tickColor, maxRotation: 45, font: {{ family: 'Poppins', size: 11 }} }}, grid: {{ color: gridColor }} }},
        y: {{ ticks: {{ color: tickColor, font: {{ family: 'Poppins', size: 11 }} }}, grid: {{ color: gridColor }} }}
      }}
    }}
  }});

  if (distChart) distChart.destroy();
  distChart = new Chart(document.getElementById('distChart'), {{
    type: 'doughnut',
    data: {{
      labels: ['Sponsored', 'Organic'],
      datasets: [{{ data: [sp, org], backgroundColor: [spColor, orgColor], borderWidth: 0 }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ labels: {{ color: tickColor, font: legendFont }} }} }}
    }}
  }});
}}

const _init = getFiltered();
updateSummary(_init);
renderTable(_init);
updateCharts(_init);
</script>
</body>
</html>'''

with open(OUT_FILE, "w") as f:
    f.write(html)

print(f"Dashboard built: {OUT_FILE}")
print(f"  Size: {len(html):,} chars / {len(html.encode()):,} bytes")
print(f"  {total} results, {len(geos)} geos, {len(keywords)} keywords, {unique_brands} brands")
