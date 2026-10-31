import hashlib
import hmac
import json

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse

from .config import settings
from .db import init_db, recent_reviews
from .reviewer import review_pull_request
from .analyzer import AGENTS

app = FastAPI(title="PR Guardian", version="0.2.0")


@app.on_event("startup")
def startup():
    init_db()


def verify_signature(body: bytes, signature: str | None):
    if not settings.github_webhook_secret:
        raise HTTPException(500, "GITHUB_WEBHOOK_SECRET is not configured")
    if not signature:
        raise HTTPException(401, "Missing GitHub signature")
    digest = hmac.new(
        settings.github_webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    expected = f"sha256={digest}"
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid GitHub signature")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def api_status():
    return {
        "status": "online",
        "dry_run": settings.dry_run,
        "model": settings.ollama_model,
        "reviewers": list(AGENTS.keys()),
    }



@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    body = await request.body()

    verify_signature(
        body,
        request.headers.get("X-Hub-Signature-256")
    )

    event = request.headers.get("X-GitHub-Event")
    payload = json.loads(body or b"{}")

    if event != "pull_request":
        return {"ignored": True}

    action = payload.get("action")

    if action not in {
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review"
    }:
        return {"ignored": True}

    pr = payload.get("pull_request", {})

    if pr.get("draft"):
        return {"ignored": True}

    repo = payload.get("repository", {}).get("full_name")
    number = payload.get("number")

    if not repo or not number:
        raise HTTPException(
            status_code=400,
            detail="Missing repository or PR number"
        )

    # Run AI review in the background
    background_tasks.add_task(
        review_pull_request,
        repo,
        int(number)
    )

    # Respond immediately to GitHub
    return {
        "accepted": True,
        "message": "PR review started",
        "repository": repo,
        "pull_request": number
    }



@app.get("/api/reviews")
def reviews():
    rows = recent_reviews()
    for row in rows:
        row["findings"] = json.loads(row.pop("findings_json"))
    return rows


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#071326">
<title>PR Guardian — Review Dashboard</title>
<style>
:root{
 --bg:#071326;--bg2:#0a1a31;--panel:#0d203b;--panel2:#102746;--line:#1d3a60;
 --text:#e8f2ff;--muted:#8fa9c8;--blue:#38bdf8;--blue2:#2563eb;
 --purple:#a78bfa;--green:#34d399;--yellow:#fbbf24;--red:#fb7185;
 --shadow:0 18px 50px rgba(0,0,0,.24)
}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(ellipse at 15% 0%,#102d50 0,transparent 38%),var(--bg);
 color:var(--text);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}
button,input{font:inherit}
button{cursor:pointer}
.app{min-height:100vh;display:grid;grid-template-columns:248px minmax(0,1fr)}
.sidebar{padding:26px 17px;border-right:1px solid rgba(80,130,190,.17);background:rgba(5,16,32,.72)}
.brand{display:flex;align-items:center;gap:12px;padding:0 8px 28px}
.brand-mark{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;
 background:linear-gradient(145deg,#2563eb,#7c3aed);box-shadow:0 8px 25px #2563eb44;font-size:22px}
.brand strong{display:block;font-size:17px;letter-spacing:.2px}
.brand small{display:block;color:var(--muted);font-size:11px}
.nav{display:grid;gap:7px}
.nav a{color:#b9cbe2;text-decoration:none;padding:11px 13px;border-radius:10px;display:flex;gap:12px;align-items:center}
.nav a.active,.nav a:hover{background:linear-gradient(90deg,#1d4ed8aa,#2563eb33);color:white}
.nav-icon{width:19px;text-align:center;color:var(--blue)}
.side-note{margin:30px 5px 0;padding:14px;border:1px solid var(--line);border-radius:13px;background:#0b1b31}
.side-note b{font-size:12px}.side-note p{font-size:11px;color:var(--muted);margin:7px 0 0}
main{min-width:0;padding:28px clamp(18px,3vw,42px) 50px;max-width:1700px;width:100%;margin:0 auto}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:25px}
.eyebrow{color:var(--blue);font-size:11px;text-transform:uppercase;letter-spacing:1.5px;font-weight:700}
h1{font-size:27px;margin:2px 0 3px;letter-spacing:-.6px}
.subtitle{color:var(--muted);font-size:13px}
.top-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.online{display:flex;align-items:center;gap:8px;color:var(--green);font-size:12px}
.dot{width:8px;height:8px;border-radius:50%;background:currentColor;box-shadow:0 0 12px currentColor}
.mode{border:1px solid #31527a;background:#102846;padding:8px 12px;border-radius:10px;font-size:11px;color:#bfdbfe}
.mode strong{color:var(--yellow);letter-spacing:.6px}
.btn{border:1px solid #315d99;color:#d9edff;background:#123b70;padding:9px 13px;border-radius:9px;font-weight:600}
.btn:hover{background:#1d4f91}
.btn:disabled{opacity:.6;cursor:wait}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin-bottom:20px}
.metric,.panel,.review-card{background:linear-gradient(145deg,rgba(15,38,68,.96),rgba(9,27,49,.96));border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}
.metric{padding:16px 18px;position:relative;overflow:hidden}
.metric:after{content:"";position:absolute;width:90px;height:90px;border-radius:50%;right:-35px;top:-42px;background:#38bdf81a}
.metric-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.8px}
.metric-value{font-size:27px;font-weight:750;margin-top:4px;letter-spacing:-.5px}
.metric-foot{font-size:11px;color:var(--muted)}
.metric.blue .metric-value{color:var(--blue)}.metric.green .metric-value{color:var(--green)}
.metric.yellow .metric-value{color:var(--yellow)}.metric.red .metric-value{color:var(--red)}
.content-grid{display:grid;grid-template-columns:minmax(0,1fr) 285px;gap:17px;align-items:start}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin:5px 0 13px}
.section-head h2{font-size:17px;margin:0}.section-head p{margin:3px 0 0;color:var(--muted);font-size:12px}
.review-list{display:grid;gap:15px}
.review-card{padding:18px 19px}
.review-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}
.pr-title{display:flex;gap:11px;min-width:0}
.pr-icon{width:38px;height:38px;flex:none;border-radius:12px;display:grid;place-items:center;color:var(--purple);background:#6d4bb533;border:1px solid #8b5cf655;font-size:18px}
.pr-name{font-size:15px;font-weight:750;overflow-wrap:anywhere}
.repo{color:var(--blue);font-size:11px;margin-left:6px;font-weight:600}
.pr-subtitle{color:#c0d3e9;margin-top:3px;font-size:12px;overflow-wrap:anywhere}
.pr-meta{display:flex;flex-wrap:wrap;gap:12px;color:var(--muted);font-size:11px;margin-top:9px}
.status{border:1px solid #168b70;color:var(--green);background:#064e3b55;border-radius:20px;padding:5px 10px;font-size:11px;white-space:nowrap;font-weight:700}
.status.dry{border-color:#8b6a21;color:var(--yellow);background:#713f122e}
.verdict{margin-top:16px;border:1px solid #25486f;background:#0b1d34;border-radius:12px;padding:13px 15px;display:flex;gap:12px;align-items:flex-start}
.verdict-icon{width:30px;height:30px;display:grid;place-items:center;border-radius:50%;background:#78350f55;color:var(--yellow);font-size:16px;flex:none}
.verdict b{display:block;font-size:12px}.verdict p{margin:3px 0 0;color:var(--muted);font-size:12px}
.finding-head{display:flex;justify-content:space-between;align-items:center;margin:17px 0 9px}
.finding-head h3{font-size:13px;margin:0}
.finding-count{font-size:11px;color:var(--muted)}
.findings{display:grid;gap:8px}
.finding{border:1px solid #1d3a5b;background:#0a1b31;border-radius:11px;padding:12px 13px}
.finding-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.finding-title{font-size:12px;font-weight:700}
.severity{font-size:9px;letter-spacing:.6px;font-weight:800;border-radius:20px;padding:3px 8px;text-transform:uppercase;white-space:nowrap}
.sev-critical,.sev-high{color:#fda4af;background:#88133755;border:1px solid #9f123955}
.sev-medium{color:#fcd34d;background:#78350f55;border:1px solid #a1620755}
.sev-low{color:#93c5fd;background:#1e40af44;border:1px solid #1d4ed855}
.sev-info{color:#67e8f9;background:#164e6344;border:1px solid #0e749055}
.finding-file{font:11px ui-monospace,SFMono-Regular,Consolas,monospace;color:#7dd3fc;margin:7px 0;overflow-wrap:anywhere}
.finding p{margin:5px 0 0;color:#bfd0e5;font-size:12px}
.detail-label{color:#8fa9c8;font-size:10px;text-transform:uppercase;letter-spacing:.7px;font-weight:700;margin-top:9px}
.finding-foot{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;color:#7894b4;font-size:10px}
.empty{padding:38px 20px;text-align:center;border:1px dashed #315273;border-radius:14px;color:var(--muted)}
.empty strong{display:block;color:var(--text);font-size:15px;margin-bottom:5px}
.side-col{display:grid;gap:14px}
.panel{padding:16px}
.panel h3{font-size:13px;margin:0 0 13px}
.activity{display:grid;gap:12px}
.activity-row{display:flex;align-items:center;gap:10px}
.activity-icon{width:30px;height:30px;border-radius:9px;background:#312e8155;color:#c4b5fd;display:grid;place-items:center}
.activity-text{min-width:0;flex:1}.activity-text b{display:block;font-size:11px}.activity-text small{color:var(--muted);font-size:10px}
.mini-status{font-size:9px;color:var(--green);border:1px solid #168b70;border-radius:20px;padding:3px 6px}
.stat-row{display:flex;justify-content:space-between;gap:8px;padding:8px 0;border-bottom:1px solid #1a3655;font-size:11px}
.stat-row:last-child{border:0}.stat-row span{color:var(--muted)}.stat-row b{font-variant-numeric:tabular-nums}
.reviewer{display:flex;gap:9px;align-items:center;padding:8px 0}
.reviewer-icon{width:29px;height:29px;border:1px solid #24547a;border-radius:50%;display:grid;place-items:center;color:var(--blue)}
.reviewer b{display:block;font-size:11px}.reviewer small{color:var(--muted);font-size:10px}
.check{margin-left:auto;color:var(--green);font-size:10px}
.footer-note{color:#7189a7;font-size:10px;margin-top:18px;line-height:1.5}
.search{width:190px;background:#091a30;border:1px solid #244466;color:var(--text);padding:8px 10px;border-radius:9px;outline:none}
.search:focus{border-color:var(--blue)}
.toast{position:fixed;bottom:20px;right:20px;background:#123b70;border:1px solid #3673ad;color:white;padding:10px 14px;border-radius:10px;display:none}
@media(max-width:1100px){.content-grid{grid-template-columns:minmax(0,1fr)}.side-col{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:760px){.app{grid-template-columns:1fr}.sidebar{padding:12px 16px;border-right:0;border-bottom:1px solid var(--line)}.brand{padding:0 0 10px}.nav{display:flex;overflow:auto}.nav a{white-space:nowrap;padding:8px 10px}.side-note{display:none}main{padding:20px 14px}.topbar{align-items:flex-start;flex-direction:column}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.side-col{grid-template-columns:1fr}.review-top{flex-direction:column}.search{width:100%}}
</style>
</head>
<body>
<div class="app">
 <aside class="sidebar">
  <div class="brand"><div class="brand-mark">🛡</div><div><strong>PR Guardian</strong><small>Local-first AI code reviewer</small></div></div>
  <nav class="nav">
   <a class="active" href="/"><span class="nav-icon">▦</span>Dashboard</a>
   <a href="#reviews"><span class="nav-icon">⑂</span>Pull Requests</a>
   <a href="#reviewers"><span class="nav-icon">⚙</span>AI Reviewers</a>
   <a href="/docs"><span class="nav-icon">⌘</span>API Docs</a>
  </nav>
  <div class="side-note"><b>🔒 Local-first analysis</b><p>Your code diffs are analyzed by your configured Ollama model. Review findings carefully before merging.</p></div>
 </aside>
 <main>
  <header class="topbar">
   <div><div class="eyebrow">Workspace / Overview</div><h1>PR Review Dashboard</h1><div class="subtitle">AI-powered code reviews for safer, higher-quality software.</div></div>
   <div class="top-actions"><div class="online"><span class="dot"></span><span id="system-status">Checking system…</span></div><div class="mode" id="mode-pill">MODE · <strong>LOADING</strong></div><button class="btn" id="refresh" onclick="load()">↻ Refresh</button></div>
  </header>
  <section class="metrics">
   <div class="metric blue"><div class="metric-label">Total reviews</div><div class="metric-value" id="m-total">—</div><div class="metric-foot">Saved review runs</div></div>
   <div class="metric green"><div class="metric-label">No findings</div><div class="metric-value" id="m-clean">—</div><div class="metric-foot">Reviews with no reported issues</div></div>
   <div class="metric yellow"><div class="metric-label">Needs attention</div><div class="metric-value" id="m-attention">—</div><div class="metric-foot">Reviews with reported findings</div></div>
   <div class="metric red"><div class="metric-label">High / critical</div><div class="metric-value" id="m-critical">—</div><div class="metric-foot">High and critical findings</div></div>
  </section>
  <div class="content-grid">
   <section id="reviews">
    <div class="section-head"><div><h2>Recent pull request reviews</h2><p>Detailed findings, evidence, and suggested next steps.</p></div><input class="search" id="search" placeholder="Search repository or PR…" oninput="renderReviews()"></div>
    <div class="review-list" id="review-list"><div class="empty">Loading reviews…</div></div>
   </section>
   <aside class="side-col">
    <section class="panel"><h3>◷ Recent activity</h3><div class="activity" id="activity"><div class="subtitle">Loading…</div></div></section>
    <section class="panel"><h3>▥ Finding breakdown</h3>
     <div class="stat-row"><span>Critical</span><b id="s-critical">0</b></div>
     <div class="stat-row"><span>High</span><b id="s-high">0</b></div>
     <div class="stat-row"><span>Medium</span><b id="s-medium">0</b></div>
     <div class="stat-row"><span>Low</span><b id="s-low">0</b></div>
     <div class="stat-row"><span>Informational</span><b id="s-info">0</b></div>
    </section>
    <section class="panel" id="reviewers"><h3>✣ AI reviewer roles</h3><div id="reviewer-list">
     <div class="reviewer"><div class="reviewer-icon">⌕</div><div><b>Bug Hunter</b><small>Logic errors and edge cases</small></div><span class="check">●</span></div>
     <div class="reviewer"><div class="reviewer-icon">⌑</div><div><b>Security Reviewer</b><small>Security risks and unsafe patterns</small></div><span class="check">●</span></div>
     <div class="reviewer"><div class="reviewer-icon">✓</div><div><b>Quality &amp; Tests</b><small>Maintainability and test gaps</small></div><span class="check">●</span></div>
    </div></section>
   </aside>
  </div>
  <div class="footer-note">PR Guardian uses AI-generated analysis. Findings may be incomplete or incorrect; validate evidence and recommendations yourself. A clean review is not a guarantee that code is bug-free.</div>
 </main>
</div>
<div class="toast" id="toast"></div>
<script>
let allReviews=[];
const $=id=>document.getElementById(id);
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function sev(s){s=String(s||'info').toLowerCase();return ['critical','high','medium','low','info'].includes(s)?s:'info';}
function dateLabel(v){if(!v)return 'Date unavailable';const d=new Date(v);return isNaN(d)?esc(v):d.toLocaleString();}
function findingHtml(f){
 const s=sev(f.severity),loc=f.file?(f.file+(f.line?' · line '+f.line:'')):'Location not provided';
 return `<article class="finding"><div class="finding-top"><div class="finding-title">${esc(f.title||'Untitled finding')}</div><span class="severity sev-${s}">${s}</span></div>
 <div class="finding-file">⌁ ${esc(loc)}</div>
 <div class="detail-label">Why it matters</div><p>${esc(f.explanation||'No explanation supplied.')}</p>
 <div class="detail-label">Suggested action</div><p>${esc(f.recommendation||'No recommendation supplied.')}</p>
 <div class="finding-foot"><span>Reviewer: ${esc(f.source||'AI')}</span><span>Confidence: ${Math.round(Math.max(0,Math.min(1,Number(f.confidence??0)))*100)}%</span></div></article>`;
}
function cardHtml(x){
 const fs=Array.isArray(x.findings)?x.findings:[];
 const high=fs.filter(f=>['critical','high'].includes(sev(f.severity))).length;
 const verdict=high?'High-priority findings detected':fs.length?'Review findings before merging':'No actionable findings reported';
 const status=String(x.status||'completed');
 return `<article class="review-card"><div class="review-top"><div class="pr-title"><div class="pr-icon">⑂</div><div><div class="pr-name">PR #${esc(x.pr_number)} <span class="repo">${esc(x.repo)}</span></div><div class="pr-subtitle">${esc(x.title||'Untitled pull request')}</div><div class="pr-meta"><span>◷ ${dateLabel(x.created_at)}</span><span>▤ ${fs.length} finding(s)</span><span>✣ ${esc(status)}</span></div></div></div><span class="status ${status==='dry_run'?'dry':''}">${status==='dry_run'?'DRY RUN':'SAVED'}</span></div>
 <div class="verdict"><div class="verdict-icon">${high?'!':fs.length?'⚑':'✓'}</div><div><b>${esc(verdict)}</b><p>${esc(x.summary||'No summary was provided by the analyzer.')}</p></div></div>
 <div class="finding-head"><h3>Detailed findings</h3><span class="finding-count">${fs.length} total</span></div>
 <div class="findings">${fs.length?fs.map(findingHtml).join(''):'<div class="empty"><strong>No findings returned</strong>No actionable issues were reported by the configured reviewers. This does not prove the change is bug-free.</div>'}</div></article>`;
}
function renderReviews(){
 const q=$('search').value.trim().toLowerCase();
 const rows=allReviews.filter(x=>(String(x.repo)+' '+String(x.pr_number)+' '+String(x.title)).toLowerCase().includes(q));
 $('review-list').innerHTML=rows.length?rows.map(cardHtml).join(''):'<div class="empty"><strong>No matching reviews</strong>Try another search, or open/update a pull request to trigger a review.</div>';
}
function renderStats(){
 const fs=allReviews.flatMap(x=>Array.isArray(x.findings)?x.findings:[]);
 const counts={critical:0,high:0,medium:0,low:0,info:0};fs.forEach(f=>counts[sev(f.severity)]++);
 const clean=allReviews.filter(x=>!x.findings?.length).length;
 $('m-total').textContent=allReviews.length;$('m-clean').textContent=clean;
 $('m-attention').textContent=allReviews.length-clean;$('m-critical').textContent=counts.critical+counts.high;
 Object.keys(counts).forEach(k=>$('s-'+k).textContent=counts[k]);
 $('activity').innerHTML=allReviews.slice(0,5).map(x=>`<div class="activity-row"><div class="activity-icon">⑂</div><div class="activity-text"><b>${esc(x.repo)} #${esc(x.pr_number)}</b><small>${dateLabel(x.created_at)}</small></div><span class="mini-status">Saved</span></div>`).join('')||'<div class="subtitle">No activity yet.</div>';
}
async function load(){
 const btn=$('refresh');btn.disabled=true;btn.textContent='Refreshing…';
 try{
  const [rr,sr]=await Promise.all([fetch('/api/reviews',{cache:'no-store'}),fetch('/api/status',{cache:'no-store'})]);
  if(!rr.ok)throw new Error('Could not load reviews (HTTP '+rr.status+')');
  allReviews=await rr.json();renderStats();renderReviews();
  if(sr.ok){const s=await sr.json();$('system-status').textContent=s.status==='online'?'System online':'System status unknown';$('mode-pill').innerHTML='MODE · <strong>'+(s.dry_run?'DRY RUN':'LIVE')+'</strong>'; }
  else {$('system-status').textContent='API online';}
 }catch(e){$('review-list').innerHTML='<div class="empty"><strong>Could not load reviews</strong>'+esc(e.message)+'</div>';$('system-status').textContent='API connection issue';}
 finally{btn.disabled=false;btn.textContent='↻ Refresh';}
}
load();
</script>
</body></html>"""
