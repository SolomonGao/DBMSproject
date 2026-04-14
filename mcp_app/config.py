# config.py - Configuration Management Module
"""
Configuration Management:
- Load sensitive config from .env file
- Load user preferences from config.yaml (optional)
- Config validation and default value handling
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
    """Application Configuration Class (Supports multiple LLM providers)"""
    
    # LLM Provider Configuration
    llm_provider: str = "kimi"  # Default: kimi
    
    # API Keys (Multiple supported)
    kimi_code_api_key: str = ""      # Kimi Code API (api.kimi.com)
    moonshot_api_key: str = ""       # Moonshot Open Platform
    anthropic_api_key: str = ""      # Claude
    gemini_api_key: str = ""         # Gemini
    
    # MCP Server Configuration
    mcp_server_path: str = ""
    mcp_transport: str = "stdio"
    mcp_port: int = 8000
    
    # LLM Configuration
    llm_model: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    
    # Logging Configuration
    log_level: str = "INFO"
    log_dir: Optional[Path] = None
    log_to_file: bool = True
    
    # Application Configuration
    debug: bool = False
    
    def __post_init__(self):
        """Validate configuration validity"""
        errors = []
        
        # Get current provider configuration
        provider = get_provider(self.llm_provider)
        if not provider:
            errors.append(f"Unsupported LLM provider: {self.llm_provider}")
            return
        
        # Get corresponding API Key based on provider
        api_key = self.get_api_key()
        if not api_key:
            errors.append(f"{provider.env_key} not set")
        
        # Auto-fill default base_url and model
        if not self.llm_base_url:
            self.llm_base_url = provider.base_url
        if not self.llm_model:
            self.llm_model = provider.default_model
        
        if not self.mcp_server_path:
            # Auto-detect server.py path
            project_root = self._get_project_root()
            default_path = project_root / "mcp_server" / "main.py"
            if default_path.exists():
                self.mcp_server_path = str(default_path)
                logger.debug(f"Auto-detected MCP Server: {default_path}")
            else:
                errors.append(f"MCP Server file not found: {default_path}")
        
        # Set log directory
        if self.log_to_file and self.log_dir is None:
            self.log_dir = self._get_project_root() / "logs"
        
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            raise ValueError("Configuration validation failed, please check .env file")
    
    def _get_project_root(self) -> Path:
        """Get project root directory"""
        return Path(__file__).parent.parent
    
    def to_dict(self) -> dict:
        """Convert to dictionary (for logging)"""
        data = asdict(self)
        # Hide sensitive information
        if self.moonshot_api_key:
            data['moonshot_api_key'] = f"{self.moonshot_api_key[:8]}...{self.moonshot_api_key[-4:]}"
        return data
    
    def get_api_key(self) -> str:
        """Get current provider's API Key"""
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
        """Get masked API Key"""
        api_key = self.get_api_key()
        if not api_key:
            return "Not set"
        if len(api_key) < 12:
            return "***"
        return f"{api_key[:8]}...{api_key[-4:]}"


class ConfigLoader:
    """Configuration Loader"""
    
    def __init__(self, env_file: Optional[Path] = None):
        self.project_root = Path(__file__).parent.parent
        self.env_file = env_file or (self.project_root / ".env")
        self._loaded_config: Optional[AppConfig] = None
    
    def load(self) -> AppConfig:
        """Load configuration"""
        logger.info("Loading configuration...")
        
        # Load .env file
        self._load_env_file()
        
        # Build configuration object
        config = self._build_config()
        
        self._loaded_config = config
        logger.info("Configuration loaded")
        
        return config
    
    def _load_env_file(self):
        """Load environment variables file"""
        if self.env_file.exists():
            load_dotenv(self.env_file)
            logger.debug(f"Loaded .env file: {self.env_file}")
        else:
            logger.warning(f".env file not found: {self.env_file}")
            logger.info("Please copy .env_example to .env and fill in your API Key")
    
    def _build_config(self) -> AppConfig:
        """Build configuration from environment variables"""
        # Read optional YAML configuration
        yaml_config = self._load_yaml_config()
        
        # Environment variables take priority over YAML
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
        
        # Get provider
        provider_id = get_env("LLM_PROVIDER", "kimi").lower()
        provider = get_provider(provider_id)
        
        # If provider doesn't exist, use default
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
        """Load YAML configuration file (optional)"""
        config_yaml = self.project_root / "config.yaml"
        if config_yaml.exists():
            try:
                import yaml
                with open(config_yaml, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except ImportError:
                logger.debug("PyYAML not installed, skipping config.yaml loading")
            except Exception as e:
                logger.warning(f"Failed to load config.yaml: {e}")
        return {}
    
    def print_config(self, config: AppConfig):
        """Print configuration summary (hide sensitive information)"""
        provider = get_provider(config.llm_provider)
        provider_name = provider.name if provider else config.llm_provider
        
        logger.info("=" * 50)
        logger.info("Configuration Summary:")
        logger.info(f"  LLM Provider: {provider_name}")
        logger.info(f"  API Key: {config.get_masked_api_key()}")
        logger.info(f"  LLM Model: {config.llm_model}")
        logger.info(f"  LLM URL: {config.llm_base_url}")
        logger.info(f"  MCP Server: {config.mcp_server_path}")
        logger.info(f"  Transport Mode: {config.mcp_transport}")
        if config.mcp_transport == "sse":
            logger.info(f"  Port: {config.mcp_port}")
        logger.info(f"  Log Level: {config.log_level}")
        if config.log_to_file:
            logger.info(f"  Log Directory: {config.log_dir}")
        logger.info("=" * 50)


# Helper functions
def load_config(env_file: Optional[Path] = None) -> AppConfig:
    """Load configuration"""
    loader = ConfigLoader(env_file)
    return loader.load()


def print_config(config: AppConfig):
    """Print configuration"""
    loader = ConfigLoader()
    loader.print_config(config)
