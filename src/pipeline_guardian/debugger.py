"""AI-assisted pipeline debugging using LLMs."""

import re
from dataclasses import dataclass
from typing import Any, Optional

from .client import JenkinsMCPClient, MCPToolResult
from .config import Settings


@dataclass
class ErrorContext:
    """Context extracted from build logs around an error."""

    line_number: int
    error_line: str
    context_before: list[str]
    context_after: list[str]
    error_type: str


@dataclass
class DebugAnalysis:
    """AI analysis of a pipeline failure."""

    job_name: str
    build_number: int
    error_summary: str
    root_cause: str
    suggested_fixes: list[str]
    related_files: list[str]
    confidence: float
    raw_analysis: str


class PipelineDebugger:
    """AI-powered pipeline debugger using Jenkins MCP Plugin."""

    ERROR_PATTERNS = [
        (r"error:", "generic_error"),
        (r"Error:", "generic_error"),
        (r"ERROR:", "generic_error"),
        (r"FAILURE:", "build_failure"),
        (r"failed:", "generic_failure"),
        (r"Failed:", "generic_failure"),
        (r"exception:", "exception"),
        (r"Exception:", "exception"),
        (r"fatal:", "fatal_error"),
        (r"Fatal:", "fatal_error"),
        (r"FATAL:", "fatal_error"),
        (r"AssertionError", "assertion_error"),
        (r"RuntimeError", "runtime_error"),
        (r"TypeError", "type_error"),
        (r"ValueError", "value_error"),
        (r"ImportError", "import_error"),
        (r"ModuleNotFoundError", "module_not_found"),
        (r"FileNotFoundError", "file_not_found"),
        (r"PermissionError", "permission_error"),
        (r"ConnectionError", "connection_error"),
        (r"TimeoutError", "timeout_error"),
        (r"java\.lang\.\w+Exception", "java_exception"),
        (r"groovy\.lang\.\w+Exception", "groovy_exception"),
        (r"hudson\.AbortException", "jenkins_abort"),
        (r"script returned exit code", "exit_code_error"),
        (r"No such file or directory", "file_not_found"),
        (r"Permission denied", "permission_error"),
        (r"Connection refused", "connection_error"),
        (r"OutOfMemoryError", "memory_error"),
        (r"npm ERR!", "npm_error"),
        (r"pip.*error", "pip_error"),
        (r"docker.*error", "docker_error"),
        (r"git.*error", "git_error"),
        (r"\[ERROR\]", "maven_error"),
        (r"BUILD FAILURE", "maven_failure"),
        (r"Compilation failure", "compilation_error"),
        (r"Test.*failed", "test_failure"),
    ]

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.mcp_client = JenkinsMCPClient(settings=self.settings)
        self._ai_client: Any = None

    async def _get_ai_client(self) -> Any:
        """Get or create the AI client."""
        if self._ai_client is not None:
            return self._ai_client

        if self.settings.ai_provider == "anthropic":
            if not self.settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            import anthropic

            self._ai_client = anthropic.AsyncAnthropic(
                api_key=self.settings.anthropic_api_key
            )
        elif self.settings.ai_provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set")
            import openai

            self._ai_client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)
        else:
            raise ValueError(f"Unknown AI provider: {self.settings.ai_provider}")

        return self._ai_client

    def extract_errors(self, console_output: str) -> list[ErrorContext]:
        """Extract error contexts from console output."""
        lines = console_output.split("\n")
        errors: list[ErrorContext] = []
        seen_contexts: set[str] = set()

        for i, line in enumerate(lines):
            for pattern, error_type in self.ERROR_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    start = max(0, i - self.settings.context_lines)
                    end = min(len(lines), i + self.settings.context_lines + 1)

                    context_key = f"{i}:{line[:50]}"
                    if context_key in seen_contexts:
                        continue
                    seen_contexts.add(context_key)

                    errors.append(
                        ErrorContext(
                            line_number=i + 1,
                            error_line=line.strip(),
                            context_before=lines[start:i],
                            context_after=lines[i + 1 : end],
                            error_type=error_type,
                        )
                    )
                    break

        return errors

    async def analyze_failure(
        self, job_name: str, build_number: Optional[int] = None
    ) -> DebugAnalysis:
        """Analyze a pipeline failure using AI."""
        # Get job details if no build number provided
        if build_number is None:
            job_result = await self.mcp_client.get_job_details(job_name)
            if not job_result.success:
                raise Exception(f"Failed to get job details: {job_result.error}")

            last_failed = job_result.content.get("last_failed_build", {})
            build_number = last_failed.get("number")

            if not build_number:
                raise Exception(f"No failed builds found for job: {job_name}")

        # Get build console output
        console_result = await self.mcp_client.get_build_console(
            job_name, build_number, self.settings.max_log_lines
        )

        if not console_result.success:
            raise Exception(f"Failed to get console output: {console_result.error}")

        console_output = console_result.content
        if isinstance(console_output, dict):
            console_output = console_output.get("console_tail", "")

        # Extract errors from console
        errors = self.extract_errors(console_output)

        # Build prompt for AI analysis
        prompt = self._build_analysis_prompt(job_name, build_number, console_output, errors)

        # Get AI analysis
        analysis_text = await self._get_ai_analysis(prompt)

        # Parse the analysis
        return self._parse_analysis(job_name, build_number, analysis_text)

    def _build_analysis_prompt(
        self,
        job_name: str,
        build_number: int,
        console_output: str,
        errors: list[ErrorContext],
    ) -> str:
        """Build the prompt for AI analysis."""
        error_sections = []
        for err in errors[:10]:  # Limit to 10 errors
            context = "\n".join(err.context_before + [f">>> {err.error_line}"] + err.context_after)
            error_sections.append(
                f"Error at line {err.line_number} ({err.error_type}):\n{context}"
            )

        errors_text = "\n\n".join(error_sections) if error_sections else "No specific errors extracted"

        # Truncate console output if too long
        max_console = 10000
        if len(console_output) > max_console:
            console_output = (
                console_output[:max_console // 2]
                + "\n... [TRUNCATED] ...\n"
                + console_output[-max_console // 2 :]
            )

        return f"""Analyze this Jenkins pipeline failure and provide debugging assistance.

## Job Information
- Job Name: {job_name}
- Build Number: {build_number}

## Extracted Errors
{errors_text}

## Console Output (Last {self.settings.max_log_lines} lines)
```
{console_output}
```

## Analysis Required
Please provide:
1. **Error Summary**: A brief one-line summary of what failed
2. **Root Cause**: The most likely root cause of the failure
3. **Suggested Fixes**: Specific actionable steps to fix the issue (list 3-5)
4. **Related Files**: Any files mentioned that might need changes
5. **Confidence**: Your confidence level (0.0-1.0) in this analysis

Format your response as:
ERROR_SUMMARY: <one line summary>
ROOT_CAUSE: <explanation>
SUGGESTED_FIXES:
- <fix 1>
- <fix 2>
- <fix 3>
RELATED_FILES:
- <file1>
- <file2>
CONFIDENCE: <0.0-1.0>
"""

    async def _get_ai_analysis(self, prompt: str) -> str:
        """Get AI analysis from the configured provider."""
        client = await self._get_ai_client()

        if self.settings.ai_provider == "anthropic":
            response = await client.messages.create(
                model=self.settings.ai_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

        elif self.settings.ai_provider == "openai":
            response = await client.chat.completions.create(
                model=self.settings.ai_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""

        raise ValueError(f"Unknown AI provider: {self.settings.ai_provider}")

    def _parse_analysis(
        self, job_name: str, build_number: int, analysis_text: str
    ) -> DebugAnalysis:
        """Parse the AI analysis response."""
        # Extract sections using regex
        error_summary = self._extract_section(analysis_text, "ERROR_SUMMARY")
        root_cause = self._extract_section(analysis_text, "ROOT_CAUSE")
        suggested_fixes = self._extract_list_section(analysis_text, "SUGGESTED_FIXES")
        related_files = self._extract_list_section(analysis_text, "RELATED_FILES")

        confidence_match = re.search(r"CONFIDENCE:\s*([\d.]+)", analysis_text)
        confidence = float(confidence_match.group(1)) if confidence_match else 0.5

        return DebugAnalysis(
            job_name=job_name,
            build_number=build_number,
            error_summary=error_summary or "Unable to determine error summary",
            root_cause=root_cause or "Unable to determine root cause",
            suggested_fixes=suggested_fixes or ["Review the console output manually"],
            related_files=related_files or [],
            confidence=min(1.0, max(0.0, confidence)),
            raw_analysis=analysis_text,
        )

    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """Extract a single-value section from the analysis."""
        pattern = rf"{section_name}:\s*(.+?)(?=\n[A-Z_]+:|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _extract_list_section(self, text: str, section_name: str) -> list[str]:
        """Extract a list section from the analysis."""
        pattern = rf"{section_name}:\s*\n((?:- .+\n?)+)"
        match = re.search(pattern, text)
        if match:
            items = re.findall(r"- (.+)", match.group(1))
            return [item.strip() for item in items if item.strip()]
        return []

    async def get_recent_failures(self, date: str = "today") -> list[dict[str, Any]]:
        """Get recent failed builds."""
        result = await self.mcp_client.get_failed_builds(date)
        if result.success:
            return result.content if isinstance(result.content, list) else []
        return []

    async def quick_diagnosis(self, job_name: str) -> str:
        """Get a quick diagnosis of the most recent failure."""
        analysis = await self.analyze_failure(job_name)
        return f"""
Pipeline: {analysis.job_name} #{analysis.build_number}
Error: {analysis.error_summary}

Root Cause: {analysis.root_cause}

Suggested Fixes:
{chr(10).join(f'  {i+1}. {fix}' for i, fix in enumerate(analysis.suggested_fixes))}

Confidence: {analysis.confidence:.0%}
"""
