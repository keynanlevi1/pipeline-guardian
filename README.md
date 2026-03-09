# Pipeline Guardian

AI-assisted pipeline debugging tool with web dashboard, powered by Jenkins MCP Plugin.

![Pipeline Guardian](screenshot.png)

## Features

- **Web Dashboard**: Modern chat interface for pipeline debugging
- **MCP Integration**: Connects to Jenkins MCP Plugin endpoint for native CI/CD data
- **AI-Powered Debugging**: Uses Claude or GPT to analyze failures and suggest fixes
- **Real-time Stats**: Running pipelines, queue, failures, node status
- **Rich CLI**: Terminal interface with the same capabilities

## Quick Start

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required settings:
```bash
JENKINS_URL=https://jenkins.ctera.dev
JENKINS_MCP_PATH=/mcp-server/mcp
JENKINS_USER=your_username
JENKINS_TOKEN=your_api_token

# AI Provider
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENAI_API_KEY=sk-...
```

### 2. Run Web Dashboard

```bash
# Install
pip install -e .

# Start server
pg-server

# Open http://localhost:8888
```

### 3. Run with Docker

```bash
docker-compose up -d
# Open http://localhost:8888
```

## Web Interface

The web dashboard provides:

- **Quick Stats**: Running pipelines, queue size, failures today, online nodes
- **Failed Builds List**: Click any failed job to trigger AI debugging
- **Chat Interface**: Ask natural language questions about your CI/CD
- **AI Debug Panel**: Detailed failure analysis with suggested fixes

### Example Queries

- "Show running pipelines"
- "What's in the queue?"
- "Show failed builds today"
- "Which nodes are offline?"
- "Debug my-pipeline" - triggers AI analysis

## CLI Interface

```bash
# Check status
pg status

# View running pipelines
pg running

# View failures
pg failures
pg failures --date yesterday

# AI debugging
pg debug my-pipeline-job
pg debug my-pipeline-job --build 123

# View logs
pg logs my-pipeline-job --lines 200

# Quick diagnosis
pg quick my-pipeline-job

# List MCP tools
pg tools
```

## How AI Debugging Works

1. **Fetch**: Gets build console output via Jenkins MCP Plugin
2. **Extract**: Identifies error patterns and relevant context
3. **Analyze**: Sends to AI (Claude/GPT) for root cause analysis
4. **Report**: Returns actionable fixes with confidence score

### Debug Output Example

```
╭─────────── Pipeline Failure - my-app #456 ───────────╮
│ npm install failed - dependency resolution conflict  │
╰──────────────────────────────────────────────────────╯

Root Cause:
Peer dependency conflict between react@18.2.0 and react-dom@17.0.2

Suggested Fixes:
  💡 Update react-dom to version 18.2.0
  💡 Run 'npm install --legacy-peer-deps' temporarily  
  💡 Check package-lock.json for conflicts

Related Files: package.json, package-lock.json

Confidence: 85%
```

## Architecture

```
pipeline-guardian/
├── src/pipeline_guardian/
│   ├── __init__.py          # Package exports
│   ├── config.py             # Settings from env vars
│   ├── client.py             # MCP client for Jenkins plugin
│   ├── debugger.py           # AI-powered failure analysis
│   ├── cli.py                # Rich CLI interface
│   ├── server.py             # Web server entry point
│   └── web/
│       ├── app.py            # FastAPI application
│       └── static/
│           └── index.html    # Web dashboard
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Jenkins MCP Plugin

This tool requires the Jenkins MCP Plugin installed on your Jenkins server. The plugin exposes an MCP endpoint (typically at `/mcp-server/mcp`) that provides:

- Running pipeline information
- Build queue status
- Failed build details
- Console log access
- Node/agent status
- Job configuration

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web dashboard |
| `POST /api/query` | Natural language query |
| `POST /api/debug` | AI debugging analysis |
| `GET /api/debug/{job_name}` | Debug specific job |
| `GET /api/jenkins/running` | Running pipelines |
| `GET /api/jenkins/queue` | Build queue |
| `GET /api/jenkins/failed` | Failed builds |
| `GET /api/jenkins/nodes` | Node status |
| `GET /api/mcp/tools` | Available MCP tools |

## Development

```bash
# Clone
git clone https://github.com/keynanlevi1/pipeline-guardian.git
cd pipeline-guardian

# Create venv
python -m venv venv
source venv/bin/activate

# Install with dev deps
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
mypy src/
```

## License

MIT
