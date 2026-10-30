import hashlib, hmac, json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from .config import settings
from .db import init_db, recent_reviews
from .reviewer import review_pull_request

app = FastAPI(title="PR Guardian", version="0.1.0")

@app.on_event("startup")
def startup():
    init_db()

def verify_signature(body: bytes, signature: str | None):
    if not settings.github_webhook_secret:
        raise HTTPException(500, "GITHUB_WEBHOOK_SECRET is not configured")
    if not signature:
        raise HTTPException(401, "Missing GitHub signature")
    digest = hmac.new(settings.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid GitHub signature")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/webhooks/github")
async def github_webhook(request: Request):
    body = await request.body()
    verify_signature(body, request.headers.get("X-Hub-Signature-256"))
    event = request.headers.get("X-GitHub-Event")
    payload = json.loads(body or b"{}")
    if event != "pull_request":
        return {"ignored": True, "reason": "unsupported event"}
    action = payload.get("action")
    if action not in {"opened", "synchronize", "reopened", "ready_for_review"}:
        return {"ignored": True, "reason": f"unsupported action: {action}"}
    pr = payload.get("pull_request", {})
    if pr.get("draft"):
        return {"ignored": True, "reason": "draft PR"}
    repo = payload.get("repository", {}).get("full_name")
    number = payload.get("number")
    if not repo or not number:
        raise HTTPException(400, "Missing repository or pull request number")
    # For a production deployment, move this work to a durable background queue.
    return await review_pull_request(repo, int(number))

@app.get("/api/reviews")
def reviews():
    rows = recent_reviews()
    for row in rows:
        row["findings"] = json.loads(row.pop("findings_json"))
    return rows

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
    <title>PR Guardian</title><style>
    body{font:15px system-ui;background:#0b1020;color:#e8ecf5;margin:0;padding:32px}
    main{max-width:1000px;margin:auto}h1{margin-bottom:4px}.muted{color:#9aa6bf}
    .card{background:#151d32;border:1px solid #293653;border-radius:12px;padding:18px;margin:14px 0}
    .pill{padding:3px 9px;border-radius:20px;background:#263b5d;font-size:12px}
    pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#c9d5ea}
    button{background:#4263eb;color:white;border:0;padding:9px 14px;border-radius:8px;cursor:pointer}
    </style></head><body><main><h1>🛡️ PR Guardian</h1><div class="muted">Local-first AI pull request reviewer</div>
    <p><button onclick="load()">Refresh reviews</button></p><div id="reviews">Loading…</div></main>
    <script>
    async function load(){const r=await fetch('/api/reviews');const rows=await r.json();const root=document.getElementById('reviews');
    root.innerHTML=rows.length?rows.map(x=>`<section class="card"><b>${esc(x.repo)} #${x.pr_number}</b> <span class="pill">${esc(x.status)}</span>
    <p>${esc(x.title||'')}</p><div class="muted">${esc(x.created_at)} · ${x.findings.length} finding(s)</div>
    <pre>${esc(x.summary||'')}</pre>${x.findings.map(f=>`<p><b>${esc(f.severity.toUpperCase())}: ${esc(f.title)}</b><br>${esc(f.explanation)}</p>`).join('')}</section>`).join(''):'<p class="muted">No reviews yet. Open or update a GitHub pull request to trigger a review.</p>'}
    function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}load();
    </script></body></html>
    """
