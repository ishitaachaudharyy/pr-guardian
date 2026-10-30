import httpx
from .config import settings

class GitHubClient:
    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {settings.github_token}",
        }

    async def get_pull(self, repo, number):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{settings.github_api_url}/repos/{repo}/pulls/{number}", headers=self.headers)
            r.raise_for_status()
            return r.json()

    async def get_files(self, repo, number):
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(f"{settings.github_api_url}/repos/{repo}/pulls/{number}/files",
                                 headers=self.headers, params={"per_page": 100})
            r.raise_for_status()
            return r.json()

    async def post_comment(self, repo, number, body):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{settings.github_api_url}/repos/{repo}/issues/{number}/comments",
                headers=self.headers, json={"body": body}
            )
            r.raise_for_status()
            return r.json()
