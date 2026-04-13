# config_wizard.py - interactive configuration wizard
"""
interactive configuration wizard：
- guide user selection LLM provider
- collect API Key 和配置
- 保存到 .env 文件
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from .providers import LLM_PROVIDERS, get_provider, ProviderConfig
from .logger import get_logger

logger = get_logger("config_wizard")


class ConfigWizard:
    """interactive configuration wizard"""
    
    # 彩色输出
    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'cyan': '\033[36m',
        'red': '\033[31m',
    }
    
    def __init__(self, env_file: Optional[Path] = None):
        self.project_root = Path(__file__).parent.parent
        self.env_file = env_file or (self.project_root / ".env")
        self.config: Dict[str, Any] = {}
    
    def _print(self, text: str, color: str = '', bold: bool = False):
        """彩色打印"""
        prefix = ''
        if bold:
            prefix += self.COLORS['bold']
        if color in self.COLORS:
            prefix += self.COLORS[color]
        
        suffix = self.COLORS['reset'] if prefix else ''
        print(f"{prefix}{text}{suffix}")
    
    def _print_header(self, title: str):
        """打印标题"""
        print()
        self._print("=" * 60, 'cyan', bold=True)
        self._print(f"  {title}", 'cyan', bold=True)
        self._print("=" * 60, 'cyan', bold=True)
        print()
    
    def _print_success(self, message: str):
        """打印成功消息"""
        self._print(f"✅ {message}", 'green')
    
    def _print_error(self, message: str):
        """打印错误消息"""
        self._print(f"❌ {message}", 'red')
    
    def _print_info(self, message: str):
        """打印信息"""
        self._print(f"ℹ️  {message}", 'blue')
    
    def _input_required(self, prompt: str, hide_input: bool = False) -> str:
        """fetch必填input"""
        while True:
            if hide_input:
                import getpass
                value = getpass.getpass(prompt)
            else:
                value = input(prompt).strip()
            
            if value:
                return value
            self._print_error("此字段不能为空，请重新input")
    
    def _select_provider(self) -> ProviderConfig:
        """步骤 1: select择 LLM provider"""
        self._print_header("步骤 1/3: select择 LLM provider")
        
        self._print("请select择您要use AI 服务provider：\n", bold=True)
        
        providers = list(LLM_PROVIDERS.items())
        for idx, (key, provider) in enumerate(providers, 1):
            marker = " ⭐" if key == "kimi_code" else ""
            self._print(f"  [{idx}] {provider.name}{marker}", 'green' if key == "kimi_code" else 'cyan')
            print(f"      默认模型: {provider.default_model}")
            print()
        
        while True:
            try:
                choice = input(f"请inputselectitem编号 (1-{len(providers)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(providers):
                    provider_id, provider = providers[idx]
                    self.config['provider_id'] = provider_id
                    self._print_success(f"已select择: {provider.name}")
                    return provider
                else:
                    self._print_error(f"无效selectitem，请input 1-{len(providers)}")
            except ValueError:
                self._print_error("请input有效数字")
    
    def _input_api_key(self, provider: ProviderConfig) -> str:
        """步骤 2: input API Key"""
        self._print_header("步骤 2/3: 配置 API Key")
        
        self._print(f"provider: {provider.name}", bold=True)
        print()
        self._print_info(provider.api_key_hint)
        print(f"格式提示: {provider.api_key_pattern}")
        print()
        
        # 检查是否已有配置
        existing_key = os.getenv(provider.env_key, '')
        if existing_key and len(existing_key) > 10:
            # verify现有 key 不是日志错误信息（简单检查）
            if '|' not in existing_key and 'ERROR' not in existing_key:
                masked = f"{existing_key[:8]}...{existing_key[-4:]}"
                self._print_info(f"检测到已有 API Key: {masked}")
                keep = input("是否use已有配置? (y/n，默认 y): ").strip().lower()
                if keep in ('', 'y', 'yes'):
                    self.config['api_key'] = existing_key
                    return existing_key
            else:
                self._print_error("检测到现有 API Key 格式异常，请重新input")
        
        print()
        print("请粘贴您 API Key (input不会显示在屏幕上):")
        api_key = self._input_required(
            f"{provider.env_key}=", 
            hide_input=True
        )
        
        # 简单verify
        if not self._validate_api_key(api_key, provider):
            self._print_error("API Key 格式似乎不正确，但仍继续保存")
        else:
            self._print_success("API Key 格式verify通过")
        
        self.config['api_key'] = api_key
        return api_key
    
    def _validate_api_key(self, api_key: str, provider: ProviderConfig) -> bool:
        """简单verify API Key 格式"""
        if not api_key or len(api_key) < 10:
            return False
        
        # 根据不同providerverifybefore缀
        if provider.env_key == "MOONSHOT_API_KEY":
            return api_key.startswith("sk-")
        elif provider.env_key == "ANTHROPIC_API_KEY":
            return api_key.startswith("sk-ant-")
        elif provider.env_key == "GEMINI_API_KEY":
            return len(api_key) > 30  # Gemini key 通常较长
        
        return True
    
    def _select_model(self, provider: ProviderConfig) -> str:
        """步骤 3: select择模型"""
        self._print_header("步骤 3/3: select择模型")
        
        self._print(f"provider: {provider.name}", bold=True)
        print()
        print("可用模型列表:")
        print()
        
        for idx, model in enumerate(provider.models, 1):
            marker = " (默认)" if model == provider.default_model else ""
            color = 'green' if model == provider.default_model else 'cyan'
            self._print(f"  [{idx}] {model}{marker}", color)
        
        print()
        
        while True:
            choice = input(f"请select择模型 (1-{len(provider.models)}，直接回车use默认): ").strip()
            
            # use默认
            if not choice:
                self._print_success(f"use默认模型: {provider.default_model}")
                self.config['model'] = provider.default_model
                return provider.default_model
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(provider.models):
                    selected = provider.models[idx]
                    self._print_success(f"已select择模型: {selected}")
                    self.config['model'] = selected
                    return selected
                else:
                    self._print_error(f"无效selectitem，请input 1-{len(provider.models)}")
            except ValueError:
                self._print_error("请input有效数字")
    
    def _advanced_options(self):
        """高级配置selectitem"""
        self._print_header("高级配置selectitem（可select）")
        
        print("以下配置use默认value即可，如需修改请input新value，直接回车跳过:")
        print()
        
        # Temperature
        temp = input("Temperature (0.0-1.0, 默认 0.7): ").strip()
        self.config['temperature'] = float(temp) if temp else 0.7
        
        # Max Tokens
        max_tokens = input("Max Tokens (默认 4096): ").strip()
        self.config['max_tokens'] = int(max_tokens) if max_tokens else 4096
        
        # Log Level
        print()
        print("日志级别: [1] DEBUG [2] INFO [3] WARNING [4] ERROR")
        log_choice = input("请select择 (默认 2-INFO): ").strip()
        log_levels = {'1': 'DEBUG', '2': 'INFO', '3': 'WARNING', '4': 'ERROR'}
        self.config['log_level'] = log_levels.get(log_choice, 'INFO')
        
        self._print_success("高级配置已保存")
    
    def _generate_env_content(self) -> str:
        """生成 .env 文件内容"""
        provider = get_provider(self.config['provider_id'])
        
        lines = [
            "# GDELT MCP Client App 配置",
            "# 由配置向导自动生成",
            "",
            "# ============================================",
            "# LLM provider配置",
            "# ============================================",
            "",
            f"# provider: {provider.name}",
            f"LLM_PROVIDER={self.config['provider_id']}",
            "",
            f"# API Key",
            f"{provider.env_key}={self.config['api_key']}",
            "",
            "# API 地址",
            f"LLM_BASE_URL={provider.base_url}",
            "",
            "# 模型",
            f"LLM_MODEL={self.config['model']}",
            "",
            "# ============================================",
            "# MCP Server 配置",
            "# ============================================",
            "",
            "# 传输模式: stdio 或 sse",
            "MCP_TRANSPORT=stdio",
            "",
            "# SSE 模式端口（仅 transport=sse 时有效）",
            "MCP_PORT=8000",
            "",
            "# ============================================",
            "# LLM 参数配置",
            "# ============================================",
            "",
            f"# 温度参数 (0.0 - 1.0)",
            f"LLM_TEMPERATURE={self.config['temperature']}",
            "",
            f"# 最大 Token 数",
            f"LLM_MAX_TOKENS={self.config['max_tokens']}",
            "",
            "# ============================================",
            "# 日志配置",
            "# ============================================",
            "",
            f"# 日志级别: DEBUG, INFO, WARNING, ERROR",
            f"LOG_LEVEL={self.config['log_level']}",
            "",
            "# 是否写入文件日志",
            "LOG_TO_FILE=true",
            "",
            "# ============================================",
            "# 开发配置",
            "# ============================================",
            "",
            "# 调试模式",
            "DEBUG=false",
            "",
        ]
        
        return '\n'.join(lines)
    
    def _save_config(self):
        """保存配置到 .env 文件"""
        self._print_header("保存配置")
        
        # 生成内容
        content = self._generate_env_content()
        
        # backup旧配置
        if self.env_file.exists():
            backup = self.env_file.with_suffix('.env.backup')
            backup.write_text(self.env_file.read_text(encoding='utf-8'), encoding='utf-8')
            self._print_info(f"已backup旧配置到: {backup.name}")
        
        # 写入新配置
        self.env_file.write_text(content, encoding='utf-8')
        
        self._print_success(f"配置已保存到: {self.env_file}")
        print()
        self._print("您可以随时编辑此文件来修改配置", 'yellow')
    
    def run(self) -> bool:
        """
        运行配置向导
        
        Returns:
            是否成功完成配置
        """
        try:
            self._print_header("🚀 GDELT MCP Client 配置向导")
            print()
            print("欢迎use！这个向导将帮助您配置 AI 服务provider。")
            print()
            
            # 步骤 1: select择provider
            provider = self._select_provider()
            
            # 步骤 2: input API Key
            self._input_api_key(provider)
            
            # 步骤 3: select择模型
            self._select_model(provider)
            
            # 高级selectitem
            print()
            advanced = input("是否配置高级selectitem? (y/n，默认 n): ").strip().lower()
            if advanced in ('y', 'yes'):
                self._advanced_options()
            else:
                # use默认value
                self.config['temperature'] = 0.7
                self.config['max_tokens'] = 4096
                self.config['log_level'] = 'INFO'
            
            # 保存配置
            self._save_config()
            
            # 完成
            self._print_header("配置完成！")
            print()
            self._print_success("您现在可以运行: python run.py")
            print()
            
            return True
            
        except KeyboardInterrupt:
            print()
            print()
            self._print_error("配置已取消")
            return False
        except Exception as e:
            logger.exception(f"配置向导错误: {e}")
            self._print_error(f"配置失败: {e}")
            return False
    
    def check_and_prompt(self) -> bool:
        """
        检查配置是否存在，不存在则启动向导
        
        Returns:
            配置是否就绪
        """
        # 尝试加载现有配置
        from dotenv import load_dotenv
        
        if self.env_file.exists():
            load_dotenv(self.env_file)
        else:
            load_dotenv()
        
        # 检查是否有任何provider API Key
        has_config = any(
            os.getenv(provider.env_key)
            for provider in LLM_PROVIDERS.values()
        )
        
        if has_config:
            return True
        
        # 没有配置，启动向导
        print()
        self._print("⚠️  未检测到有效 API Key 配置", 'yellow', bold=True)
        print()
        
        response = input("是否启动配置向导? (y/n，默认 y): ").strip().lower()
        if response in ('', 'y', 'yes'):
            return self.run()
        else:
            self._print_error("缺少配置，无法启动应用")
            return False
