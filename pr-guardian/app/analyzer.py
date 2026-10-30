import json, re
import httpx
from .config import settings
from .schemas import Finding, AgentResult

AGENTS = {
    "Bug Hunter": "Find likely correctness bugs, edge cases, unsafe assumptions, and logic errors.",
    "Security Reviewer": "Find security vulnerabilities such as injection, path traversal, secret exposure, unsafe deserialization, and auth flaws. Do not claim a vulnerability without evidence.",
    "Quality & Tests Reviewer": "Find maintainability/performance problems and important missing tests. Avoid style-only nitpicks.",
}

SYSTEM = """You are a careful senior software engineer reviewing a GitHub pull request.
Only report actionable issues introduced by or directly affected by this diff.
Do not invent facts. If uncertain, omit the issue. Do not report style preferences as bugs.
Return ONLY valid JSON with this shape:
{"summary":"short review summary","findings":[
 {"title":"short title","severity":"critical|high|medium|low|info","file":"path or null",
  "line":12,"explanation":"specific evidence and impact","recommendation":"concrete fix",
  "confidence":0.0}
]}
Line must be an integer if known, otherwise null. Confidence must be between 0 and 1.
"""

def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model did not return a JSON object")
    return json.loads(text[start:end+1])

async def run_agent(name, instruction, diff):
    prompt = f"Review role: {instruction}\n\nPull request diff:\n{diff}"
    async with httpx.AsyncClient(timeout=240) as client:
        response = await client.post(
            f"{settings.ollama_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "stream": False,
                "format": "json",
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": prompt}],
                "options": {"temperature": 0.1}
            }
        )
        response.raise_for_status()
        raw = response.json()["message"]["content"]
    data = parse_json(raw)
    findings = []
    for item in data.get("findings", []):
        try:
            findings.append(Finding(**item, source=name))
        except Exception:
            continue
    return AgentResult(agent=name, findings=findings, summary=data.get("summary", ""))

async def analyze(diff):
    results = []
    for name, instruction in AGENTS.items():
        results.append(await run_agent(name, instruction, diff))
    # Basic duplicate suppression by normalized title + file.
    seen, merged = set(), []
    for result in results:
        for f in result.findings:
            key = (f.title.lower().strip(), (f.file or "").lower())
            if key not in seen:
                seen.add(key)
                merged.append(f)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    merged.sort(key=lambda f: (order[f.severity], -f.confidence))
    return merged, " ".join(r.summary for r in results if r.summary)
