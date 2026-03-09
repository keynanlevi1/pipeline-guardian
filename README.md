# Pipeline Guardian

AI-assisted pipeline debugging tool that connects to Jenkins MCP Plugin for intelligent failure analysis.

## Features

- **MCP Integration**: Connects to Jenkins MCP Plugin endpoint for native CI/CD data access
- **AI-Powered Debugging**: Uses Claude or GPT to analyze pipeline failures and suggest fixes
- **Rich CLI**: Beautiful terminal interface with real-time status updates
- **Error Extraction**: Automatically identifies and contextualizes errors from build logs
- **Quick Diagnosis**: Get instant insights into why your pipeline failed

## Installation

### Using pip

```bash
pip install pipeline-guardian
```

### From source

```bash
git clone https://github.com/your-org/pipeline-guardian.git
cd pipeline-guardian
pip install -e .
```

### Using Docker

```bash
docker build -t pipeline-guardian .
docker run --env-file .env pipeline-guardian status
```

## Configuration

Create a `.env` file or set environment variables:

```bash
# Copy the example
cp .env.example .env

# Edit with your credentials
vim .env
```

### Required Settings

```bash
# Jenkins MCP Plugin Connection
JENKINS_URL=https://jenkins.ctera.dev
JENKINS_MCP_PATH=/mcp-server/mcp
JENKINS_USER=your_username
JENKINS_TOKEN=your_api_token

# AI Provider (choose one)
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

### Check Jenkins Status

```bash
# Overall status summary
pg status

# Currently running pipelines
pg running

# Build queue
pg queue

# Today's failures
pg failures

# Yesterday's failures
pg failures --date yesterday
```

### Debug Pipeline Failures

```bash
# AI-assisted debugging for the last failed build
pg debug my-pipeline-job

# Debug a specific build
pg debug my-pipeline-job --build 123

# Quick one-line diagnosis
pg quick my-pipeline-job
```

### View Build Logs

```bash
# View last build logs
pg logs my-pipeline-job

# View specific build with more lines
pg logs my-pipeline-job --build 123 --lines 500
```

### Check Nodes

```bash
pg nodes
```

### List Available MCP Tools

```bash
pg tools
```

## Example Output

```
$ pg debug my-failing-pipeline

Analyzing failure for: my-failing-pipeline

╭──────────────────────── Pipeline Failure - my-failing-pipeline #456 ────────────────────────╮
│ npm install failed with exit code 1 - dependency resolution conflict                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────╯

Root Cause:
The build failed because npm encountered a peer dependency conflict between 
react@18.2.0 and react-dom@17.0.2. The package.json requires incompatible versions.

Suggested Fixes:
  1. Update react-dom to version 18.2.0 to match react
  2. Run 'npm install --legacy-peer-deps' as a temporary workaround
  3. Check package-lock.json for conflicting transitive dependencies

Related Files:
  - package.json
  - package-lock.json

Confidence: 85%
```

## How It Works

1. **Connect**: Pipeline Guardian connects to your Jenkins MCP Plugin endpoint
2. **Fetch**: Retrieves build information, console logs, and error context via MCP
3. **Extract**: Automatically identifies error patterns and relevant context
4. **Analyze**: Sends extracted information to AI (Claude/GPT) for analysis
5. **Report**: Presents actionable debugging insights in a clean format

## Jenkins MCP Plugin

This tool requires the Jenkins MCP Plugin to be installed on your Jenkins server. The plugin exposes an MCP endpoint (typically at `/mcp-server/mcp`) that provides:

- Running pipeline information
- Build queue status
- Failed build details
- Console log access
- Node/agent status
- Job configuration

## CLI Commands Reference

| Command | Description |
|---------|-------------|
| `pg status` | Show overall Jenkins status summary |
| `pg running` | List currently running pipelines |
| `pg queue` | Show build queue |
| `pg failures` | List failed builds (default: today) |
| `pg nodes` | Show Jenkins nodes/agents |
| `pg tools` | List available MCP tools |
| `pg debug <job>` | AI-assisted failure analysis |
| `pg quick <job>` | Quick one-line diagnosis |
| `pg logs <job>` | View build console output |

## Development

```bash
# Clone the repo
git clone https://github.com/your-org/pipeline-guardian.git
cd pipeline-guardian

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint code
ruff check src/
mypy src/
```

## License

MIT
