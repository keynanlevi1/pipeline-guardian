"""FastAPI web application for Pipeline Guardian."""

import os
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Any

from ..config import Settings
from ..agent import PipelineAgent

# Use direct API in Docker (MCP subprocess has compatibility issues)
if os.environ.get("JENKINS_MCP_COMMAND") == "jenkins-mcp":
    from ..jenkins_api import JenkinsAPIClient as JenkinsClient
else:
    from ..client import JenkinsMCPClient as JenkinsClient

app = FastAPI(
    title="Pipeline Guardian",
    description="Pipeline debugging using Jenkins MCP Server",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_settings: Optional[Settings] = None
_client: Optional[Any] = None
_agent: Optional[PipelineAgent] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_client():
    global _client
    if _client is None:
        _client = JenkinsClient(settings=get_settings())
    return _client


def get_agent() -> PipelineAgent:
    global _agent
    if _agent is None:
        _agent = PipelineAgent(settings=get_settings())
    return _agent


def parse_count_from_text(text: str, pattern: str) -> int:
    """Extract a count from MCP text response."""
    match = re.search(pattern, text)
    if match:
        return int(match.group(1))
    return 0


# Serve static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
async def root():
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Pipeline Guardian API", "docs": "/docs"}


# ==================== JENKINS MCP ENDPOINTS ====================


@app.get("/api/jenkins/running")
async def get_running_pipelines():
    try:
        client = get_client()
        result = await client.get_running_pipelines()
        if result.success:
            content = result.content
            if isinstance(content, str):
                count = parse_count_from_text(content, r'\((\d+)\s+active\)')
                return {"status": "success", "data": [], "count": count, "text": content}
            return {"status": "success", "data": content if isinstance(content, list) else []}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/queue")
async def get_queue():
    try:
        client = get_client()
        result = await client.get_queue()
        if result.success:
            content = result.content
            if isinstance(content, str):
                count = parse_count_from_text(content, r'\((\d+)\s+items?\)')
                if count == 0:
                    count = parse_count_from_text(content, r'(\d+)\s+items?\s+in\s+queue')
                return {"status": "success", "data": [], "count": count, "text": content}
            return {"status": "success", "data": content if isinstance(content, list) else []}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/failed")
async def get_failed_builds(
    date: str = Query("today", description="Date: 'today', 'yesterday', or YYYY-MM-DD")
):
    try:
        client = get_client()
        result = await client.get_failed_builds(date)
        if result.success:
            content = result.content
            if isinstance(content, str):
                count = parse_count_from_text(content, r'\((\d+)\s+total\)')
                if count == 0:
                    count = parse_count_from_text(content, r'\((\d+)\s+failures?\)')
                return {"status": "success", "data": [], "count": count, "text": content}
            return {"status": "success", "data": content if isinstance(content, list) else []}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/nodes")
async def get_nodes():
    try:
        client = get_client()
        result = await client.get_nodes()
        if result.success:
            content = result.content
            if isinstance(content, str):
                online = parse_count_from_text(content, r'(\d+)\s+online')
                return {"status": "success", "data": [], "count": online, "text": content}
            return {"status": "success", "data": content if isinstance(content, list) else []}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/jobs")
async def list_jobs():
    try:
        client = get_client()
        result = await client.list_jobs()
        if result.success:
            return {"status": "success", "data": result.content, "text": result.content if isinstance(result.content, str) else None}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/job/{job_name}")
async def get_job_details(job_name: str):
    try:
        client = get_client()
        result = await client.get_job_details(job_name)
        if result.success:
            return {"status": "success", "data": result.content}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/build/{job_name}/{build_number}/console")
async def get_build_console(
    job_name: str,
    build_number: int,
    tail_lines: int = Query(500, description="Number of lines to return"),
):
    try:
        client = get_client()
        result = await client.get_build_console(job_name, build_number, tail_lines)
        if result.success:
            return {"status": "success", "data": result.content}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mcp/tools")
async def list_mcp_tools():
    try:
        client = get_client()
        tools = await client.list_tools()
        return {
            "status": "success",
            "data": [{"name": t.name, "description": t.description} for t in tools],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== QUERY ENDPOINT (LLM + MCP) ====================


class QueryRequest(BaseModel):
    query: str


@app.post("/api/query")
async def process_query(request: QueryRequest):
    """Process a natural language query using LLM to call MCP tools."""
    try:
        agent = get_agent()
        response = await agent.process_query(request.query)
        return {"response": response}
    except ValueError as e:
        return {"response": f"⚠️ AI not configured: {e}"}
    except TimeoutError as e:
        return {"response": f"⏱️ {str(e)}"}
    except Exception as e:
        return {"response": f"❌ Error: {str(e)}"}


@app.post("/api/query/clear")
async def clear_conversation():
    agent = get_agent()
    agent.clear_history()
    return {"status": "success", "message": "Conversation cleared"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Pipeline Guardian"}
