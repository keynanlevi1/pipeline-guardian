"""Client for official Jenkins MCP Server via stdio."""

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import Settings


@dataclass
class MCPToolResult:
    """Result from an MCP tool call."""

    tool_name: str
    success: bool
    content: Any
    error: Optional[str] = None


@dataclass
class MCPTool:
    """Definition of an MCP tool."""

    name: str
    description: str
    input_schema: dict[str, Any]


class JenkinsMCPClient:
    """Client for official Jenkins MCP Server via stdio subprocess."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._process: Optional[asyncio.subprocess.Process] = None
        self._tools: list[MCPTool] = []
        self._initialized = False
        self._request_id = 0
        self._lock = asyncio.Lock()

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        """Ensure the MCP server process is running."""
        if self._process is None or self._process.returncode is not None:
            env = os.environ.copy()
            env["JENKINS_URL"] = self.settings.jenkins_url
            if self.settings.jenkins_user:
                env["JENKINS_USER"] = self.settings.jenkins_user
            if self.settings.jenkins_token:
                env["JENKINS_API_TOKEN"] = self.settings.jenkins_token

            mcp_command = self.settings.jenkins_mcp_command
            
            self._process = await asyncio.create_subprocess_exec(
                mcp_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        return self._process

    async def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request to the MCP server."""
        async with self._lock:
            process = await self._ensure_process()
            
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params,
            }
            
            request_line = json.dumps(request) + "\n"
            
            if process.stdin is None or process.stdout is None:
                raise Exception("MCP process stdin/stdout not available")
            
            process.stdin.write(request_line.encode())
            await process.stdin.drain()
            
            response_line = await asyncio.wait_for(
                process.stdout.readline(),
                timeout=60.0
            )
            
            if not response_line:
                raise Exception("No response from MCP server")
            
            response = json.loads(response_line.decode())
            
            if "error" in response:
                raise Exception(f"MCP Error: {response['error']}")
            
            return response.get("result", {})

    async def initialize(self) -> None:
        """Initialize connection and discover tools."""
        if self._initialized:
            return

        try:
            result = await self._send_request("tools/list", {})
            if "tools" in result:
                self._tools = [
                    MCPTool(
                        name=t["name"],
                        description=t.get("description", ""),
                        input_schema=t.get("inputSchema", {}),
                    )
                    for t in result["tools"]
                ]
            self._initialized = True
        except Exception as e:
            self._initialized = True
            self._tools = [
                MCPTool("get_running_pipelines", "Get running pipelines", {}),
                MCPTool("get_queue", "Get build queue", {}),
                MCPTool("get_failed_builds", "Get failed builds", {}),
                MCPTool("get_nodes", "Get nodes", {}),
                MCPTool("list_jobs", "List jobs", {}),
                MCPTool("get_job_details", "Get job details", {}),
                MCPTool("get_build_details", "Get build details", {}),
                MCPTool("get_build_console", "Get build console", {}),
            ]

    async def list_tools(self) -> list[MCPTool]:
        """List available MCP tools."""
        await self.initialize()
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Call an MCP tool."""
        try:
            result = await self._send_request(
                "tools/call",
                {"name": name, "arguments": arguments},
            )

            if "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    first = content[0]
                    if first.get("type") == "text":
                        try:
                            parsed = json.loads(first["text"])
                            return MCPToolResult(name, True, parsed)
                        except json.JSONDecodeError:
                            return MCPToolResult(name, True, first["text"])
                return MCPToolResult(name, True, content)

            return MCPToolResult(name, True, result)

        except Exception as e:
            return MCPToolResult(name, False, None, str(e))

    async def close(self) -> None:
        """Close the MCP server process."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            await self._process.wait()

    # Convenience methods
    async def get_running_pipelines(self) -> MCPToolResult:
        return await self.call_tool("get_running_pipelines", {})

    async def get_queue(self) -> MCPToolResult:
        return await self.call_tool("get_queue", {})

    async def get_failed_builds(self, date: str = "today") -> MCPToolResult:
        return await self.call_tool("get_failed_builds", {"date": date})

    async def get_build_details(self, job_name: str, build_number: int) -> MCPToolResult:
        return await self.call_tool(
            "get_build_details",
            {"job_name": job_name, "build_number": build_number},
        )

    async def get_build_console(
        self, job_name: str, build_number: int, tail_lines: int = 500
    ) -> MCPToolResult:
        return await self.call_tool(
            "get_build_console",
            {"job_name": job_name, "build_number": build_number, "tail_lines": tail_lines},
        )

    async def get_job_details(self, job_name: str) -> MCPToolResult:
        return await self.call_tool("get_job_details", {"job_name": job_name})

    async def get_nodes(self) -> MCPToolResult:
        return await self.call_tool("get_nodes", {})

    async def list_jobs(self) -> MCPToolResult:
        return await self.call_tool("list_jobs", {})
