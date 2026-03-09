"""FastAPI web application for Pipeline Guardian."""

import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from ..config import Settings
from ..client import JenkinsMCPClient
from ..debugger import PipelineDebugger

app = FastAPI(
    title="Pipeline Guardian",
    description="AI-assisted pipeline debugging using Jenkins MCP Plugin",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
_settings: Optional[Settings] = None
_client: Optional[JenkinsMCPClient] = None
_debugger: Optional[PipelineDebugger] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_client() -> JenkinsMCPClient:
    global _client
    if _client is None:
        _client = JenkinsMCPClient(settings=get_settings())
    return _client


def get_debugger() -> PipelineDebugger:
    global _debugger
    if _debugger is None:
        _debugger = PipelineDebugger(settings=get_settings())
    return _debugger


# Serve static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
async def root():
    """Serve the frontend."""
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Pipeline Guardian API", "docs": "/docs"}


# ==================== JENKINS MCP ENDPOINTS ====================


@app.get("/api/jenkins/running")
async def get_running_pipelines():
    """Get currently running Jenkins pipelines."""
    try:
        client = get_client()
        result = await client.get_running_pipelines()
        if result.success:
            return {"status": "success", "data": result.content}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/queue")
async def get_queue():
    """Get Jenkins build queue."""
    try:
        client = get_client()
        result = await client.get_queue()
        if result.success:
            return {"status": "success", "data": result.content}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/failed")
async def get_failed_builds(
    date: str = Query("today", description="Date: 'today', 'yesterday', or YYYY-MM-DD")
):
    """Get failed builds from a specific date."""
    try:
        client = get_client()
        result = await client.get_failed_builds(date)
        if result.success:
            return {"status": "success", "data": result.content}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/nodes")
async def get_nodes():
    """Get all Jenkins nodes/agents."""
    try:
        client = get_client()
        result = await client.get_nodes()
        if result.success:
            return {"status": "success", "data": result.content}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/jobs")
async def list_jobs():
    """List all Jenkins jobs."""
    try:
        client = get_client()
        result = await client.list_jobs()
        if result.success:
            return {"status": "success", "data": result.content}
        raise HTTPException(status_code=500, detail=result.error)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jenkins/job/{job_name}")
async def get_job_details(job_name: str):
    """Get details of a specific Jenkins job."""
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
    """Get console output for a specific build."""
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
    """List available MCP tools from Jenkins plugin."""
    try:
        client = get_client()
        tools = await client.list_tools()
        return {
            "status": "success",
            "data": [{"name": t.name, "description": t.description} for t in tools],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AI DEBUGGING ENDPOINTS ====================


class DebugRequest(BaseModel):
    job_name: str
    build_number: Optional[int] = None


@app.post("/api/debug")
async def debug_pipeline(request: DebugRequest):
    """AI-assisted debugging for a pipeline failure."""
    try:
        debugger = get_debugger()
        analysis = await debugger.analyze_failure(request.job_name, request.build_number)
        return {
            "status": "success",
            "data": {
                "job_name": analysis.job_name,
                "build_number": analysis.build_number,
                "error_summary": analysis.error_summary,
                "root_cause": analysis.root_cause,
                "suggested_fixes": analysis.suggested_fixes,
                "related_files": analysis.related_files,
                "confidence": analysis.confidence,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/debug/{job_name}")
async def debug_pipeline_get(
    job_name: str, build_number: Optional[int] = Query(None, description="Build number")
):
    """AI-assisted debugging for a pipeline failure (GET)."""
    try:
        debugger = get_debugger()
        analysis = await debugger.analyze_failure(job_name, build_number)
        return {
            "status": "success",
            "data": {
                "job_name": analysis.job_name,
                "build_number": analysis.build_number,
                "error_summary": analysis.error_summary,
                "root_cause": analysis.root_cause,
                "suggested_fixes": analysis.suggested_fixes,
                "related_files": analysis.related_files,
                "confidence": analysis.confidence,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class QueryRequest(BaseModel):
    query: str


@app.post("/api/query")
async def natural_language_query(request: QueryRequest):
    """Process a natural language query about pipelines."""
    query = request.query.lower()
    client = get_client()
    debugger = get_debugger()

    try:
        # Route based on query intent
        if any(kw in query for kw in ["running", "active", "in progress"]):
            result = await client.get_running_pipelines()
            if result.success:
                pipelines = result.content or []
                if not pipelines:
                    return {"response": "No pipelines are currently running."}
                response = f"**{len(pipelines)} Running Pipelines:**\n\n"
                for p in pipelines:
                    response += f"- **{p.get('job_name', 'Unknown')}** #{p.get('build_number', '?')} on {p.get('node', 'unknown')}\n"
                return {"response": response}

        elif any(kw in query for kw in ["queue", "queued", "waiting"]):
            result = await client.get_queue()
            if result.success:
                items = result.content or []
                if not items:
                    return {"response": "The build queue is empty."}
                response = f"**{len(items)} Items in Queue:**\n\n"
                for item in items:
                    response += f"- **{item.get('job_name', 'Unknown')}**: {item.get('reason', 'Waiting')[:60]}\n"
                return {"response": response}

        elif any(kw in query for kw in ["failed", "failure", "broken"]):
            date = "today"
            if "yesterday" in query:
                date = "yesterday"
            result = await client.get_failed_builds(date)
            if result.success:
                failures = result.content or []
                if not failures:
                    return {"response": f"No failed builds {date}."}
                response = f"**{len(failures)} Failed Builds ({date}):**\n\n"
                for f in failures[:10]:
                    response += f"- **{f.get('job_name', 'Unknown')}** #{f.get('build_number', '?')}\n"
                if len(failures) > 10:
                    response += f"\n...and {len(failures) - 10} more"
                return {"response": response}

        elif any(kw in query for kw in ["node", "agent", "offline", "online"]):
            result = await client.get_nodes()
            if result.success:
                nodes = result.content or []
                online = [n for n in nodes if not n.get("offline")]
                offline = [n for n in nodes if n.get("offline")]
                response = f"**Nodes Status:** {len(online)} online, {len(offline)} offline\n\n"
                if offline:
                    response += "**Offline Nodes:**\n"
                    for n in offline:
                        response += f"- {n.get('name', 'Unknown')}: {n.get('offline_reason', 'No reason')}\n"
                return {"response": response}

        elif any(kw in query for kw in ["debug", "analyze", "why", "fix"]):
            # Extract job name from query
            words = query.split()
            job_name = None
            for i, w in enumerate(words):
                if w in ["debug", "analyze"] and i + 1 < len(words):
                    job_name = words[i + 1]
                    break

            if job_name:
                try:
                    analysis = await debugger.analyze_failure(job_name)
                    response = f"## Debug Analysis: {analysis.job_name} #{analysis.build_number}\n\n"
                    response += f"**Error:** {analysis.error_summary}\n\n"
                    response += f"**Root Cause:** {analysis.root_cause}\n\n"
                    response += "**Suggested Fixes:**\n"
                    for fix in analysis.suggested_fixes:
                        response += f"- {fix}\n"
                    response += f"\n**Confidence:** {analysis.confidence:.0%}"
                    return {"response": response}
                except Exception as e:
                    return {"response": f"Failed to analyze: {e}"}
            return {"response": "Please specify a job name to debug. Example: 'debug my-pipeline'"}

        else:
            return {
                "response": """I can help you with:
- **Running pipelines**: "Show running pipelines"
- **Build queue**: "What's in the queue?"
- **Failed builds**: "Show failed builds today"
- **Nodes status**: "Which nodes are offline?"
- **AI debugging**: "Debug my-pipeline"

Try asking one of these questions!"""
            }

    except Exception as e:
        return {"response": f"Error processing query: {e}"}


@app.post("/api/query/clear")
async def clear_conversation():
    """Clear conversation history."""
    return {"status": "success", "message": "Conversation cleared"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Pipeline Guardian"}
