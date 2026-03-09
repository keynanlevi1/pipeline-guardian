"""Configuration management for Pipeline Guardian."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Jenkins MCP Plugin settings
    jenkins_url: str = Field(
        default="https://jenkins.example.com",
        description="Jenkins server URL",
    )
    jenkins_mcp_path: str = Field(
        default="/mcp-server/mcp",
        description="Path to Jenkins MCP endpoint",
    )
    jenkins_user: Optional[str] = Field(
        default=None,
        description="Jenkins username for authentication",
    )
    jenkins_token: Optional[str] = Field(
        default=None,
        description="Jenkins API token for authentication",
    )

    # AI Provider settings
    ai_provider: str = Field(
        default="anthropic",
        description="AI provider: 'anthropic' or 'openai'",
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for GPT models",
    )
    ai_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="AI model to use for analysis",
    )

    # Debugging settings
    max_log_lines: int = Field(
        default=500,
        description="Maximum log lines to analyze",
    )
    context_lines: int = Field(
        default=10,
        description="Context lines around errors",
    )

    @property
    def jenkins_mcp_url(self) -> str:
        """Full URL to Jenkins MCP endpoint."""
        base = self.jenkins_url.rstrip("/")
        path = self.jenkins_mcp_path.lstrip("/")
        return f"{base}/{path}"

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
