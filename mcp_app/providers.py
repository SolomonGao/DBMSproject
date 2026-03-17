# providers.py - LLM 提供商配置
"""
支持多 LLM 提供商的配置管理
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ProviderConfig:
    """提供商配置"""
    name: str                           # 显示名称
    env_key: str                        # 环境变量名
    base_url: str                       # API 基础地址
    default_model: str                  # 默认模型
    models: list                        # 可用模型列表
    api_key_hint: str                   # API Key 获取提示
    api_key_pattern: str                # API Key 格式提示


# 支持的 LLM 提供商配置
LLM_PROVIDERS: Dict[str, ProviderConfig] = {
    "kimi_code": ProviderConfig(
        name="Kimi Code (推荐)",
        env_key="KIMI_CODE_API_KEY",
        base_url="https://api.kimi.com/coding/v1",
        default_model="kimi-k2-0905-preview",
        models=[
            "kimi-k2-0905-preview",
            "kimi-k2-0711-preview",
            "kimi-k1.5-0711-preview",
            "kimi-latest"
        ],
        api_key_hint="获取地址: Kimi Code CLI 内部使用 / 联系管理员",
        api_key_pattern="以 'sk-' 开头的字符串"
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
        api_key_hint="获取地址: https://platform.moonshot.cn/",
        api_key_pattern="以 'sk-' 开头的字符串"
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
        api_key_hint="获取地址: https://console.anthropic.com/",
        api_key_pattern="以 'sk-ant-' 开头的字符串"
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
        api_key_hint="获取地址: https://ai.google.dev/",
        api_key_pattern="约 39 位字符的字符串"
    )
}


def get_provider(provider_id: str) -> Optional[ProviderConfig]:
    """获取提供商配置"""
    return LLM_PROVIDERS.get(provider_id.lower())


def list_providers() -> Dict[str, str]:
    """列出所有支持的提供商"""
    return {k: v.name for k, v in LLM_PROVIDERS.items()}
