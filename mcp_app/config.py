# config.py - 配置管理模块
"""
配置管理：
- 从 .env 文件加载敏感配置
- 从 config.yaml 加载用户偏好（可选）
- 配置验证和默认值处理
"""

import os
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from dotenv import load_dotenv

from .logger import get_logger
from .providers import get_provider, LLM_PROVIDERS

logger = get_logger("config")


@dataclass
class AppConfig:
    """应用配置类（支持多 LLM 提供商）"""
    
    # LLM 提供商配置
    llm_provider: str = "kimi"  # 默认 kimi
    
    # API Keys (支持多个)
    kimi_code_api_key: str = ""      # Kimi Code API (api.kimi.com)
    moonshot_api_key: str = ""       # Moonshot Open Platform
    anthropic_api_key: str = ""      # Claude
    gemini_api_key: str = ""         # Gemini
    
    # MCP Server 配置
    mcp_server_path: str = ""
    mcp_transport: str = "stdio"
    mcp_port: int = 8000
    
    # LLM 配置
    llm_model: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    
    # 日志配置
    log_level: str = "INFO"
    log_dir: Optional[Path] = None
    log_to_file: bool = True
    
    # 应用配置
    debug: bool = False
    
    def __post_init__(self):
        """验证配置有效性"""
        errors = []
        
        # 获取当前提供商配置
        provider = get_provider(self.llm_provider)
        if not provider:
            errors.append(f"不支持的 LLM 提供商: {self.llm_provider}")
            return
        
        # 根据提供商获取对应的 API Key
        api_key = self.get_api_key()
        if not api_key:
            errors.append(f"{provider.env_key} 未设置")
        
        # 自动填充默认的 base_url 和 model
        if not self.llm_base_url:
            self.llm_base_url = provider.base_url
        if not self.llm_model:
            self.llm_model = provider.default_model
        
        if not self.mcp_server_path:
            # 自动检测 server.py 路径
            project_root = self._get_project_root()
            default_path = project_root / "mcp_server" / "server.py"
            if default_path.exists():
                self.mcp_server_path = str(default_path)
                logger.debug(f"自动检测到 MCP Server: {default_path}")
            else:
                errors.append(f"未找到 MCP Server 文件: {default_path}")
        
        # 设置日志目录
        if self.log_to_file and self.log_dir is None:
            self.log_dir = self._get_project_root() / "logs"
        
        if errors:
            for error in errors:
                logger.error(f"配置错误: {error}")
            raise ValueError("配置验证失败，请检查 .env 文件")
    
    def _get_project_root(self) -> Path:
        """获取项目根目录"""
        return Path(__file__).parent.parent
    
    def to_dict(self) -> dict:
        """转换为字典（用于日志记录）"""
        data = asdict(self)
        # 隐藏敏感信息
        if self.moonshot_api_key:
            data['moonshot_api_key'] = f"{self.moonshot_api_key[:8]}...{self.moonshot_api_key[-4:]}"
        return data
    
    def get_api_key(self) -> str:
        """获取当前提供商的 API Key"""
        provider = get_provider(self.llm_provider)
        if not provider:
            return ""
        
        if provider.env_key == "KIMI_CODE_API_KEY":
            return self.kimi_code_api_key
        elif provider.env_key == "MOONSHOT_API_KEY":
            return self.moonshot_api_key
        elif provider.env_key == "ANTHROPIC_API_KEY":
            return self.anthropic_api_key
        elif provider.env_key == "GEMINI_API_KEY":
            return self.gemini_api_key
        return ""
    
    def get_masked_api_key(self) -> str:
        """获取脱敏的 API Key"""
        api_key = self.get_api_key()
        if not api_key:
            return "未设置"
        if len(api_key) < 12:
            return "***"
        return f"{api_key[:8]}...{api_key[-4:]}"


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, env_file: Optional[Path] = None):
        self.project_root = Path(__file__).parent.parent
        self.env_file = env_file or (self.project_root / ".env")
        self._loaded_config: Optional[AppConfig] = None
    
    def load(self) -> AppConfig:
        """加载配置"""
        logger.info("正在加载配置...")
        
        # 加载 .env 文件
        self._load_env_file()
        
        # 构建配置对象
        config = self._build_config()
        
        self._loaded_config = config
        logger.info("配置加载完成")
        
        return config
    
    def _load_env_file(self):
        """加载环境变量文件"""
        if self.env_file.exists():
            load_dotenv(self.env_file)
            logger.debug(f"已加载 .env 文件: {self.env_file}")
        else:
            logger.warning(f"未找到 .env 文件: {self.env_file}")
            logger.info("请复制 .env_example 为 .env 并填写您的 API Key")
    
    def _build_config(self) -> AppConfig:
        """从环境变量构建配置"""
        # 读取可选的 YAML 配置
        yaml_config = self._load_yaml_config()
        
        # 环境变量优先级高于 YAML
        def get_env(key: str, default=None, cast_type=str):
            value = os.getenv(key)
            if value is None:
                value = yaml_config.get(key.lower(), default)
            if value is not None and cast_type != str:
                try:
                    value = cast_type(value)
                except (ValueError, TypeError):
                    value = default
            return value
        
        # 获取提供商
        provider_id = get_env("LLM_PROVIDER", "kimi").lower()
        provider = get_provider(provider_id)
        
        # 如果提供商不存在，使用默认
        if not provider:
            provider_id = "kimi"
            provider = get_provider("kimi")
        
        return AppConfig(
            llm_provider=provider_id,
            kimi_code_api_key=get_env("KIMI_CODE_API_KEY", ""),
            moonshot_api_key=get_env("MOONSHOT_API_KEY", ""),
            anthropic_api_key=get_env("ANTHROPIC_API_KEY", ""),
            gemini_api_key=get_env("GEMINI_API_KEY", ""),
            mcp_server_path=get_env("MCP_SERVER_PATH", ""),
            mcp_transport=get_env("MCP_TRANSPORT", "stdio"),
            mcp_port=get_env("MCP_PORT", 8000, int),
            llm_model=get_env("LLM_MODEL", provider.default_model),
            llm_base_url=get_env("LLM_BASE_URL", provider.base_url),
            llm_temperature=get_env("LLM_TEMPERATURE", 0.7, float),
            llm_max_tokens=get_env("LLM_MAX_TOKENS", 4096, int),
            log_level=get_env("LOG_LEVEL", "INFO"),
            log_to_file=get_env("LOG_TO_FILE", "true").lower() == "true",
            debug=get_env("DEBUG", "false").lower() == "true",
        )
    
    def _load_yaml_config(self) -> dict:
        """加载 YAML 配置文件（可选）"""
        config_yaml = self.project_root / "config.yaml"
        if config_yaml.exists():
            try:
                import yaml
                with open(config_yaml, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except ImportError:
                logger.debug("未安装 PyYAML，跳过 config.yaml 加载")
            except Exception as e:
                logger.warning(f"加载 config.yaml 失败: {e}")
        return {}
    
    def print_config(self, config: AppConfig):
        """打印配置摘要（隐藏敏感信息）"""
        provider = get_provider(config.llm_provider)
        provider_name = provider.name if provider else config.llm_provider
        
        logger.info("=" * 50)
        logger.info("配置摘要:")
        logger.info(f"  LLM 提供商: {provider_name}")
        logger.info(f"  API Key: {config.get_masked_api_key()}")
        logger.info(f"  LLM 模型: {config.llm_model}")
        logger.info(f"  LLM 地址: {config.llm_base_url}")
        logger.info(f"  MCP Server: {config.mcp_server_path}")
        logger.info(f"  传输模式: {config.mcp_transport}")
        if config.mcp_transport == "sse":
            logger.info(f"  端口: {config.mcp_port}")
        logger.info(f"  日志级别: {config.log_level}")
        if config.log_to_file:
            logger.info(f"  日志目录: {config.log_dir}")
        logger.info("=" * 50)


# 便捷函数
def load_config(env_file: Optional[Path] = None) -> AppConfig:
    """加载配置"""
    loader = ConfigLoader(env_file)
    return loader.load()


def print_config(config: AppConfig):
    """打印配置"""
    loader = ConfigLoader()
    loader.print_config(config)
