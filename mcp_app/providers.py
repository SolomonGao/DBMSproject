# providers.py - LLM Provider Configuration
"""
Multi-LLM provider configuration management
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ProviderConfig:
    """Provider Configuration"""
    name: str                           # Display name
    env_key: str                        # Environment variable name
    base_url: str                       # API base URL
    default_model: str                  # Default model
    models: list                        # Available models list
    api_key_hint: str                   # API Key acquisition hint
    api_key_pattern: str                # API Key format hint


# Supported LLM provider configurations
LLM_PROVIDERS: Dict[str, ProviderConfig] = {
    "kimi_code": ProviderConfig(
        name="Kimi Code (Recommended)",
        env_key="KIMI_CODE_API_KEY",
        base_url="https://api.kimi.com/coding/v1",
        default_model="kimi-k2-0905-preview",
        models=[
            "kimi-k2-0905-preview",
            "kimi-k2-0711-preview",
            "kimi-k1.5-0711-preview",
            "kimi-latest"
        ],
        api_key_hint="Get from: Kimi Code CLI internal use / contact admin",
        api_key_pattern="String starting with 'sk-'"
    ),
    
    "moonshot": ProviderConfig(
        name="Moonshot AI (Open Platform)",
        env_key="MOONSHOT_API_KEY",
        base_url="https://api.moonshot.cn/v1",
        default_model="kimi-k2-0905-preview",
        models=[
            "kimi-k2-0905-preview",
            "kimi-k2-0711-preview", 
            "kimi-k1.5-0711-preview",
            "kimi-latest"
        ],
        api_key_hint="Get from: https://platform.moonshot.cn/",
        api_key_pattern="String starting with 'sk-'"
    ),
    
    "claude": ProviderConfig(
        name="Claude (Anthropic)",
        env_key="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com/v1",
        default_model="claude-3-5-sonnet-20241022",
        models=[
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229"
        ],
        api_key_hint="Get from: https://console.anthropic.com/",
        api_key_pattern="String starting with 'sk-ant-'"
    ),
    
    "gemini": ProviderConfig(
        name="Gemini (Google)",
        env_key="GEMINI_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-1.5-pro",
        models=[
            "gemini-1.5-pro",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-exp-1206"
        ],
        api_key_hint="Get from: https://ai.google.dev/",
        api_key_pattern="String of about 39 characters"
    )
}


def get_provider(provider_id: str) -> Optional[ProviderConfig]:
    """Get provider configuration"""
    return LLM_PROVIDERS.get(provider_id.lower())


def list_providers() -> Dict[str, str]:
    """List all supported providers"""
    return {k: v.name for k, v in LLM_PROVIDERS.items()}
