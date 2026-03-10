"""Direct Jenkins API client (fallback when jenkins-mcp fails)."""

import httpx
from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime, timedelta

from .config import Settings


@dataclass
class MCPToolResult:
    tool_name: str
    success: bool
    content: Any
    error: Optional[str] = None


class JenkinsAPIClient:
    """Direct Jenkins API client."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.base_url = self.settings.jenkins_url.rstrip("/")
        self.auth = None
        if self.settings.jenkins_user and self.settings.jenkins_token:
            self.auth = (self.settings.jenkins_user, self.settings.jenkins_token)

    async def _request(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(url, auth=self.auth)
            response.raise_for_status()
            return response.json()

    async def get_running_pipelines(self) -> MCPToolResult:
        try:
            data = await self._request("/api/json?tree=jobs[name,builds[number,building,timestamp,estimatedDuration,url]]")
            running = []
            for job in data.get("jobs", []):
                for build in job.get("builds", [])[:5]:
                    if build.get("building"):
                        started = datetime.fromtimestamp(build["timestamp"] / 1000)
                        elapsed = datetime.now() - started
                        running.append(f"• {job['name']} #{build['number']} - Running for {str(elapsed).split('.')[0]}")
            
            text = f"🚀 RUNNING PIPELINES ({len(running)} active)\n\n"
            text += "\n".join(running) if running else "No builds currently running."
            return MCPToolResult("get_running_pipelines", True, text)
        except Exception as e:
            return MCPToolResult("get_running_pipelines", False, None, str(e))

    async def get_queue(self) -> MCPToolResult:
        try:
            data = await self._request("/queue/api/json")
            items = data.get("items", [])
            text = f"📋 BUILD QUEUE ({len(items)} items)\n\n"
            if not items:
                text += "Queue is empty."
            else:
                for item in items[:20]:
                    task = item.get("task", {})
                    text += f"• {task.get('name', 'Unknown')} - {item.get('why', '')[:50]}\n"
            return MCPToolResult("get_queue", True, text)
        except Exception as e:
            return MCPToolResult("get_queue", False, None, str(e))

    async def get_failed_builds(self, date: str = "today") -> MCPToolResult:
        try:
            if date == "today":
                target_date = datetime.now().date()
            elif date == "yesterday":
                target_date = (datetime.now() - timedelta(days=1)).date()
            else:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()

            data = await self._request("/api/json?tree=jobs[name,builds[number,result,timestamp,url]]")
            failed = []
            for job in data.get("jobs", []):
                for build in job.get("builds", [])[:20]:
                    if build.get("result") in ["FAILURE", "UNSTABLE", "ABORTED"]:
                        build_date = datetime.fromtimestamp(build["timestamp"] / 1000).date()
                        if build_date == target_date:
                            icon = "🔴" if build["result"] == "FAILURE" else "🟡" if build["result"] == "UNSTABLE" else "⚪"
                            failed.append(f"{icon} {job['name']} #{build['number']} - {build['result']}")

            text = f"❌ FAILED BUILDS ({len(failed)} total) - {date}\n\n"
            text += "\n".join(failed[:50]) if failed else "No failures found."
            return MCPToolResult("get_failed_builds", True, text)
        except Exception as e:
            return MCPToolResult("get_failed_builds", False, None, str(e))

    async def get_nodes(self) -> MCPToolResult:
        try:
            data = await self._request("/computer/api/json")
            computers = data.get("computer", [])
            online = len([c for c in computers if not c.get("offline")])
            offline = len([c for c in computers if c.get("offline")])
            
            text = f"🖥️ JENKINS NODES ({online} online, {offline} offline)\n\n"
            for c in computers:
                status = "🟢" if not c.get("offline") else "🔴"
                text += f"{status} {c.get('displayName', 'Unknown')}\n"
            return MCPToolResult("get_nodes", True, text)
        except Exception as e:
            return MCPToolResult("get_nodes", False, None, str(e))

    async def get_build_console(self, job_name: str, build_number: int, tail_lines: int = 500) -> MCPToolResult:
        try:
            url = f"{self.base_url}/job/{job_name}/{build_number}/consoleText"
            async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
                response = await client.get(url, auth=self.auth)
                response.raise_for_status()
                lines = response.text.split("\n")[-tail_lines:]
            text = f"📜 CONSOLE: {job_name} #{build_number}\n\n" + "\n".join(lines)
            return MCPToolResult("get_build_console", True, text)
        except Exception as e:
            return MCPToolResult("get_build_console", False, None, str(e))

    async def get_job_details(self, job_name: str) -> MCPToolResult:
        try:
            data = await self._request(f"/job/{job_name}/api/json")
            text = f"📋 JOB: {job_name}\n\n"
            text += f"Description: {data.get('description', 'None')}\n"
            text += f"URL: {data.get('url', '')}\n"
            text += f"Buildable: {data.get('buildable', False)}\n"
            text += f"In Queue: {data.get('inQueue', False)}\n"
            if data.get('lastBuild'):
                text += f"Last Build: #{data['lastBuild']['number']}\n"
            if data.get('lastSuccessfulBuild'):
                text += f"Last Success: #{data['lastSuccessfulBuild']['number']}\n"
            if data.get('lastFailedBuild'):
                text += f"Last Failure: #{data['lastFailedBuild']['number']}\n"
            return MCPToolResult("get_job_details", True, text)
        except Exception as e:
            return MCPToolResult("get_job_details", False, None, str(e))

    async def get_build_details(self, job_name: str, build_number: int) -> MCPToolResult:
        try:
            data = await self._request(f"/job/{job_name}/{build_number}/api/json")
            text = f"🔧 BUILD: {job_name} #{build_number}\n\n"
            text += f"Result: {data.get('result', 'UNKNOWN')}\n"
            text += f"Duration: {data.get('duration', 0) // 1000}s\n"
            text += f"Building: {data.get('building', False)}\n"
            if data.get('timestamp'):
                build_time = datetime.fromtimestamp(data['timestamp'] / 1000)
                text += f"Started: {build_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            return MCPToolResult("get_build_details", True, text)
        except Exception as e:
            return MCPToolResult("get_build_details", False, None, str(e))

    async def list_jobs(self) -> MCPToolResult:
        try:
            data = await self._request("/api/json?tree=jobs[name,color]")
            jobs = data.get("jobs", [])
            text = f"📋 JENKINS JOBS ({len(jobs)} total)\n\n"
            for job in jobs[:50]:
                color = job.get("color", "unknown")
                icon = "🟢" if color.startswith("blue") else "🔴" if color.startswith("red") else "🟡"
                text += f"{icon} {job['name']}\n"
            return MCPToolResult("list_jobs", True, text)
        except Exception as e:
            return MCPToolResult("list_jobs", False, None, str(e))

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        if name == "get_running_pipelines":
            return await self.get_running_pipelines()
        elif name == "get_queue":
            return await self.get_queue()
        elif name == "get_failed_builds":
            return await self.get_failed_builds(arguments.get("date", "today"))
        elif name == "get_nodes":
            return await self.get_nodes()
        elif name == "get_build_console":
            return await self.get_build_console(
                arguments.get("job_name", ""),
                arguments.get("build_number", 0),
                arguments.get("tail_lines", 500)
            )
        elif name == "get_job_details":
            return await self.get_job_details(arguments.get("job_name", ""))
        elif name == "get_build_details":
            return await self.get_build_details(
                arguments.get("job_name", ""),
                arguments.get("build_number", 0)
            )
        elif name == "list_jobs":
            return await self.list_jobs()
        else:
            return MCPToolResult(name, False, None, f"Unknown tool: {name}")

    async def initialize(self):
        pass

    async def close(self):
        pass
