"""MCP Client for Jenkins MCP Plugin."""

import httpx
from httpx_sse import aconnect_sse
from typing import Any, Optional
import json
import asyncio
from dataclasses import dataclass, field

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


@dataclass
class JenkinsMCPClient:
    """Client for Jenkins MCP Plugin endpoint."""

    settings: Settings
    _tools: list[MCPTool] = field(default_factory=list)
    _initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the MCP connection and discover available tools."""
        if self._initialized:
            return

        tools_response = await self._call_mcp("tools/list", {})
        if tools_response and "tools" in tools_response:
            self._tools = [
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                )
                for t in tools_response["tools"]
            ]
        self._initialized = True

    async def _call_mcp(
        self, method: str, params: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Make an MCP request to the Jenkins plugin."""
        auth = None
        if self.settings.jenkins_user and self.settings.jenkins_token:
            auth = (self.settings.jenkins_user, self.settings.jenkins_token)

        request_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        async with httpx.AsyncClient(timeout=60.0, auth=auth) as client:
            response = await client.post(
                self.settings.jenkins_mcp_url,
                json=request_body,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                raise Exception(f"MCP Error: {result['error']}")

            return result.get("result")

    async def list_tools(self) -> list[MCPTool]:
        """List available MCP tools from Jenkins."""
        await self.initialize()
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Call an MCP tool on Jenkins."""
        await self.initialize()

        try:
            result = await self._call_mcp(
                "tools/call",
                {"name": name, "arguments": arguments},
            )

            if result and "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    first_content = content[0]
                    if first_content.get("type") == "text":
                        try:
                            parsed = json.loads(first_content["text"])
                            return MCPToolResult(
                                tool_name=name,
                                success=True,
                                content=parsed,
                            )
                        except json.JSONDecodeError:
                            return MCPToolResult(
                                tool_name=name,
                                success=True,
                                content=first_content["text"],
                            )
                return MCPToolResult(tool_name=name, success=True, content=content)

            return MCPToolResult(
                tool_name=name,
                success=False,
                content=None,
                error="No content in response",
            )

        except Exception as e:
            return MCPToolResult(
                tool_name=name,
                success=False,
                content=None,
                error=str(e),
            )

    # Convenience methods for common Jenkins operations
    async def get_running_pipelines(self) -> MCPToolResult:
        """Get currently running Jenkins pipelines."""
        return await self.call_tool("get_running_pipelines", {})

    async def get_queue(self) -> MCPToolResult:
        """Get Jenkins build queue."""
        return await self.call_tool("get_queue", {})

    async def get_failed_builds(self, date: str = "today") -> MCPToolResult:
        """Get failed builds from a specific date."""
        return await self.call_tool("get_failed_builds", {"date": date})

    async def get_build_details(
        self, job_name: str, build_number: int
    ) -> MCPToolResult:
        """Get details of a specific build."""
        return await self.call_tool(
            "get_build_details",
            {"job_name": job_name, "build_number": build_number},
        )

    async def get_build_console(
        self, job_name: str, build_number: int, tail_lines: int = 500
    ) -> MCPToolResult:
        """Get console output for a specific build."""
        return await self.call_tool(
            "get_build_console",
            {
                "job_name": job_name,
                "build_number": build_number,
                "tail_lines": tail_lines,
            },
        )

    async def get_job_details(self, job_name: str) -> MCPToolResult:
        """Get details of a specific Jenkins job."""
        return await self.call_tool("get_job_details", {"job_name": job_name})

    async def get_nodes(self) -> MCPToolResult:
        """Get all Jenkins nodes/agents."""
        return await self.call_tool("get_nodes", {})

    async def list_jobs(self) -> MCPToolResult:
        """List all Jenkins jobs."""
        return await self.call_tool("list_jobs", {})
