"""A self-contained, local HTML report. No network, telemetry or CDN assets."""
from __future__ import annotations
import html
import json
import re
import numpy as np


def _points(frame, indices):
    result = []
    for i in indices:
        row = frame.iloc[int(i)]
        result.append({"i": int(i), "t": row.timestamp.isoformat(),
                       "o": float(row.original_value) if np.isfinite(row.original_value) else None,
                       "y": float(row.value) if np.isfinite(row.value) else None,
                       "lo": float(row.lower) if np.isfinite(row.lower) else None,
                       "hi": float(row.upper) if np.isfinite(row.upper) else None})
    return result


def render_report(report, frame):
    """Render only measured outputs. Unknown missing values have no accuracy score."""
    n = len(frame)
    overview_indices = set(np.linspace(0, n - 1, min(n, 1000), dtype=int).tolist())
    for gap in report["gaps"]:
        s, e = gap["start_index"], gap["end_index_exclusive"]
        overview_indices.update(i for i in (s - 1, s, e - 1, e) if 0 <= i < n)
    views = {}
    for gap in report["gaps"]:
        s, e = gap["start_index"], gap["end_index_exclusive"]
        a, b = max(0, s - 36), min(n, e + 36)
        indices = np.linspace(a, b - 1, min(b - a, 500), dtype=int)
        views[str(gap["id"])] = _points(frame, indices)
    payload = {"report": report, "overview": _points(frame, sorted(overview_indices)), "views": views}
    # HTML parsing precedes JSON parsing. Escape '<' so file names cannot close a
    # script element, and U+2028/U+2029 for compatibility with older JS engines.
    data = json.dumps(payload, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>GapLens · __TITLE__</title>
<style>
:root{--ink:#172c3c;--muted:#536b7b;--line:#dbe5e9;--bg:#f4f7f8;--blue:#087c94;--amber:#b66b12;--soft:#e9f5f7;--navy:#112b3b}*{box-sizing:border-box}body{margin:0;color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg)}a{color:var(--blue)}button,select{font:inherit}header{padding:24px max(24px,calc((100vw - 1320px)/2));background:var(--navy);color:white;display:flex;justify-content:space-between;gap:20px;align-items:center}.brand{font-weight:760;font-size:24px;letter-spacing:-1px}.brand span{color:#70d7e5}.badge{border:1px solid #456371;border-radius:30px;padding:5px 12px;font-size:12px;letter-spacing:1px}main{max-width:1368px;margin:auto;padding:36px 24px 50px}.eyebrow{text-transform:uppercase;font-size:11px;letter-spacing:1.8px;font-weight:750;color:var(--blue)}h1{font-size:clamp(29px,4vw,43px);letter-spacing:-1.7px;margin:5px 0 10px;line-height:1.15}h2{font-size:18px;margin:0 0 8px}h3{font-size:14px;margin:0 0 6px}.intro{max-width:830px;color:var(--muted);margin:0}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0}.button{display:inline-block;text-decoration:none;border:1px solid var(--line);background:white;color:var(--ink);border-radius:8px;padding:9px 15px;font-weight:650}.button.primary{background:var(--blue);border-color:var(--blue);color:white}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin:25px 0}.stat{padding:18px 20px;background:white;border:1px solid var(--line);border-radius:12px}.stat b{font-size:31px;letter-spacing:-1.3px;display:block}.stat span{color:var(--muted);font-size:12px}.grid{display:grid;grid-template-columns:310px minmax(0,1fr);gap:20px}.panel{background:white;border:1px solid var(--line);border-radius:13px;overflow:hidden}.panelhead{padding:19px 22px;border-bottom:1px solid var(--line)}.panelbody{padding:22px}.gaps{max-height:500px;overflow:auto}.gapbutton{display:block;width:100%;text-align:left;background:white;border:0;border-bottom:1px solid #edf1f3;padding:15px 20px;cursor:pointer;color:var(--ink)}.gapbutton:hover{background:#f5fafa}.gapbutton.active{background:var(--soft);box-shadow:inset 3px 0 var(--blue)}.gapbutton strong{font-size:13px}.gapbutton small{display:block;color:var(--muted);font-size:11px;margin-top:3px}.pill{font-size:10px;padding:2px 6px;background:#e4f4ed;color:#226a53;border-radius:10px;float:right}.pill.unresolved{background:#fff1dc;color:#8b550c}.charthead{display:flex;align-items:start;justify-content:space-between;gap:15px}.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--muted);margin-top:10px}.legend i{display:inline-block;vertical-align:middle;margin-right:5px;width:17px;height:3px;background:#6d7f89}.legend .recovery{background:var(--blue)}.legend .band{height:9px;background:#bce5ea}#chart{display:block;width:100%;height:auto;min-height:220px}.chartnote{color:var(--muted);font-size:11px;padding:0 22px 15px}.detailgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 0 15px}.detail{padding:12px 14px;background:var(--bg);border-radius:7px;font-size:12px}.detail b{display:block;font-size:17px}.detail span{color:var(--muted)}.note{padding:12px 15px;background:#fff7e9;border-left:3px solid #dda54a;font-size:12px;margin:12px 0}.footgrid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px}dl{margin:0;font-size:12px}dt{color:var(--muted);margin-top:9px}dd{margin:0;overflow-wrap:anywhere}.hash{font:11px/1.6 ui-monospace,Consolas,monospace}.muted{color:var(--muted)}ul{padding-left:19px;margin:8px 0;font-size:12px}.neighbors{font:11px/1.7 ui-monospace,Consolas,monospace;color:var(--muted);padding:8px 0}footer{font-size:11px;color:var(--muted);margin-top:28px}select{border:1px solid var(--line);border-radius:6px;padding:6px;background:white;color:var(--ink)}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:900px){.grid{grid-template-columns:1fr}.gaps{max-height:220px}.footgrid{grid-template-columns:1fr}.stats{grid-template-columns:repeat(2,1fr)}main{padding:25px 15px}.badge{display:none}}@media print{header{background:white;color:black}.toolbar{display:none}.grid,.footgrid{display:block}.panel{margin-bottom:15px}.gaps{max-height:none}.stat{break-inside:avoid}}
</style></head><body>
<header><div class="brand">Gap<span>Lens</span></div><div class="badge">LOCAL ANALYSIS · AUDITABLE RECOVERY</div></header>
<main><div class="eyebrow">Reconstruction report</div><h1>Fill the gap. Keep the evidence.</h1>
<p class="intro">Historical patterns and observed endpoints provide a reconstruction; calibrated bands show its uncertainty. Original observations are preserved, and unsupported gaps remain explicit.</p>
<div class="toolbar"><a class="button primary" href="repaired.csv" download>Download repaired CSV</a><a class="button" href="report.json" download>Download audit JSON</a><button class="button" id="print">Print report</button></div>
<div class="stats"><div class="stat"><b id="stat-repaired"></b><span>gaps reconstructed</span></div><div class="stat"><b id="stat-values"></b><span>missing samples reconstructed</span></div><div class="stat"><b id="stat-observed"></b><span>observations preserved</span></div><div class="stat"><b id="stat-target"></b><span>nominal whole-gap coverage target¹</span></div></div>
<div class="grid"><section class="panel"><div class="panelhead"><h2>Inspect a gap</h2><label class="sr-only" for="filter">Filter gaps</label><select id="filter"><option value="all">All gaps</option><option value="reconstructed">Reconstructed</option><option value="unresolved">Unresolved</option></select></div><div class="gaps" id="gap-list"></div></section>
<section class="panel"><div class="panelhead charthead"><div><h2 id="chart-title">Full input series</h2><div id="chart-subtitle" class="muted"></div><div class="legend"><span><i></i>Observed</span><span><i class="recovery"></i>Reconstructed</span><span><i class="band"></i>Calibrated band</span></div></div><button class="button" id="overview">Overview</button></div><svg id="chart" viewBox="0 0 900 335" role="img" aria-label="Time series and reconstruction uncertainty"></svg><div class="chartnote" id="chart-note"></div><div class="panelbody" id="gap-details"></div></section></div>
<div class="footgrid"><section class="panel"><div class="panelhead"><h2>Provenance & configuration</h2></div><div class="panelbody"><dl id="provenance"></dl></div></section><section class="panel"><div class="panelhead"><h2>What this report establishes</h2></div><div class="panelbody"><p style="font-size:13px;margin-top:0">The workflow used separate, earlier training and calibration history. It never used missing input values or reused an estimate as an observation.</p><ul id="warnings"></ul><div class="note">¹ Coverage is a calibration target, not measured accuracy on these unknown values. Temporal dependence, unusual events and distribution shift can invalidate nominal coverage. This report does not establish ground-truth accuracy.</div><h3>Historical analogs for the selected gap</h3><div id="neighbors" class="neighbors">Choose a reconstructed gap to inspect reference windows.</div></div></section></div>
<footer id="footer"></footer><noscript><p>This report needs JavaScript for local charts. The complete results remain available in repaired.csv and report.json; no internet access is needed.</p></noscript></main>
<script id="gaplens-data" type="application/json">__DATA__</script>
<script>
"use strict";
const D=JSON.parse(document.getElementById("gaplens-data").textContent), R=D.report;
const $=id=>document.getElementById(id), text=(id,s)=>$(id).textContent=s;
const fmt=n=>Number(n).toLocaleString(undefined,{maximumFractionDigits:3});
const date=s=>s.replace("T"," ").replace("+00:00"," UTC");
text("stat-repaired",`${R.summary.reconstructed_gaps} / ${R.summary.gaps}`);
text("stat-values",`${R.summary.reconstructed_samples} / ${R.summary.missing_samples}`);
text("stat-observed",fmt(R.summary.unchanged_observations));text("stat-target",`${Math.round(100*R.target_gap_coverage)}%`);
$("print").addEventListener("click",()=>window.print());
const provenance=[['Input',R.input.name],['Reference',R.reference.name],['Method',R.config.method],['Sampling cadence',`${fmt(R.input.cadence_seconds)} seconds`],['History split',`${R.reference.training_rows} training / ${R.reference.calibration_rows} calibration rows`],['Training ends',date(R.reference.training_end)],['Calibration ends',date(R.reference.end)],['Input begins',date(R.input.start)],['Context / analogs',`${R.config.context} samples each side / ${R.config.neighbors} requested neighbors`],['Seed / elapsed compute',`${R.config.seed} / ${fmt(R.runtime_seconds)} seconds`],['Input SHA-256',R.input.sha256],['Reference SHA-256',R.reference.sha256]];
provenance.forEach(([k,v])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=v;if(k.includes('SHA'))dd.className='hash';$('provenance').append(dt,dd)});
R.warnings.forEach(w=>{const li=document.createElement('li');li.textContent=w;$('warnings').append(li)});
text('footer',`GapLens ${R.environment.packages.gaplens} · ${date(R.generated_at)} · ${R.environment.platform} · Local report, no remote resources.`);
let selected=null;
function gapList(){const list=$('gap-list');list.replaceChildren();const filter=$('filter').value;const gaps=R.gaps.filter(g=>filter==='all'||g.status===filter);if(!gaps.length){const p=document.createElement('p');p.className='panelbody muted';p.textContent='No gaps in this view.';list.append(p)}gaps.forEach(g=>{const b=document.createElement('button');b.className='gapbutton'+(selected===g.id?' active':'');b.setAttribute('aria-pressed',selected===g.id?'true':'false');const pill=document.createElement('span');pill.className='pill '+g.status;pill.textContent=g.status;const title=document.createElement('strong');title.textContent=`Gap ${g.id} · ${g.length} samples`;const small=document.createElement('small');small.textContent=date(g.start_time);b.append(pill,title,small);b.onclick=()=>show(g);list.append(b)})}
function elem(name,attrs,parent){const e=document.createElementNS('http://www.w3.org/2000/svg',name);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));parent.append(e);return e}
function chart(points,gap){const svg=$('chart');svg.replaceChildren();const W=900,H=335,L=75,T=22,B=43,RR=25;const finite=points.flatMap(p=>[p.o,p.y,p.lo,p.hi]).filter(v=>v!==null&&Number.isFinite(v));if(!finite.length){elem('text',{x:50,y:80,fill:'#536b7b'},svg).textContent='No finite values in this view';return}let low=Math.min(...finite),high=Math.max(...finite);const pad=Math.max((high-low)*.08,Math.abs(high)*.001,1e-6);low-=pad;high+=pad;const minI=points[0].i,maxI=points[points.length-1].i;const x=i=>L+(i-minI)/Math.max(1,maxI-minI)*(W-L-RR),y=v=>T+(high-v)/(high-low)*(H-T-B);for(let j=0;j<=4;j++){const v=low+(high-low)*j/4,yy=y(v);elem('line',{x1:L,y1:yy,x2:W-RR,y2:yy,stroke:'#e8eef1'},svg);const label=elem('text',{x:L-10,y:yy+4,'text-anchor':'end',fill:'#536b7b','font-size':11},svg);label.textContent=fmt(v)}if(gap){elem('rect',{x:x(gap.start_index),y:T,width:Math.max(1,x(gap.end_index_exclusive-1)-x(gap.start_index)),height:H-T-B,fill:'#f1f7f8'},svg)}let band=[];function bandDraw(){
 if(band.length===1){
  const p=band[0],xx=x(p.i),top=y(p.hi),bottom=y(p.lo);
  elem('line',{x1:xx,y1:top,x2:xx,y2:bottom,stroke:'#72bdc9','stroke-width':3,'data-role':'singleton-interval'},svg);
  [top,bottom].forEach(yy=>elem('line',{x1:xx-6,y1:yy,x2:xx+6,y2:yy,stroke:'#72bdc9','stroke-width':2,'data-role':'singleton-cap'},svg));
 }else if(band.length>1){
  const path=band.map(p=>`${x(p.i)},${y(p.hi)}`).concat([...band].reverse().map(p=>`${x(p.i)},${y(p.lo)}`)).join(' ');
  elem('polygon',{points:path,fill:'#bce5ea','fill-opacity':.65},svg);
 }
 band=[];
}points.forEach(p=>{if(p.lo!==null&&p.hi!==null){band.push(p)}else bandDraw()});bandDraw();function line(key,color,width){let segment=[];function flush(){if(segment.length>1)elem('polyline',{points:segment.join(' '),fill:'none',stroke:color,'stroke-width':width,'stroke-linejoin':'round','stroke-linecap':'round'},svg);else if(segment.length===1){const [cx,cy]=segment[0].split(',');elem('circle',{cx,cy,r:2.5,fill:color},svg)}segment=[]}points.forEach(p=>{const value=key==='repair'?(p.o===null?p.y:null):p.o;if(value!==null)segment.push(`${x(p.i)},${y(value)}`);else flush()});flush()}line('observed','#6d7f89',1.7);line('repair','#087c94',2.7);points.forEach(p=>{if(p.o===null&&p.y!==null){const c=elem('circle',{cx:x(p.i),cy:y(p.y),r:2.7,fill:'#087c94'},svg);elem('title',{},c).textContent=`${date(p.t)} · estimate ${fmt(p.y)} · band [${fmt(p.lo)}, ${fmt(p.hi)}]`}});[points[0],points[Math.floor(points.length/2)],points[points.length-1]].forEach((p,j)=>{const t=elem('text',{x:x(p.i),y:H-14,'text-anchor':j===0?'start':j===2?'end':'middle',fill:'#536b7b','font-size':10},svg);t.textContent=date(p.t).replace(' UTC','')});}
function detail(label,value){const d=document.createElement('div');d.className='detail';const b=document.createElement('b'),s=document.createElement('span');b.textContent=value;s.textContent=label;d.append(b,s);return d}
function show(g){selected=g?g.id:null;gapList();const details=$('gap-details');details.replaceChildren();if(!g){text('chart-title','Full input series');text('chart-subtitle',R.input.name);chart(D.overview,null);text('chart-note',`Overview samples ${D.overview.length} plotted points from ${R.input.rows} rows; inspect a gap for local detail. The downloaded CSV contains every row.`);text('neighbors','Choose a reconstructed gap to inspect reference windows.');return}text('chart-title',`Gap ${g.id} · ${g.length} missing samples`);text('chart-subtitle',`${date(g.start_time)} — ${date(g.end_time)}`);chart(D.views[String(g.id)],g);text('chart-note','Shaded region marks the missing block. Hover over reconstructed points for values and interval limits.');const grid=document.createElement('div');grid.className='detailgrid';grid.append(detail('status',g.status),detail('calibration gaps',g.calibration_count),detail('interval multiplier',g.quantile===null?'—':fmt(g.quantile)));details.append(grid);if(g.reason||g.warning){const p=document.createElement('div');p.className='note';p.textContent=g.reason||g.warning;details.append(p)}if(g.neighbors.length){text('neighbors',g.neighbors.map((n,i)=>`${i+1}. ${date(n.start_time)} → ${date(n.end_time)} (reference row ${n.reference_index})`).join('\n'));$('neighbors').style.whiteSpace='pre-wrap'}else{text('neighbors',g.status==='unresolved'?'No reconstruction was produced.':'This baseline does not use historical analog windows.')}}
$('overview').onclick=()=>show(null);$('filter').onchange=gapList;show(R.gaps[0]||null);
</script></body></html>'''
    replacements = {"TITLE": html.escape(report["input"]["name"], quote=True), "DATA": data}
    return re.sub(r"__(TITLE|DATA)__", lambda match: replacements[match.group(1)], template)
