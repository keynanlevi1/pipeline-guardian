"""LLM Agent that uses Jenkins and GitHub tools."""

import asyncio
import json
import os
from typing import Any, Optional

from .config import Settings
from .github_api import GitHubAPIClient

# Use direct API in Docker (MCP subprocess has compatibility issues)
if os.environ.get("JENKINS_MCP_COMMAND") == "jenkins-mcp":
    from .jenkins_api import JenkinsAPIClient as JenkinsClient
else:
    from .client import JenkinsMCPClient as JenkinsClient


class PipelineAgent:
    """Agent that uses LLM to decide which Jenkins/GitHub tools to call."""

    SYSTEM_PROMPT = """You are a CI/CD assistant with access to Jenkins and GitHub.

JENKINS TOOLS:
- get_running_pipelines: Get running pipelines (no params)
- get_queue: Get build queue (no params)  
- get_failed_builds: Get failed builds (params: {"date": "today"|"yesterday"|"YYYY-MM-DD"})
- get_nodes: Get Jenkins nodes (no params)
- list_jobs: List all jobs (no params)
- get_job_details: Get job info (params: {"job_name": "string"})
- get_build_details: Get build info (params: {"job_name": "string", "build_number": integer})
- get_build_console: Get build logs (params: {"job_name": "string", "build_number": integer, "tail_lines": integer})

GITHUB TOOLS:
- github_get_file: Get file contents (params: {"owner": "string", "repo": "string", "path": "string", "ref": "branch"})
- github_search_code: Search code (params: {"query": "string", "owner": "string", "repo": "string"})
- github_repo_info: Get repo info (params: {"owner": "string", "repo": "string"})
- github_list_branches: List branches (params: {"owner": "string", "repo": "string"})

IMPORTANT: Respond with ONLY a JSON object. No text before or after.

To call tools:
{"tools": [{"name": "tool_name", "arguments": {...}}]}

If no tools needed:
{"tools": [], "response": "Your response here"}

Remember context from previous messages. If the user refers to "that build" or "it", use info from conversation history.
For Jenkinsfile requests, use github_get_file with path "Jenkinsfile" (or the job's configured script path)."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.mcp_client = JenkinsClient(settings=self.settings)
        self.github_client = GitHubAPIClient(settings=self.settings)
        self._ai_client: Any = None
        self.conversation_history: list[dict] = []
        self.max_history: int = 20

    def _get_ai_client(self) -> Any:
        """Get the AI client (sync)."""
        if self._ai_client is not None:
            return self._ai_client

        if self.settings.ai_provider == "anthropic":
            if not self.settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            import anthropic
            self._ai_client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key
            )
        elif self.settings.ai_provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set")
            import openai
            self._ai_client = openai.OpenAI(api_key=self.settings.openai_api_key)
        elif self.settings.ai_provider == "azure":
            if not self.settings.azure_openai_key:
                raise ValueError("AZURE_OPENAI_KEY not set")
            if not self.settings.azure_openai_base:
                raise ValueError("AZURE_OPENAI_BASE not set")
            from openai import AzureOpenAI
            self._ai_client = AzureOpenAI(
                api_key=self.settings.azure_openai_key,
                azure_endpoint=self.settings.azure_openai_base,
                api_version=self.settings.azure_openai_version,
            )
        elif self.settings.ai_provider == "azure_foundry":
            if not self.settings.azure_foundry_key:
                raise ValueError("AZURE_FOUNDRY_KEY not set")
            from azure.ai.inference import ChatCompletionsClient
            from azure.core.credentials import AzureKeyCredential
            self._ai_client = ChatCompletionsClient(
                endpoint=self.settings.azure_foundry_endpoint,
                credential=AzureKeyCredential(self.settings.azure_foundry_key),
            )
        else:
            raise ValueError(f"Unknown AI provider: {self.settings.ai_provider}")

        return self._ai_client

    def _call_llm_sync(self, messages: list, include_history: bool = True) -> str:
        """Call LLM synchronously."""
        client = self._get_ai_client()
        
        # Combine history with new messages if requested
        if include_history and self.conversation_history:
            all_messages = self.conversation_history[-self.max_history:] + messages
        else:
            all_messages = messages

        if self.settings.ai_provider == "anthropic":
            response = client.messages.create(
                model=self.settings.ai_model,
                max_tokens=1000,
                system=self.SYSTEM_PROMPT,
                messages=all_messages,
            )
            return response.content[0].text
        elif self.settings.ai_provider == "azure_foundry":
            from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
            foundry_messages = [SystemMessage(content=self.SYSTEM_PROMPT)]
            for msg in all_messages:
                if msg["role"] == "user":
                    foundry_messages.append(UserMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    foundry_messages.append(AssistantMessage(content=msg["content"]))
            response = client.complete(
                messages=foundry_messages,
                model=self.settings.azure_foundry_model,
            )
            return response.choices[0].message.content or ""
        else:
            # OpenAI or Azure
            full_messages = [{"role": "system", "content": self.SYSTEM_PROMPT}] + all_messages
            model = self.settings.azure_openai_deployment if self.settings.ai_provider == "azure" else self.settings.ai_model
            response = client.chat.completions.create(
                model=model,
                max_tokens=1000,
                messages=full_messages,
            )
            return response.choices[0].message.content or ""

    async def _call_llm(self, user_query: str) -> dict[str, Any]:
        """Call LLM to determine which tools to use."""
        loop = asyncio.get_event_loop()
        
        def call_sync():
            return self._call_llm_sync([{"role": "user", "content": user_query}])
        
        try:
            text = await asyncio.wait_for(
                loop.run_in_executor(None, call_sync),
                timeout=120.0
            )
        except asyncio.TimeoutError:
            raise TimeoutError("Request timed out after 2 minutes. The query may be too complex or the AI service is slow. Please try a simpler question.")

        # Try to parse the entire response as JSON first
        text = text.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and ("tools" in parsed or "response" in parsed):
                return parsed
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        import re
        code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_block:
            try:
                parsed = json.loads(code_block.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Fallback: treat entire text as plain response
        return {"tools": [], "response": text}

    async def _format_results(self, query: str, tool_results: list[dict]) -> str:
        """Use LLM to format tool results into a nice response."""
        results_text = json.dumps(tool_results, indent=2, default=str)
        
        prompt = f"""Format this Jenkins data as a helpful response. Use markdown. Be concise.

User question: {query}

Data:
{results_text}

IMPORTANT: Respond with plain text/markdown ONLY. Do NOT wrap your response in JSON."""

        loop = asyncio.get_event_loop()
        
        def call_sync():
            # Don't include history for formatting, use fresh context
            return self._call_llm_sync([{"role": "user", "content": prompt}], include_history=False)
        
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, call_sync),
                timeout=120.0
            )
        except asyncio.TimeoutError:
            raise TimeoutError("Request timed out after 2 minutes while formatting results. Please try again.")
        
        # Strip any JSON wrapper if the LLM still outputs it
        if response.strip().startswith('{"'):
            try:
                parsed = json.loads(response)
                if "response" in parsed:
                    return parsed["response"]
            except:
                pass
        
        return response

    async def process_query(self, query: str) -> str:
        """Process a user query using LLM and MCP tools."""
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": query})
        
        # Step 1: Ask LLM which tools to call
        llm_response = await self._call_llm(query)

        # If LLM gave a direct response without tools
        if not llm_response.get("tools") and llm_response.get("response"):
            response = llm_response["response"]
            # Failsafe: if response is still JSON, extract the text
            if isinstance(response, str) and response.strip().startswith('{"'):
                try:
                    inner = json.loads(response)
                    if isinstance(inner, dict) and "response" in inner:
                        response = inner["response"]
                except:
                    pass
            self.conversation_history.append({"role": "assistant", "content": response})
            return response

        tools_to_call = llm_response.get("tools", [])
        
        if not tools_to_call:
            response = "I'm not sure how to help with that. Try asking about running pipelines, failed builds, queue status, or nodes."
            self.conversation_history.append({"role": "assistant", "content": response})
            return response

        # Step 2: Execute the tools (Jenkins or GitHub)
        tool_results = []
        for tool in tools_to_call:
            tool_name = tool.get("name", "")
            arguments = tool.get("arguments", {})
            
            # Route to appropriate client
            if tool_name.startswith("github_"):
                result = await self.github_client.call_tool(tool_name, arguments)
            else:
                result = await self.mcp_client.call_tool(tool_name, arguments)
            
            tool_results.append({
                "tool": tool_name,
                "success": result.success,
                "data": result.content if result.success else None,
                "error": result.error,
            })

        # Step 3: Format results with LLM
        formatted_response = await self._format_results(query, tool_results)
        
        # Add assistant response to history
        self.conversation_history.append({"role": "assistant", "content": formatted_response})
        
        return formatted_response

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []

    async def close(self):
        """Clean up resources."""
        await self.mcp_client.close()
