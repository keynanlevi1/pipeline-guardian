"""GitHub API client for accessing repository contents."""

import httpx
from dataclasses import dataclass
from typing import Any, Optional
import base64

from .config import Settings


@dataclass
class GitHubResult:
    tool_name: str
    success: bool
    content: Any
    error: Optional[str] = None


class GitHubAPIClient:
    """GitHub API client."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.token = self.settings.github_token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}" if self.token else "",
        }

    async def _request(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def get_file_contents(self, owner: str, repo: str, path: str, ref: str = "main") -> GitHubResult:
        """Get file contents from a repository."""
        try:
            data = await self._request(f"/repos/{owner}/{repo}/contents/{path}?ref={ref}")
            
            if isinstance(data, list):
                # It's a directory
                items = [f"{'📁' if item['type'] == 'dir' else '📄'} {item['name']}" for item in data]
                text = f"📂 Directory: {owner}/{repo}/{path}\n\n" + "\n".join(items)
                return GitHubResult("get_file_contents", True, text)
            else:
                # It's a file
                content = base64.b64decode(data.get("content", "")).decode("utf-8")
                text = f"📄 File: {owner}/{repo}/{path}\n\n```\n{content}\n```"
                return GitHubResult("get_file_contents", True, text)
        except Exception as e:
            return GitHubResult("get_file_contents", False, None, str(e))

    async def search_code(self, query: str, owner: str = None, repo: str = None) -> GitHubResult:
        """Search for code in repositories."""
        try:
            search_query = query
            if owner and repo:
                search_query = f"{query} repo:{owner}/{repo}"
            elif owner:
                search_query = f"{query} user:{owner}"
            
            data = await self._request(f"/search/code?q={search_query}&per_page=10")
            
            items = data.get("items", [])
            text = f"🔍 Code Search Results ({len(items)} found)\n\n"
            for item in items[:10]:
                text += f"• {item['repository']['full_name']}/{item['path']}\n"
            
            return GitHubResult("search_code", True, text)
        except Exception as e:
            return GitHubResult("search_code", False, None, str(e))

    async def get_repo_info(self, owner: str, repo: str) -> GitHubResult:
        """Get repository information."""
        try:
            data = await self._request(f"/repos/{owner}/{repo}")
            
            text = f"📦 Repository: {data['full_name']}\n\n"
            text += f"Description: {data.get('description', 'None')}\n"
            text += f"Default Branch: {data.get('default_branch', 'main')}\n"
            text += f"Language: {data.get('language', 'Unknown')}\n"
            text += f"Stars: {data.get('stargazers_count', 0)}\n"
            text += f"URL: {data.get('html_url')}\n"
            
            return GitHubResult("get_repo_info", True, text)
        except Exception as e:
            return GitHubResult("get_repo_info", False, None, str(e))

    async def list_branches(self, owner: str, repo: str) -> GitHubResult:
        """List repository branches."""
        try:
            data = await self._request(f"/repos/{owner}/{repo}/branches?per_page=30")
            
            text = f"🌿 Branches in {owner}/{repo}\n\n"
            for branch in data:
                text += f"• {branch['name']}\n"
            
            return GitHubResult("list_branches", True, text)
        except Exception as e:
            return GitHubResult("list_branches", False, None, str(e))

    async def call_tool(self, name: str, arguments: dict) -> GitHubResult:
        """Call a GitHub tool by name."""
        if name == "github_get_file":
            return await self.get_file_contents(
                arguments.get("owner", ""),
                arguments.get("repo", ""),
                arguments.get("path", ""),
                arguments.get("ref", "main")
            )
        elif name == "github_search_code":
            return await self.search_code(
                arguments.get("query", ""),
                arguments.get("owner"),
                arguments.get("repo")
            )
        elif name == "github_repo_info":
            return await self.get_repo_info(
                arguments.get("owner", ""),
                arguments.get("repo", "")
            )
        elif name == "github_list_branches":
            return await self.list_branches(
                arguments.get("owner", ""),
                arguments.get("repo", "")
            )
        else:
            return GitHubResult(name, False, None, f"Unknown GitHub tool: {name}")
