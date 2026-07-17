import { useState, useCallback, useMemo } from "react";
import Papa from "papaparse";

// ─── Brand colors ─────────────────────────────────────────────────────────────
const TEAL      = "#367588";
const POWDER    = "#B8DBD9";
const FLAME     = "#E35D34";
const RAISIN    = "#1D1D20";
const TEAL_DARK = "#2A5A6A";

// ─── Status helpers ───────────────────────────────────────────────────────────
const STATUS_ORDER  = { "Wasted Spend": 0, "Inefficient": 1, "Opportunity": 2, "Working": 3, "No Signal": 4 };
const STATUS_LABEL  = {
  "Working":      "✅ Working",
  "Wasted Spend": "💸 Wasted Spend",
  "Opportunity":  "💡 Opportunity",
  "Inefficient":  "⚠️ Inefficient",
  "No Signal":    "➖ No Signal",
};
const STATUS_COLOR = {
  "Working":      "#00A650",
  "Wasted Spend": "#E53E3E",
  "Opportunity":  "#D4860A",
  "Inefficient":  FLAME,
  "No Signal":    "#6B7280",
};

// ─── Currency symbols ─────────────────────────────────────────────────────────
const CURRENCY_SYMBOLS = {
  "USD":"$","INR":"₹","EUR":"€","GBP":"£","JPY":"¥",
  "CAD":"C$","AUD":"A$","MXN":"MX$","BRL":"R$","SGD":"S$",
  "AED":"AED ","SAR":"SAR ","SEK":"kr ","PLN":"zł ","TRY":"₺",
};

// ─── Safe parsers ─────────────────────────────────────────────────────────────
function parseFloatSafe(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = parseFloat(String(v).replace(/[,%]/g, "").trim());
  return isNaN(n) ? null : n;
}
function stripCurrency(str) {
  const n = parseFloat(String(str || "").replace(/[^0-9.\-]/g, ""));
  return isNaN(n) ? null : n;
}

// ─── SQPA parser (replicates app.py load_sqpa) ────────────────────────────────
function parseSQPA(text) {
  const lines = text.split(/\r?\n/);
  const metaLine = lines[0] || "";

  // Extract period from metadata row 0
  let period = "";
  const mWeek  = metaLine.match(/Select week=\["([^"]+)"\]/);
  const mYear  = metaLine.match(/Select year=\["([^"]+)"\]/);
  const mMonth = metaLine.match(/Select month=\["([^"]+)"\]/);
  if (mWeek) period = mWeek[1];
  else if (mYear && mMonth) period = `${mMonth[1]} ${mYear[1]}`;
  else period = metaLine.split(",")[0]?.replace(/"/g, "").trim() || "";

  // Skip row 0 (metadata); parse from row 1 which has headers
  const dataText = lines.slice(1).join("\n");
  const result = Papa.parse(dataText, {
    header: true,
    skipEmptyLines: true,
    transformHeader: h => h.trim(),
  });

  const df = result.data.map(row => {
    const atcVal = row["Cart Adds: Brand Share %"] ?? row["Add to Cart: Brand Share %"] ?? "";
    return {
      Keyword: String(row["Search Query"] || "").trim().toLowerCase(),
      SQV:     parseFloatSafe(row["Search Query Volume"]),
      IS:      parseFloatSafe(row["Impressions: Brand Share %"]),
      CS:      parseFloatSafe(row["Clicks: Brand Share %"]),
      ATC:     parseFloatSafe(atcVal),
      PS:      parseFloatSafe(row["Purchases: Brand Share %"]),
    };
  }).filter(r => r.Keyword);

  return { df, period };
}

// ─── STIS parser (replicates app.py load_stis) ───────────────────────────────
function parseSTIS(text) {
  const result = Papa.parse(text, {
    header: true,
    skipEmptyLines: true,
    transformHeader: h => h.trim(),
  });
  const rows = result.data;
  if (!rows.length) throw new Error("STIS file appears empty.");

  const cols = Object.keys(rows[0]);

  // Find sales column: contains "total sales", NOT "acos"
  const salesCol = cols.find(c => c.toLowerCase().includes("total sales") && !c.toLowerCase().includes("acos"));
  if (!salesCol) throw new Error(`Could not find total sales column. Columns found: ${cols.join(", ")}`);

  const ordersCol = cols.find(c => c.toLowerCase().includes("total orders"));
  if (!ordersCol) throw new Error(`Could not find total orders column. Columns found: ${cols.join(", ")}`);

  const isCol = cols.find(c => c.toLowerCase().includes("impression share"));

  // Detect currency
  let cur = "$";
  const currencyCol = cols.find(c => c.toLowerCase() === "currency");
  if (currencyCol) {
    const modes = {};
    rows.forEach(r => {
      const v = (r[currencyCol] || "").trim().toUpperCase();
      if (v) modes[v] = (modes[v] || 0) + 1;
    });
    const topCode = Object.entries(modes).sort((a,b)=>b[1]-a[1])[0]?.[0];
    if (topCode) cur = CURRENCY_SYMBOLS[topCode] || topCode + " ";
  } else if (cols.includes("Spend")) {
    const firstSpend = rows.find(r => r["Spend"] && String(r["Spend"]).trim())?.[" Spend"] || rows[0]["Spend"] || "";
    const symMatch = String(firstSpend).match(/[^\d\s.,\-]+/);
    if (symMatch) cur = symMatch[0];
  }

  // Parse all rows
  const parsed = rows.map(row => {
    const spend       = stripCurrency(row["Spend"]);
    const sales       = stripCurrency(row[salesCol]);
    const clicks      = parseFloatSafe(row["Clicks"]);
    const impressions = parseFloatSafe(row["Impressions"]);
    const orders      = parseFloatSafe(row[ordersCol]);
    const keyword     = String(row["Customer Search Term"] || "").trim().toLowerCase();
    const campaign    = String(row["Campaign Name"] || "").trim();
    const portfolio   = String(row["Portfolio name"] || "").trim() || "No Portfolio";
    const dateStr     = row["Date"] || "";

    let stis_is = null;
    if (isCol) {
      const rawIS = String(row[isCol] || "").replace("%", "").trim();
      const p_is = parseFloat(rawIS);
      if (!isNaN(p_is)) stis_is = p_is;
    }

    return { keyword, campaign, portfolio, spend, sales, clicks, impressions, orders, stis_is, dateStr };
  }).filter(r => r.keyword);

  // Scale STIS_IS: if max <= 1.0, multiply by 100
  const validIS = parsed.filter(r => r.stis_is !== null).map(r => r.stis_is);
  if (validIS.length && Math.max(...validIS) <= 1.0) {
    parsed.forEach(r => { if (r.stis_is !== null) r.stis_is *= 100; });
  }

  // ── Campaign-level aggregation (keyword × campaign × portfolio) ─────────────
  const campMap = {};
  parsed.forEach(r => {
    const key = `${r.keyword}|||${r.campaign}|||${r.portfolio}`;
    if (!campMap[key]) {
      campMap[key] = {
        keyword: r.keyword, campaign: r.campaign, portfolio: r.portfolio,
        spend: 0, sales: 0, impressions: 0, clicks: 0, orders: 0,
        _IS_x_I: 0, _IS_imp: 0,
      };
    }
    const g = campMap[key];
    g.spend       += r.spend       ?? 0;
    g.sales       += r.sales       ?? 0;
    g.impressions += r.impressions ?? 0;
    g.clicks      += r.clicks      ?? 0;
    g.orders      += r.orders      ?? 0;
    if (r.stis_is !== null && (r.impressions ?? 0) > 0) {
      g._IS_x_I += r.stis_is * r.impressions;
      g._IS_imp += r.impressions;
    }
  });

  const campAgg = Object.values(campMap).map(g => {
    const stis_is = g._IS_imp > 0 ? g._IS_x_I / g._IS_imp : null;
    const acos    = g.sales > 0 ? g.spend / g.sales * 100 : null;
    const ctr     = g.impressions > 0 ? g.clicks / g.impressions * 100 : null;
    const cpc     = g.clicks > 0 ? g.spend / g.clicks : null;
    const cvr     = g.clicks > 0 ? g.orders / g.clicks * 100 : null;
    return { ...g, stis_is, acos, ctr, cpc, cvr };
  });

  // ── Keyword-level aggregation ─────────────────────────────────────────────
  const kwMap = {};
  campAgg.forEach(r => {
    if (!kwMap[r.keyword]) {
      kwMap[r.keyword] = {
        keyword: r.keyword, spend: 0, sales: 0, impressions: 0, clicks: 0, orders: 0,
        _portfolios: {}, _IS_x_I: 0, _IS_imp: 0, dates: [],
      };
    }
    const g = kwMap[r.keyword];
    g.spend       += r.spend;
    g.sales       += r.sales;
    g.impressions += r.impressions;
    g.clicks      += r.clicks;
    g.orders      += r.orders;
    g._portfolios[r.portfolio] = (g._portfolios[r.portfolio] || 0) + 1;
    if (r.stis_is !== null && r.impressions > 0) {
      g._IS_x_I += r.stis_is * r.impressions;
      g._IS_imp += r.impressions;
    }
  });

  parsed.forEach(r => {
    if (r.dateStr && kwMap[r.keyword]) kwMap[r.keyword].dates.push(r.dateStr);
  });

  const kwAgg = Object.values(kwMap).map(g => {
    const weightedIS  = g._IS_imp > 0 ? g._IS_x_I / g._IS_imp : null;
    const acos  = g.sales > 0 ? g.spend / g.sales * 100 : null;
    const ctr   = g.impressions > 0 ? g.clicks / g.impressions * 100 : null;
    const cpc   = g.clicks > 0 ? g.spend / g.clicks : null;
    const cvr   = g.clicks > 0 ? g.orders / g.clicks * 100 : null;
    const portfolio = Object.entries(g._portfolios).sort((a,b)=>b[1]-a[1])[0]?.[0] || "No Portfolio";
    const parsedDates = g.dates.map(d => new Date(d)).filter(d => !isNaN(d.getTime()));
    const dateMin = parsedDates.length ? new Date(Math.min(...parsedDates.map(d=>d.getTime()))) : null;
    const dateMax = parsedDates.length ? new Date(Math.max(...parsedDates.map(d=>d.getTime()))) : null;
    return { keyword: g.keyword, spend: g.spend, sales: g.sales, impressions: g.impressions,
      clicks: g.clicks, orders: g.orders, portfolio, weightedIS, acos, ctr, cpc, cvr, dateMin, dateMax };
  });

  return { kwAgg, campAgg, cur };
}

// ─── Merge SQPA + STIS ────────────────────────────────────────────────────────
function mergeData(sqpaDf, kwAgg) {
  const kwMap = {};
  kwAgg.forEach(r => { kwMap[r.keyword] = r; });
  return sqpaDf.map(sq => {
    const kw = kwMap[sq.Keyword] || {};
    return {
      Keyword:     sq.Keyword,
      SQV:         sq.SQV,
      IS:          sq.IS,
      CS:          sq.CS,
      ATC:         sq.ATC,
      PS:          sq.PS,
      Spend:       kw.spend       ?? null,
      Sales:       kw.sales       ?? null,
      ACOS:        kw.acos        ?? null,
      Portfolio:   kw.portfolio   ?? "No Portfolio",
      Impressions: kw.impressions ?? null,
      Clicks:      kw.clicks      ?? null,
      Orders:      kw.orders      ?? null,
      CTR:         kw.ctr         ?? null,
      CPC:         kw.cpc         ?? null,
      CVR:         kw.cvr         ?? null,
    };
  });
}

// ─── Classify (exact match to app.py classify()) ─────────────────────────────
function classify(row, t) {
  const spend = row.Spend ?? 0;
  const sales = row.Sales ?? 0;
  const acos  = row.ACOS  != null ? row.ACOS  : null;
  const is_v  = row.IS    ?? 0;
  const sqv   = row.SQV   ?? 0;

  if (spend >= t.waste_min_spend && sales === 0) return "Wasted Spend";
  if (is_v >= t.work_min_is && sales >= t.work_min_sales && acos !== null && acos <= t.work_max_acos) return "Working";
  if (acos !== null && acos > t.ineff_min_acos && spend >= t.ineff_min_spend && sales > 0) return "Inefficient";
  if (sqv >= t.opp_min_sqv && is_v < t.opp_max_is) return "Opportunity";
  return "No Signal";
}

// ─── WoW builder ─────────────────────────────────────────────────────────────
function buildWoW(curr, prev) {
  const prevMap = {};
  prev.forEach(r => { prevMap[r.Keyword] = r; });
  const currMap = {};
  curr.forEach(r => { currMap[r.Keyword] = r; });

  const allKeys = new Set([...curr.map(r=>r.Keyword), ...prev.map(r=>r.Keyword)]);
  const pct = (a, b) => (a==null||b==null||b===0) ? null : (a-b)/Math.abs(b)*100;
  const pp  = (a, b) => (a==null||b==null)        ? null : a-b;

  const rows = [];
  allKeys.forEach(kw => {
    const c = currMap[kw] || null;
    const p = prevMap[kw] || null;
    rows.push({
      Keyword:       kw,
      Portfolio:     c?.Portfolio || p?.Portfolio || "–",
      Status:        c?.Status    || "No Signal",
      Status_prev:   p?.Status    || "No Signal",
      Status_changed:(c?.Status||"No Signal") !== (p?.Status||"No Signal"),
      _in_curr: !!c, _in_prev: !!p,
      SQV: c?.SQV, IS: c?.IS, CS: c?.CS, ATC: c?.ATC, PS: c?.PS,
      Spend: c?.Spend, Sales: c?.Sales, ACOS: c?.ACOS,
      Impressions: c?.Impressions, Clicks: c?.Clicks, Orders: c?.Orders,
      SQV_prev: p?.SQV, IS_prev: p?.IS, CS_prev: p?.CS, ATC_prev: p?.ATC, PS_prev: p?.PS,
      Spend_prev: p?.Spend, Sales_prev: p?.Sales, ACOS_prev: p?.ACOS,
      Impressions_prev: p?.Impressions, Clicks_prev: p?.Clicks, Orders_prev: p?.Orders,
      SQV_delta:         pct(c?.SQV, p?.SQV),
      Spend_delta:       pct(c?.Spend, p?.Spend),
      Sales_delta:       pct(c?.Sales, p?.Sales),
      Impressions_delta: pct(c?.Impressions, p?.Impressions),
      Clicks_delta:      pct(c?.Clicks, p?.Clicks),
      Orders_delta:      pct(c?.Orders, p?.Orders),
      IS_delta:   pp(c?.IS, p?.IS),
      CS_delta:   pp(c?.CS, p?.CS),
      ATC_delta:  pp(c?.ATC, p?.ATC),
      PS_delta:   pp(c?.PS, p?.PS),
      ACOS_delta: pp(c?.ACOS, p?.ACOS),
    });
  });
  return rows;
}

// ─── Formatters ──────────────────────────────────────────────────────────────
const fmtInt   = v => v==null ? "–" : Math.round(v).toLocaleString();
const fmtPct   = (v, dp=2) => v==null ? "–" : `${v.toFixed(dp)}%`;
const fmtCur   = (v, sym, dp=2) => v==null ? "–" : `${sym}${Math.abs(v).toLocaleString("en-US",{minimumFractionDigits:dp,maximumFractionDigits:dp})}`;
const fmtDate  = d => d ? d.toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"}) : "–";
const fmtDelta = (v, suffix="%", dp=1) => v==null ? "–" : `${v>0?"+":""}${v.toFixed(dp)}${suffix}`;

// ─── CSV helpers ──────────────────────────────────────────────────────────────
function toCSV(rows, columns) {
  const hdr  = columns.map(c=>`"${c.label}"`).join(",");
  const body = rows.map(r=>columns.map(c=>`"${String(c.get(r)??"").replace(/"/g,'""')}"`).join(",")).join("\n");
  return hdr+"\n"+body;
}
function downloadCSV(content, filename) {
  const blob = new Blob([content],{type:"text/csv;charset=utf-8;"});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href=url; a.download=filename; a.click();
  URL.revokeObjectURL(url);
}

// ─── Small UI components ──────────────────────────────────────────────────────
function Slider({ label, min, max, step, value, onChange, sym="" }) {
  return (
    <div style={{marginBottom:12}}>
      <div style={{display:"flex",justifyContent:"space-between",marginBottom:2}}>
        <span style={{fontSize:10,fontWeight:600,color:POWDER}}>{label}</span>
        <span style={{fontSize:10,fontWeight:700,color:"#fff",background:TEAL_DARK,padding:"1px 7px",borderRadius:20}}>{sym}{value}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e=>onChange(parseFloat(e.target.value))}
        style={{width:"100%",accentColor:POWDER,cursor:"pointer"}} />
    </div>
  );
}

function KPICard({ label, value, color }) {
  return (
    <div style={{flex:1,background:POWDER,borderLeft:`4px solid ${color}`,padding:"10px 14px",
      borderRadius:"0 8px 8px 0",minWidth:0,overflow:"hidden"}}>
      <div style={{fontSize:11,fontWeight:600,color:RAISIN,whiteSpace:"nowrap",marginBottom:3}}>{label}</div>
      <div style={{fontSize:19,fontWeight:700,color,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{value}</div>
    </div>
  );
}

function TabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick} style={{
      padding:"9px 16px",border:"none",borderBottom:active?`3px solid ${TEAL}`:"3px solid transparent",
      background:"transparent",color:active?TEAL:RAISIN,fontWeight:active?700:500,
      fontSize:12.5,cursor:"pointer",fontFamily:"inherit",whiteSpace:"nowrap",
    }}>{children}</button>
  );
}

function FileDropZone({ label, file, onChange }) {
  return (
    <label style={{
      display:"block",border:`2px dashed ${POWDER}`,borderRadius:8,
      padding:"14px 12px",cursor:"pointer",background:"#fff",textAlign:"center",
    }}
    onDragOver={e=>{e.preventDefault();e.currentTarget.style.borderColor=TEAL;}}
    onDragLeave={e=>{e.currentTarget.style.borderColor=POWDER;}}
    onDrop={e=>{e.preventDefault();e.currentTarget.style.borderColor=POWDER;const f=e.dataTransfer.files[0];if(f)onChange(f);}}>
      <input type="file" accept=".csv" style={{display:"none"}}
        onChange={e=>{if(e.target.files[0])onChange(e.target.files[0]);e.target.value="";}} />
      {file
        ? <span style={{color:TEAL,fontWeight:600,fontSize:12}}>✓ {file.name}</span>
        : <span style={{color:"#9ca3af",fontSize:12}}>{label}</span>}
    </label>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function App() {
  const [sqpaFile,     setSqpaFile]     = useState(null);
  const [stisFile,     setStisFile]     = useState(null);
  const [sqpaPrevFile, setSqpaPrevFile] = useState(null);
  const [stisPrevFile, setStisPrevFile] = useState(null);
  const [data,         setData]         = useState(null);
  const [prevData,     setPrevData]     = useState(null);
  const [error,        setError]        = useState("");
  const [loading,      setLoading]      = useState(false);
  const [activeTab,    setActiveTab]    = useState(0);
  const [selectedKw,   setSelectedKw]   = useState(null);
  const [selPortfolios,setSelPortfolios]= useState(null); // null = all
  const [showChangedOnly,setShowChangedOnly]=useState(false);
  const [sort, setSort] = useState({col:null,dir:0});

  const [thresholds, setThresholds] = useState({
    work_min_is:5, work_max_acos:30, work_min_sales:0,
    opp_min_sqv:500, opp_max_is:5,
    ineff_min_acos:30, ineff_min_spend:5,
    waste_min_spend:5,
  });
  const setT = (k,v) => setThresholds(t=>({...t,[k]:v}));

  function readFile(file) {
    return new Promise((res,rej)=>{
      const r=new FileReader();
      r.onload=e=>res(e.target.result);
      r.onerror=()=>rej(new Error("Failed to read "+file.name));
      r.readAsText(file);
    });
  }

  async function processFiles() {
    setLoading(true); setError(""); setData(null); setPrevData(null);
    try {
      const [sqpaText, stisText] = await Promise.all([readFile(sqpaFile), readFile(stisFile)]);
      const { df: sqpaDf, period: sqpaPeriod } = parseSQPA(sqpaText);
      const { kwAgg, campAgg, cur } = parseSTIS(stisText);
      const merged = mergeData(sqpaDf, kwAgg);
      const allDates = kwAgg.flatMap(k=>[k.dateMin,k.dateMax]).filter(Boolean);
      const stisRange = allDates.length
        ? `${fmtDate(new Date(Math.min(...allDates.map(d=>d.getTime()))))} → ${fmtDate(new Date(Math.max(...allDates.map(d=>d.getTime()))))}`
        : "–";
      const portfolios = [...new Set(merged.map(r=>r.Portfolio).filter(Boolean))].sort();
      setData({ merged, campAgg, sqpaPeriod, stisRange, cur, portfolios });
      setSelPortfolios(null);

      if (sqpaPrevFile && stisPrevFile) {
        const [pSqpa, pStis] = await Promise.all([readFile(sqpaPrevFile), readFile(stisPrevFile)]);
        const { df: pDf, period: pPeriod } = parseSQPA(pSqpa);
        const { kwAgg: pKwAgg, campAgg: pCampAgg, cur: pCur } = parseSTIS(pStis);
        const pMerged = mergeData(pDf, pKwAgg);
        const pDates = pKwAgg.flatMap(k=>[k.dateMin,k.dateMax]).filter(Boolean);
        const pRange = pDates.length
          ? `${fmtDate(new Date(Math.min(...pDates.map(d=>d.getTime()))))} → ${fmtDate(new Date(Math.max(...pDates.map(d=>d.getTime()))))}`
          : "–";
        setPrevData({ merged: pMerged, campAgg: pCampAgg, sqpaPeriod: pPeriod, stisRange: pRange, cur: pCur });
      }
    } catch(e) { setError(e.message); }
    setLoading(false);
  }

  // ── Derived ──────────────────────────────────────────────────────────────────
  const { filtered, filteredPrev, wowRows, counts } = useMemo(() => {
    if (!data) return {filtered:[],filteredPrev:[],wowRows:[],counts:{}};
    const portFilter = selPortfolios && selPortfolios.length>0 ? selPortfolios : null;
    const applyF = merged => {
      let rows = portFilter ? merged.filter(r=>portFilter.includes(r.Portfolio)) : [...merged];
      rows = rows.map(r=>({...r, Status:classify(r,thresholds)}));
      rows.sort((a,b)=>(STATUS_ORDER[a.Status]??99)-(STATUS_ORDER[b.Status]??99));
      return rows;
    };
    const filtered = applyF(data.merged);
    let filteredPrev=[], wowRows=[];
    if (prevData) {
      filteredPrev = applyF(prevData.merged);
      wowRows = buildWoW(filtered, filteredPrev);
    }
    const counts = {
      all: filtered.length,
      working: filtered.filter(r=>r.Status==="Working").length,
      wasted:  filtered.filter(r=>r.Status==="Wasted Spend").length,
      opp:     filtered.filter(r=>r.Status==="Opportunity").length,
      ineff:   filtered.filter(r=>r.Status==="Inefficient").length,
    };
    return {filtered,filteredPrev,wowRows,counts};
  }, [data,prevData,selPortfolios,thresholds]);

  const hasWoW = !!prevData;
  const cur    = data?.cur || "$";

  const tabData = useMemo(()=>({
    0: filtered,
    1: filtered.filter(r=>r.Status==="Working").sort((a,b)=>(b.Sales??0)-(a.Sales??0)),
    2: filtered.filter(r=>r.Status==="Wasted Spend").sort((a,b)=>(b.Spend??0)-(a.Spend??0)),
    3: filtered.filter(r=>r.Status==="Opportunity").sort((a,b)=>(b.SQV??0)-(a.SQV??0)),
    4: filtered.filter(r=>r.Status==="Inefficient").sort((a,b)=>(b.ACOS??0)-(a.ACOS??0)),
  }),[filtered]);

  const sortedRows = useCallback((rows,s)=>{
    if (!s.col) return rows;
    const numCols = ["SQV","IS","CS","ATC","PS","Spend","Sales","ACOS","Impressions","Clicks","Orders","CTR","CPC","CVR"];
    const isNum = numCols.includes(s.col);
    return [...rows].sort((a,b)=>{
      const av = isNum?(a[s.col]??-Infinity):String(a[s.col]||"").toLowerCase();
      const bv = isNum?(b[s.col]??-Infinity):String(b[s.col]||"").toLowerCase();
      return s.dir===1?(bv>av?1:bv<av?-1:0):(av>bv?1:av<bv?-1:0);
    });
  },[]);

  function toggleSort(col){
    setSort(prev=>{
      if(prev.col!==col) return {col,dir:1};
      if(prev.dir===1) return {col,dir:-1};
      return {col:null,dir:0};
    });
    setSelectedKw(null);
  }

  const campRows = useMemo(()=>{
    if(!selectedKw||!data) return [];
    return data.campAgg.filter(r=>r.keyword===selectedKw);
  },[selectedKw,data]);

  const wowKPIs = useMemo(()=>{
    if(!hasWoW) return null;
    const cSpend=filtered.reduce((s,r)=>s+(r.Spend??0),0);
    const pSpend=filteredPrev.reduce((s,r)=>s+(r.Spend??0),0);
    const cSales=filtered.reduce((s,r)=>s+(r.Sales??0),0);
    const pSales=filteredPrev.reduce((s,r)=>s+(r.Sales??0),0);
    const cOrders=filtered.reduce((s,r)=>s+(r.Orders??0),0);
    const pOrders=filteredPrev.reduce((s,r)=>s+(r.Orders??0),0);
    const cAcos=cSales>0?cSpend/cSales*100:null;
    const pAcos=pSales>0?pSpend/pSales*100:null;
    const pct=(c,p)=>(p==null||p===0)?null:(c-p)/Math.abs(p)*100;
    const pp=(c,p)=>(c==null||p==null)?null:c-p;
    return {cSpend,pSpend,cSales,pSales,cAcos,pAcos,cOrders,pOrders,
      changed:wowRows.filter(r=>r.Status_changed).length,
      newKws:wowRows.filter(r=>!r._in_prev).length,
      lostKws:wowRows.filter(r=>!r._in_curr).length,
      spendDelta:pct(cSpend,pSpend), salesDelta:pct(cSales,pSales),
      acosDelta:pp(cAcos,pAcos), ordersDelta:pct(cOrders,pOrders),
    };
  },[filtered,filteredPrev,wowRows,hasWoW]);

  const totalSpend = filtered.reduce((s,r)=>s+(r.Spend??0),0);
  const totalSales = filtered.reduce((s,r)=>s+(r.Sales??0),0);
  const overallAcos = totalSales>0 ? totalSpend/totalSales*100 : null;

  const wowDisplay = useMemo(()=>showChangedOnly?wowRows.filter(r=>r.Status_changed):[...wowRows],[wowRows,showChangedOnly]);

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div style={{display:"flex",minHeight:"100vh",fontFamily:"'Poppins',sans-serif"}}>

      {/* SIDEBAR */}
      <div style={{width:230,flexShrink:0,background:TEAL,padding:"20px 16px",
        overflowY:"auto",position:"sticky",top:0,height:"100vh"}}>
        <div style={{marginBottom:18}}>
          <div style={{fontSize:14,fontWeight:700,color:"#fff",lineHeight:1.3}}>SQPA × STIS</div>
          <div style={{fontSize:10,color:POWDER,fontWeight:500,marginTop:1}}>Analyser (WoW) | Growisto</div>
        </div>

        {data && (
          <div style={{borderTop:`1px solid ${TEAL_DARK}`,paddingTop:14,marginBottom:14}}>
            <div style={{fontSize:10,fontWeight:700,color:POWDER,marginBottom:8,textTransform:"uppercase",letterSpacing:.5}}>Portfolio Filter</div>
            {data.portfolios.map(p=>(
              <label key={p} style={{display:"flex",alignItems:"center",gap:6,marginBottom:4,cursor:"pointer"}}>
                <input type="checkbox"
                  checked={selPortfolios===null||selPortfolios.includes(p)}
                  onChange={e=>{
                    setSelPortfolios(prev=>{
                      const all=prev===null?data.portfolios:prev;
                      if(e.target.checked){const next=[...new Set([...all,p])];return next.length===data.portfolios.length?null:next;}
                      else{const next=all.filter(x=>x!==p);return next.length?next:[p];}
                    });
                  }}
                  style={{accentColor:POWDER}}/>
                <span style={{fontSize:10,color:"#fff",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{p}</span>
              </label>
            ))}
            {selPortfolios!==null&&(
              <button onClick={()=>setSelPortfolios(null)} style={{
                background:"transparent",border:`1px solid ${POWDER}`,color:POWDER,
                fontSize:9,padding:"2px 8px",borderRadius:4,cursor:"pointer",fontFamily:"inherit",marginTop:4
              }}>Select All</button>
            )}
          </div>
        )}

        <div style={{borderTop:`1px solid ${TEAL_DARK}`,paddingTop:14}}>
          <div style={{fontSize:10,fontWeight:700,color:POWDER,marginBottom:10,textTransform:"uppercase",letterSpacing:.5}}>⚙️ Thresholds</div>

          <div style={{fontSize:9,fontWeight:700,color:STATUS_COLOR["Working"],marginBottom:6}}>✅ Working</div>
          <Slider label="Min IS (%)" min={0} max={50} step={0.5} value={thresholds.work_min_is} onChange={v=>setT("work_min_is",v)}/>
          <Slider label="Max ACOS (%)" min={0} max={150} step={1} value={thresholds.work_max_acos} onChange={v=>setT("work_max_acos",v)}/>
          <Slider label={`Min Sales (${cur})`} min={0} max={500} step={5} value={thresholds.work_min_sales} onChange={v=>setT("work_min_sales",v)}/>

          <div style={{fontSize:9,fontWeight:700,color:STATUS_COLOR["Opportunity"],marginBottom:6,marginTop:10}}>💡 Opportunity</div>
          <Slider label="Min SQV" min={0} max={10000} step={100} value={thresholds.opp_min_sqv} onChange={v=>setT("opp_min_sqv",v)}/>
          <Slider label="Max IS (%)" min={0} max={50} step={0.5} value={thresholds.opp_max_is} onChange={v=>setT("opp_max_is",v)}/>

          <div style={{fontSize:9,fontWeight:700,color:STATUS_COLOR["Inefficient"],marginBottom:6,marginTop:10}}>⚠️ Inefficient</div>
          <Slider label="Min ACOS (%)" min={0} max={150} step={1} value={thresholds.ineff_min_acos} onChange={v=>setT("ineff_min_acos",v)}/>
          <Slider label={`Min Spend (${cur})`} min={0} max={200} step={1} value={thresholds.ineff_min_spend} onChange={v=>setT("ineff_min_spend",v)}/>

          <div style={{fontSize:9,fontWeight:700,color:STATUS_COLOR["Wasted Spend"],marginBottom:6,marginTop:10}}>💸 Wasted Spend</div>
          <Slider label={`Min Spend (${cur})`} min={0} max={200} step={1} value={thresholds.waste_min_spend} onChange={v=>setT("waste_min_spend",v)}/>
        </div>
      </div>

      {/* MAIN */}
      <div style={{flex:1,padding:"24px 28px",overflowY:"auto",minWidth:0}}>

        {/* Header */}
        <div style={{background:`linear-gradient(135deg,${TEAL},${TEAL_DARK})`,color:"#fff",
          padding:"18px 22px",borderRadius:8,marginBottom:4}}>
          <h1 style={{margin:0,fontSize:21,fontWeight:700,display:"flex",alignItems:"center",gap:10}}>
            📊 Keyword-Level Organic Tracker
          </h1>
          <p style={{margin:"4px 0 0",color:POWDER,fontSize:12}}>
            SQPA brand share × STIS paid performance — combined keyword intelligence
          </p>
        </div>
        <div style={{height:4,background:FLAME,borderRadius:2,marginBottom:20}}/>

        {/* Upload */}
        <div style={{background:"#fff",border:`1px solid ${POWDER}`,borderRadius:8,padding:"16px 18px",marginBottom:20}}>
          <div style={{fontSize:13,fontWeight:700,color:TEAL,marginBottom:12}}>📂 Upload Reports</div>

          <div style={{fontSize:10,fontWeight:700,color:TEAL,marginBottom:8,textTransform:"uppercase",letterSpacing:.4}}>Current Period</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:14}}>
            <div>
              <div style={{fontSize:11,fontWeight:600,color:RAISIN,marginBottom:5}}>SQPA — Search Query Performance</div>
              <FileDropZone label="Drop SQPA CSV or click to browse" file={sqpaFile} onChange={setSqpaFile}/>
            </div>
            <div>
              <div style={{fontSize:11,fontWeight:600,color:RAISIN,marginBottom:5}}>STIS — Search Term Impression Share</div>
              <FileDropZone label="Drop STIS CSV or click to browse" file={stisFile} onChange={setStisFile}/>
            </div>
          </div>

          <div style={{fontSize:10,fontWeight:700,color:TEAL,marginBottom:6,textTransform:"uppercase",letterSpacing:.4}}>
            Previous Period <span style={{fontWeight:400,color:"#9ca3af",textTransform:"none",fontSize:10}}>— optional, unlocks 📊 WoW tab</span>
          </div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:14}}>
            <div>
              <div style={{fontSize:11,fontWeight:600,color:RAISIN,marginBottom:5}}>SQPA — Previous Week</div>
              <FileDropZone label="Drop previous SQPA CSV" file={sqpaPrevFile} onChange={setSqpaPrevFile}/>
            </div>
            <div>
              <div style={{fontSize:11,fontWeight:600,color:RAISIN,marginBottom:5}}>STIS — Previous Week</div>
              <FileDropZone label="Drop previous STIS CSV" file={stisPrevFile} onChange={setStisPrevFile}/>
            </div>
          </div>

          <button disabled={!sqpaFile||!stisFile||loading} onClick={processFiles}
            style={{background:(!sqpaFile||!stisFile||loading)?POWDER:TEAL,color:"#fff",border:"none",
              borderRadius:6,padding:"9px 22px",fontSize:12.5,fontWeight:700,cursor:(!sqpaFile||!stisFile||loading)?"not-allowed":"pointer",
              fontFamily:"inherit"}}>
            {loading?"Processing…":"Analyse →"}
          </button>

          {error&&(
            <div style={{marginTop:10,background:"#fef0ec",border:`1px solid ${FLAME}`,
              borderRadius:6,padding:"9px 14px",fontSize:11,color:FLAME}}>
              ⚠ {error}
            </div>
          )}
        </div>

        {!data&&!loading&&(
          <div style={{background:POWDER,border:`1px solid ${TEAL}`,borderRadius:8,
            padding:"14px 18px",fontSize:13,color:RAISIN}}>
            ℹ️ Upload both current period reports above to activate the tracker.
          </div>
        )}

        {data&&(
          <>
            {/* Period info bar */}
            <div style={{fontSize:11.5,color:RAISIN,marginBottom:12}}>
              <b>SQPA period:</b> {data.sqpaPeriod||"–"} &nbsp;·&nbsp;
              <b>STIS period:</b> {data.stisRange||"–"} &nbsp;·&nbsp;
              <b>{counts.all.toLocaleString()}</b> keywords tracked
            </div>

            {/* KPI cards */}
            <div style={{display:"flex",gap:8,marginBottom:16,flexWrap:"wrap"}}>
              <KPICard label="Total KWs"       value={counts.all.toLocaleString()}       color={TEAL}/>
              <KPICard label="✅ Working"       value={counts.working.toLocaleString()}   color={STATUS_COLOR["Working"]}/>
              <KPICard label="💸 Wasted"        value={counts.wasted.toLocaleString()}    color={STATUS_COLOR["Wasted Spend"]}/>
              <KPICard label="💡 Opportunity"   value={counts.opp.toLocaleString()}       color={STATUS_COLOR["Opportunity"]}/>
              <KPICard label="⚠️ Inefficient"  value={counts.ineff.toLocaleString()}     color={STATUS_COLOR["Inefficient"]}/>
              <KPICard label="Total Spend"      value={fmtCur(totalSpend,cur,0)}          color={TEAL}/>
              <KPICard label="Overall ACOS"     value={overallAcos!=null?fmtPct(overallAcos,1):"N/A"} color={TEAL}/>
            </div>

            <div style={{height:1,background:POWDER,marginBottom:0}}/>

            {/* Tab bar */}
            <div style={{display:"flex",borderBottom:`2px solid ${POWDER}`,overflowX:"auto"}}>
              {[
                `All Keywords (${counts.all.toLocaleString()})`,
                `✅ Working (${counts.working})`,
                `💸 Wasted Spend (${counts.wasted})`,
                `💡 Opportunity (${counts.opp})`,
                `⚠️ Inefficient (${counts.ineff})`,
                ...(hasWoW?["📊 Week-on-Week"]:[]),
              ].map((label,i)=>(
                <TabBtn key={i} active={activeTab===i}
                  onClick={()=>{setActiveTab(i);setSelectedKw(null);if(i<5)setSort({col:null,dir:0});}}>
                  {label}
                </TabBtn>
              ))}
            </div>

            {/* Tab hints */}
            {activeTab===2&&<div style={{padding:"7px 12px",background:"#fef9f9",fontSize:10.5,color:"#6B7280",borderBottom:`1px solid ${POWDER}`}}>Spend ≥ {cur}{thresholds.waste_min_spend} with {cur}0 sales — review bids or pause.</div>}
            {activeTab===3&&<div style={{padding:"7px 12px",background:"#fefce8",fontSize:10.5,color:"#6B7280",borderBottom:`1px solid ${POWDER}`}}>SQV ≥ {thresholds.opp_min_sqv.toLocaleString()} and brand IS &lt; {thresholds.opp_max_is}% — brand is underrepresented; increase bids or add to campaigns.</div>}
            {activeTab===4&&<div style={{padding:"7px 12px",background:"#fff8f5",fontSize:10.5,color:"#6B7280",borderBottom:`1px solid ${POWDER}`}}>Sales &gt; {cur}0, ACOS &gt; {thresholds.ineff_min_acos}%, Spend ≥ {cur}{thresholds.ineff_min_spend} — converting but above target; optimise bids.</div>}

            {activeTab<5&&(
              <KeywordTable
                rows={tabData[activeTab]}
                sortedRows={sortedRows}
                sort={sort}
                onSort={toggleSort}
                cur={cur}
                selectedKw={selectedKw}
                onSelectKw={kw=>setSelectedKw(kw===selectedKw?null:kw)}
                campRows={campRows}
                tabKey={["all","working","wasted","opportunity","inefficient"][activeTab]}
              />
            )}

            {activeTab===5&&hasWoW&&(
              <WoWTab
                wowDisplay={wowDisplay}
                wowRows={wowRows}
                wowKPIs={wowKPIs}
                cur={cur}
                data={data}
                prevData={prevData}
                showChangedOnly={showChangedOnly}
                onShowChangedOnly={setShowChangedOnly}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ─── Keyword table component ──────────────────────────────────────────────────
function KeywordTable({ rows, sortedRows, sort, onSort, cur, selectedKw, onSelectKw, campRows, tabKey }) {
  const sorted = useMemo(()=>sortedRows(rows,sort),[rows,sort,sortedRows]);

  const columns = [
    {key:"Keyword",   label:"Keyword",             fmt:r=>r.Keyword?r.Keyword.replace(/\b\w/g,c=>c.toUpperCase()):"–"},
    {key:"Portfolio", label:"Portfolio",            fmt:r=>r.Portfolio||"–"},
    {key:"SQV",       label:"SQV",                 fmt:r=>fmtInt(r.SQV)},
    {key:"IS",        label:"Brand IS%",            fmt:r=>fmtPct(r.IS)},
    {key:"CS",        label:"Click Share%",         fmt:r=>fmtPct(r.CS)},
    {key:"ATC",       label:"ATC Share%",           fmt:r=>fmtPct(r.ATC)},
    {key:"PS",        label:"Purch. Share%",        fmt:r=>fmtPct(r.PS)},
    {key:"Spend",     label:`Spend (${cur})`,       fmt:r=>fmtCur(r.Spend,cur)},
    {key:"Sales",     label:`Sales (${cur})`,       fmt:r=>fmtCur(r.Sales,cur)},
    {key:"ACOS",      label:"ACOS%",                fmt:r=>fmtPct(r.ACOS,1)},
    {key:"Status",    label:"Status",               fmt:r=>STATUS_LABEL[r.Status]||r.Status},
  ];

  function doExport(){
    const csvCols = columns.map(c=>({label:c.label,get:r=>c.fmt(r)}));
    downloadCSV(toCSV(sorted,csvCols),`keywords_${tabKey}.csv`);
  }

  return (
    <div>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",
        padding:"8px 12px",background:"#f9f9f9",borderBottom:`1px solid ${POWDER}`}}>
        <span style={{fontSize:11.5,color:"#6B7280"}}>
          {sorted.length.toLocaleString()} keywords · Click a row to see campaign breakdown
        </span>
        <button onClick={doExport} style={{background:TEAL,color:"#fff",border:"none",
          borderRadius:5,padding:"5px 14px",fontSize:11,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>
          ⬇ Export CSV
        </button>
      </div>

      <div style={{overflowX:"auto"}}>
        <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
          <thead>
            <tr style={{background:TEAL,color:"#fff"}}>
              {columns.map(c=>(
                <th key={c.key} onClick={()=>onSort(c.key)} style={{
                  padding:"9px 12px",textAlign:"left",fontWeight:600,cursor:"pointer",
                  whiteSpace:"nowrap",userSelect:"none",fontSize:11,
                }}>
                  {c.label}{sort.col===c.key?(sort.dir===1?" ↓":" ↑"):""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length===0&&(
              <tr><td colSpan={columns.length} style={{padding:"24px",textAlign:"center",color:"#9ca3af",fontSize:13}}>
                No keywords match this filter.
              </td></tr>
            )}
            {sorted.map((row,i)=>{
              const isSelected = selectedKw===row.Keyword;
              return (
                <tr key={row.Keyword} onClick={()=>onSelectKw(row.Keyword)}
                  style={{background:isSelected?"#e8f4f5":i%2===0?"#fff":"#fafafa",
                    cursor:"pointer",borderLeft:isSelected?`3px solid ${TEAL}`:"3px solid transparent"}}
                  onMouseEnter={e=>{if(!isSelected)e.currentTarget.style.background="#f0f7f8";}}
                  onMouseLeave={e=>{if(!isSelected)e.currentTarget.style.background=i%2===0?"#fff":"#fafafa";}}>
                  {columns.map(c=>(
                    <td key={c.key} style={{padding:"8px 12px",borderBottom:"1px solid #f0f0f0",
                      whiteSpace:c.key==="Keyword"?"normal":"nowrap",
                      fontWeight:c.key==="Keyword"?600:400,
                      color:c.key==="Status"?(STATUS_COLOR[row.Status]||RAISIN):RAISIN,
                    }}>
                      {c.fmt(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedKw&&(
        <CampaignDrilldown kw={selectedKw} campRows={campRows} cur={cur}/>
      )}
    </div>
  );
}

// ─── Campaign drilldown ───────────────────────────────────────────────────────
function CampaignDrilldown({ kw, campRows, cur }) {
  const kwTitle = kw.replace(/\b\w/g,c=>c.toUpperCase());
  const columns = [
    {key:"campaign",   label:"Campaign",      fmt:r=>r.campaign||"–"},
    {key:"portfolio",  label:"Portfolio",     fmt:r=>r.portfolio||"–"},
    {key:"impressions",label:"Impressions",   fmt:r=>fmtInt(r.impressions)},
    {key:"stis_is",    label:"IS Share%",     fmt:r=>fmtPct(r.stis_is)},
    {key:"clicks",     label:"Clicks",        fmt:r=>fmtInt(r.clicks)},
    {key:"ctr",        label:"CTR%",          fmt:r=>fmtPct(r.ctr)},
    {key:"cpc",        label:`CPC (${cur})`,  fmt:r=>fmtCur(r.cpc,cur)},
    {key:"spend",      label:`Spend (${cur})`,fmt:r=>fmtCur(r.spend,cur)},
    {key:"sales",      label:`Sales (${cur})`,fmt:r=>fmtCur(r.sales,cur)},
    {key:"acos",       label:"ACOS%",         fmt:r=>fmtPct(r.acos,1)},
    {key:"cvr",        label:"CVR%",          fmt:r=>fmtPct(r.cvr)},
    {key:"orders",     label:"Orders",        fmt:r=>fmtInt(r.orders)},
  ];

  function doExport(){
    const csvCols = columns.map(c=>({label:c.label,get:r=>c.fmt(r)}));
    downloadCSV(toCSV(campRows,csvCols),`campaigns_${kw.replace(/\s+/g,"_")}.csv`);
  }

  return (
    <div style={{marginTop:14,borderRadius:8,overflow:"hidden",border:`1px solid ${POWDER}`}}>
      <div style={{background:POWDER,padding:"10px 16px",display:"flex",justifyContent:"space-between",
        alignItems:"center",borderLeft:`4px solid ${TEAL}`}}>
        <div>
          <span style={{fontWeight:700,color:TEAL,fontSize:13}}>📋 {kwTitle}</span>
          <span style={{color:RAISIN,fontSize:11,marginLeft:8}}>— campaign breakdown</span>
        </div>
        <button onClick={doExport} style={{background:TEAL,color:"#fff",border:"none",
          borderRadius:5,padding:"4px 12px",fontSize:11,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>
          ⬇ Export
        </button>
      </div>

      {campRows.length===0?(
        <div style={{padding:"14px",fontSize:12,color:"#9ca3af"}}>No campaign data found for this keyword.</div>
      ):(
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:11.5}}>
            <thead>
              <tr style={{background:"#f0f7f8"}}>
                {columns.map(c=>(
                  <th key={c.key} style={{padding:"8px 12px",textAlign:"left",fontWeight:600,
                    color:RAISIN,fontSize:10.5,whiteSpace:"nowrap",borderBottom:`1px solid ${POWDER}`}}>
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {campRows.map((r,i)=>(
                <tr key={i} style={{background:i%2===0?"#fff":"#fafafa"}}>
                  {columns.map(c=>(
                    <td key={c.key} style={{padding:"7px 12px",borderBottom:"1px solid #f5f5f5",
                      whiteSpace:c.key==="campaign"?"normal":"nowrap",
                      fontWeight:c.key==="campaign"?600:400}}>
                      {c.fmt(r)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── WoW Tab ──────────────────────────────────────────────────────────────────
function WoWTab({ wowDisplay, wowRows, wowKPIs, cur, data, prevData, showChangedOnly, onShowChangedOnly }) {
  const { cSpend, cSales, cAcos, cOrders, pSpend, pSales, pAcos, pOrders,
    changed, newKws, lostKws, spendDelta, salesDelta, acosDelta, ordersDelta } = wowKPIs;

  const deltaClr = (v, higherGood=true) => {
    if (v==null||Math.abs(v)<0.05) return "#6B7280";
    return (v>0)===higherGood ? "#00A650" : "#E53E3E";
  };

  const WCard = ({ label, value, delta, deltaIsGood=true, borderColor=TEAL, suffix="%" }) => (
    <div style={{flex:1,background:POWDER,borderLeft:`4px solid ${borderColor}`,
      padding:"10px 14px",borderRadius:"0 8px 8px 0",minWidth:0}}>
      <div style={{fontSize:10.5,fontWeight:600,color:RAISIN,marginBottom:2}}>{label}</div>
      <div style={{fontSize:17,fontWeight:700,color:borderColor}}>{value}</div>
      <div style={{fontSize:10.5,fontWeight:600,color:delta!=null?deltaClr(delta,deltaIsGood):"#9ca3af"}}>
        {delta!=null?`${delta>0?"+":""}${delta.toFixed(1)}${suffix}`:"–"}
      </div>
    </div>
  );

  const columns = [
    {key:"Keyword",     label:"Keyword",         fmt:r=>r.Keyword?.replace(/\b\w/g,c=>c.toUpperCase())||"–"},
    {key:"Portfolio",   label:"Portfolio",       fmt:r=>r.Portfolio||"–"},
    {key:"Status",      label:"Status (Curr)",   fmt:r=>STATUS_LABEL[r.Status]||r.Status},
    {key:"StatusChange",label:"Status Change",   fmt:r=>r.Status_changed
      ?`${STATUS_LABEL[r.Status_prev]||r.Status_prev} → ${STATUS_LABEL[r.Status]||r.Status}`:"–"},
    {key:"SQV_prev",    label:"SQV (Prev)",      fmt:r=>fmtInt(r.SQV_prev)},
    {key:"SQV",         label:"SQV (Curr)",      fmt:r=>fmtInt(r.SQV)},
    {key:"SQV_delta",   label:"SQV Δ%",          fmt:r=>fmtDelta(r.SQV_delta)},
    {key:"IS_prev",     label:"IS% (Prev)",      fmt:r=>fmtPct(r.IS_prev)},
    {key:"IS",          label:"IS% (Curr)",      fmt:r=>fmtPct(r.IS)},
    {key:"IS_delta",    label:"IS Δ (pp)",       fmt:r=>fmtDelta(r.IS_delta,"pp")},
    {key:"CS_prev",     label:"CS% (Prev)",      fmt:r=>fmtPct(r.CS_prev)},
    {key:"CS",          label:"CS% (Curr)",      fmt:r=>fmtPct(r.CS)},
    {key:"CS_delta",    label:"CS Δ (pp)",       fmt:r=>fmtDelta(r.CS_delta,"pp")},
    {key:"Spend_prev",  label:`Spend Prev`,      fmt:r=>fmtCur(r.Spend_prev,cur)},
    {key:"Spend",       label:`Spend Curr`,      fmt:r=>fmtCur(r.Spend,cur)},
    {key:"Spend_delta", label:"Spend Δ%",        fmt:r=>fmtDelta(r.Spend_delta)},
    {key:"Sales_prev",  label:`Sales Prev`,      fmt:r=>fmtCur(r.Sales_prev,cur)},
    {key:"Sales",       label:`Sales Curr`,      fmt:r=>fmtCur(r.Sales,cur)},
    {key:"Sales_delta", label:"Sales Δ%",        fmt:r=>fmtDelta(r.Sales_delta)},
    {key:"ACOS_prev",   label:"ACOS Prev%",      fmt:r=>fmtPct(r.ACOS_prev,1)},
    {key:"ACOS",        label:"ACOS Curr%",      fmt:r=>fmtPct(r.ACOS,1)},
    {key:"ACOS_delta",  label:"ACOS Δ (pp)",     fmt:r=>fmtDelta(r.ACOS_delta,"pp")},
    {key:"Orders_prev", label:"Orders (Prev)",   fmt:r=>fmtInt(r.Orders_prev)},
    {key:"Orders",      label:"Orders (Curr)",   fmt:r=>fmtInt(r.Orders)},
    {key:"Orders_delta",label:"Orders Δ%",       fmt:r=>fmtDelta(r.Orders_delta)},
  ];

  function doExport(){
    const csvCols = columns.map(c=>({label:c.label,get:r=>c.fmt(r)}));
    downloadCSV(toCSV(wowDisplay,csvCols),"wow_comparison.csv");
  }

  return (
    <div style={{paddingTop:14}}>
      {/* Period header */}
      <div style={{fontSize:11.5,padding:"9px 14px",background:"#f0f7f8",
        border:`1px solid ${POWDER}`,borderRadius:8,marginBottom:14}}>
        <b style={{color:TEAL}}>◀ Previous</b>&nbsp;
        SQPA {prevData.sqpaPeriod||"–"} · STIS {prevData.stisRange||"–"}
        &emsp;→&emsp;
        <b style={{color:TEAL}}>▶ Current</b>&nbsp;
        SQPA {data.sqpaPeriod||"–"} · STIS {data.stisRange||"–"}
      </div>

      {/* WoW KPI cards */}
      <div style={{display:"flex",gap:8,marginBottom:14,flexWrap:"wrap"}}>
        <WCard label="Total Spend"    value={fmtCur(cSpend,cur,0)} delta={spendDelta} deltaIsGood={false}/>
        <WCard label="Total Sales"    value={fmtCur(cSales,cur,0)} delta={salesDelta} deltaIsGood={true}/>
        <WCard label="Overall ACOS"   value={cAcos!=null?fmtPct(cAcos,1):"–"} delta={acosDelta} deltaIsGood={false} suffix="pp"/>
        <WCard label="Total Orders"   value={fmtInt(cOrders)} delta={ordersDelta} deltaIsGood={true}/>
        <WCard label="Status Changes" value={changed.toLocaleString()} delta={null} borderColor={FLAME}/>
        <WCard label="New Keywords"   value={newKws.toLocaleString()} delta={null} borderColor="#00A650"/>
        <WCard label="Lost Keywords"  value={lostKws.toLocaleString()} delta={null} borderColor="#E53E3E"/>
      </div>

      <div style={{height:1,background:POWDER,marginBottom:12}}/>

      {/* Controls */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
        <label style={{display:"flex",alignItems:"center",gap:8,fontSize:12,cursor:"pointer"}}>
          <input type="checkbox" checked={showChangedOnly} onChange={e=>onShowChangedOnly(e.target.checked)}
            style={{accentColor:TEAL}}/>
          Show only keywords with status changes
        </label>
        <button onClick={doExport} style={{background:TEAL,color:"#fff",border:"none",
          borderRadius:5,padding:"6px 16px",fontSize:11,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>
          ⬇ Export WoW CSV
        </button>
      </div>

      {/* WoW table */}
      <div style={{overflowX:"auto",border:`1px solid ${POWDER}`,borderRadius:8}}>
        <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
          <thead>
            <tr style={{background:TEAL,color:"#fff"}}>
              {columns.map(c=>(
                <th key={c.key} style={{padding:"8px 10px",textAlign:"left",fontWeight:600,
                  whiteSpace:"nowrap",fontSize:10}}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {wowDisplay.length===0&&(
              <tr><td colSpan={columns.length} style={{padding:"20px",textAlign:"center",color:"#9ca3af"}}>
                No keywords to show.
              </td></tr>
            )}
            {wowDisplay.map((row,i)=>(
              <tr key={row.Keyword} style={{
                background:row.Status_changed?(i%2===0?"#fff9f0":"#fff4e6"):(i%2===0?"#fff":"#fafafa")
              }}>
                {columns.map(c=>{
                  const v = c.fmt(row);
                  let color = RAISIN;
                  if(c.key==="Status") color=STATUS_COLOR[row.Status]||RAISIN;
                  if(c.key.endsWith("_delta")){
                    const raw=row[c.key];
                    if(raw!=null){
                      const isBad=c.key.includes("ACOS")||c.key.includes("Spend");
                      color=raw>0?(isBad?"#E53E3E":"#00A650"):raw<0?(isBad?"#00A650":"#E53E3E"):"#6B7280";
                    }
                  }
                  return (
                    <td key={c.key} style={{padding:"7px 10px",borderBottom:"1px solid #f0f0f0",
                      whiteSpace:(c.key==="Keyword"||c.key==="StatusChange")?"normal":"nowrap",
                      fontWeight:c.key==="Keyword"?600:400,color}}>
                      {v}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{padding:"7px 12px",fontSize:10.5,color:"#6B7280"}}>
        {wowDisplay.length.toLocaleString()} keywords · Δ% = % change · Δ (pp) = percentage-point change vs previous period
      </div>
    </div>
  );
}
