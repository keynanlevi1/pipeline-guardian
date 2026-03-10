"""Configuration management for Pipeline Guardian."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Jenkins MCP Server settings
    jenkins_url: str = Field(
        default="https://jenkins.example.com",
        description="Jenkins server URL",
    )
    jenkins_mcp_command: str = Field(
        default="jenkins-mcp",
        description="Path to Jenkins MCP server executable",
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
        default="azure_foundry",
        description="AI provider: 'anthropic', 'openai', 'azure', or 'azure_foundry'",
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key for Claude",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for GPT models",
    )
    azure_openai_key: Optional[str] = Field(
        default=None,
        description="Azure OpenAI API key",
    )
    azure_openai_base: Optional[str] = Field(
        default=None,
        description="Azure OpenAI endpoint base URL",
    )
    azure_openai_version: str = Field(
        default="2024-12-01-preview",
        description="Azure OpenAI API version",
    )
    azure_openai_deployment: str = Field(
        default="gpt-4",
        description="Azure OpenAI deployment name",
    )
    # Azure AI Foundry settings
    azure_foundry_key: Optional[str] = Field(
        default=None,
        description="Azure AI Foundry API key",
    )
    azure_foundry_endpoint: str = Field(
        default="https://ctera-devops-resources.services.ai.azure.com/models",
        description="Azure AI Foundry models endpoint",
    )
    azure_foundry_model: str = Field(
        default="gpt-5.2-chat",
        description="Azure AI Foundry model name",
    )
    ai_model: str = Field(
        default="gpt-4",
        description="AI model to use for analysis",
    )

    # GitHub settings
    github_token: Optional[str] = Field(
        default=None,
        description="GitHub Personal Access Token",
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

    model_config = {
        "env_prefix": "",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
