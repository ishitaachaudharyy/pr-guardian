# PR Guardian !

A local-first, open-source GitHub pull request reviewer powered by an open-weight model through Ollama. It combines three role-based AI reviews (bug, security, and quality/tests), stores review history in SQLite, and can publish a summary comment on a PR.

> **Safety:** AI findings can be wrong. Start in dry-run mode. Never run untrusted PR code on the application host. This MVP posts one summary comment, not inline line comments. It analyzes textual patches only; large/binary/generated files may be skipped.

## Features

- GitHub webhook verification using HMAC SHA-256.
- Fetches pull request metadata and changed-file patches.
- Runs three specialized reviewer prompts against a local Ollama model.
- Parses structured JSON findings and removes simple duplicates.
- Saves review history in SQLite.
- Provides a small web dashboard at `/`.
- Dry-run mode prevents GitHub comments until explicitly disabled.

## Quick start (Docker)

1. Install Docker and Docker Compose.
2. Copy `.env.example` to `.env`.
3. Set `GITHUB_TOKEN` and a strong `GITHUB_WEBHOOK_SECRET`.
4. Start the services:

   ```bash
   docker compose up --build -d
   ```

5. Pull the model inside the Ollama container:

   ```bash
   docker compose exec ollama ollama pull qwen2.5-coder:7b
   ```

6. Open `http://localhost:8000` for the dashboard and `http://localhost:8000/health` for health status.

If your machine cannot comfortably run the 7B model, choose a smaller compatible instruct/code model and set `OLLAMA_MODEL` in `.env`. Check the model's license and hardware requirements before distributing or deploying it.

## Connect a GitHub repository

For a quick test, expose your local server using a trusted HTTPS tunnel (for example, a temporary development tunnel). Do not expose a production service without TLS, access controls, rate limits, and monitoring.

In the repository:
1. Open **Settings → Webhooks → Add webhook**.
2. Set Payload URL to `https://YOUR-HTTPS-HOST/webhooks/github`.
3. Set Content type to `application/json`.
4. Set the secret to the exact `GITHUB_WEBHOOK_SECRET` in `.env`.
5. Select **Let me select individual events** and enable **Pull requests**.
6. Save the webhook.

Create a fine-grained GitHub token for the target repository with:
- **Pull requests: Read-only**
- **Metadata: Read-only**
- **Issues: Read and write** (PR conversation comments use the Issues API)

Set the token as `GITHUB_TOKEN`. Keep it private.

## Dry run, then posting

By default `DRY_RUN=true`. In this mode, PR Guardian analyzes the PR and saves the result to the dashboard/database but does not post to GitHub.

After checking several results, set `DRY_RUN=false` in `.env` and restart:

```bash
docker compose up -d --force-recreate guardian
```

The reviewer posts a single summary comment to the PR conversation. It does not approve, merge, or request changes automatically.

## Run without Docker

Requires Python 3.11+ and a running Ollama instance.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5-coder:7b
cp .env.example .env
uvicorn app.main:app --reload
```

Set `OLLAMA_URL=http://localhost:11434` in `.env`.

## Tests

```bash
pytest -q
```

## API

- `GET /health` — health check
- `GET /api/reviews` — recent review history
- `POST /webhooks/github` — GitHub webhook endpoint

## Architecture

`GitHub webhook → FastAPI → GitHub PR API → diff builder → three role-specific Ollama reviews → findings aggregation → SQLite + optional GitHub PR comment`

## Important MVP limitations / next steps

- **No inline comments yet:** GitHub inline review comments require mapping model-reported line numbers to valid diff positions. Add this after validating the MVP's findings.
- **No durable job queue:** webhook processing is synchronous. Add Celery/RQ and Redis before handling larger repos or public traffic.
- **Patch-only context:** the MVP does not yet fetch surrounding source files or repository-wide conventions. Add bounded context retrieval for better accuracy.
- **Basic deduplication:** production systems should cluster semantically similar findings and require evidence.
- **Prompt-injection defense:** treat all repository content as untrusted data; never follow instructions embedded in source files. Do not give the model tools that can execute arbitrary commands.
- **Resource limits:** cap file count and patch size; use request timeouts and per-repository rate limits.
- **Privacy:** PR diffs are sent to the configured local model runtime. If you switch to a remote inference provider, review its data policy.

## License

MIT. Add a `LICENSE` file with the standard MIT text before publishing.
