# config_wizard.py - interactive configuration wizard
"""
interactive configuration wizard：
- guide user selection LLM provider
- collect API Key 和config
- save到 .env file
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
    
    # 彩色transportoutput
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
        """彩色print"""
        prefix = ''
        if bold:
            prefix += self.COLORS['bold']
        if color in self.COLORS:
            prefix += self.COLORS[color]
        
        suffix = self.COLORS['reset'] if prefix else ''
        print(f"{prefix}{text}{suffix}")
    
    def _print_header(self, title: str):
        """print标题"""
        print()
        self._print("=" * 60, 'cyan', bold=True)
        self._print(f"  {title}", 'cyan', bold=True)
        self._print("=" * 60, 'cyan', bold=True)
        print()
    
    def _print_success(self, message: str):
        """printsuccessmessage"""
        self._print(f"✅ {message}", 'green')
    
    def _print_error(self, message: str):
        """printerrormessage"""
        self._print(f"❌ {message}", 'red')
    
    def _print_info(self, message: str):
        """print信info"""
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
            self._print_error("This field cannot be empty，请重newinput")
    
    def _select_provider(self) -> ProviderConfig:
        """step骤 1: select择 LLM provider"""
        self._print_header("step骤 1/3: select择 LLM provider")
        
        self._print("请select择您wantuse AI 服务provider：\n", bold=True)
        
        providers = list(LLM_PROVIDERS.items())
        for idx, (key, provider) in enumerate(providers, 1):
            marker = " ⭐" if key == "kimi_code" else ""
            self._print(f"  [{idx}] {provider.name}{marker}", 'green' if key == "kimi_code" else 'cyan')
            print(f"      默认model: {provider.default_model}")
            print()
        
        while True:
            try:
                choice = input(f"请inputselectitem编号 (1-{len(providers)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(providers):
                    provider_id, provider = providers[idx]
                    self.config['provider_id'] = provider_id
                    self._print_success(f"alreadyselect择: {provider.name}")
                    return provider
                else:
                    self._print_error(f"无效selectitem，请input 1-{len(providers)}")
            except ValueError:
                self._print_error("请input有效number字")
    
    def _input_api_key(self, provider: ProviderConfig) -> str:
        """step骤 2: input API Key"""
        self._print_header("step骤 2/3: config API Key")
        
        self._print(f"provider: {provider.name}", bold=True)
        print()
        self._print_info(provider.api_key_hint)
        print(f"gridpattern提示: {provider.api_key_pattern}")
        print()
        
        # Check if configuration already exists
        existing_key = os.getenv(provider.env_key, '')
        if existing_key and len(existing_key) > 10:
            # verify现有 key Not log error information（简formcheck）
            if '|' not in existing_key and 'ERROR' not in existing_key:
                masked = f"{existing_key[:8]}...{existing_key[-4:]}"
                self._print_info(f"detect到already有 API Key: {masked}")
                keep = input("whetherusealready有config? (y/n，默认 y): ").strip().lower()
                if keep in ('', 'y', 'yes'):
                    self.config['api_key'] = existing_key
                    return existing_key
            else:
                self._print_error("detect到现有 API Key gridpatternasyncconstant，请重newinput")
        
        print()
        print("请粘贴您 API Key (inputWill not display on screen):")
        api_key = self._input_required(
            f"{provider.env_key}=", 
            hide_input=True
        )
        
        # 简formverify
        if not self._validate_api_key(api_key, provider):
            self._print_error("API Key Format seems incorrect，butstillcontinuesave")
        else:
            self._print_success("API Key gridpatternverifynotify过")
        
        self.config['api_key'] = api_key
        return api_key
    
    def _validate_api_key(self, api_key: str, provider: ProviderConfig) -> bool:
        """简formverify API Key gridpattern"""
        if not api_key or len(api_key) < 10:
            return False
        
        # 根据differentproviderverifybefore缀
        if provider.env_key == "MOONSHOT_API_KEY":
            return api_key.startswith("sk-")
        elif provider.env_key == "ANTHROPIC_API_KEY":
            return api_key.startswith("sk-ant-")
        elif provider.env_key == "GEMINI_API_KEY":
            return len(api_key) > 30  # Gemini key notifyconstant较长
        
        return True
    
    def _select_model(self, provider: ProviderConfig) -> str:
        """step骤 3: select择model"""
        self._print_header("step骤 3/3: select择model")
        
        self._print(f"provider: {provider.name}", bold=True)
        print()
        print("availablemodellist:")
        print()
        
        for idx, model in enumerate(provider.models, 1):
            marker = " (默认)" if model == provider.default_model else ""
            color = 'green' if model == provider.default_model else 'cyan'
            self._print(f"  [{idx}] {model}{marker}", color)
        
        print()
        
        while True:
            choice = input(f"请select择model (1-{len(provider.models)}，directenteruse默认): ").strip()
            
            # use默认
            if not choice:
                self._print_success(f"use默认model: {provider.default_model}")
                self.config['model'] = provider.default_model
                return provider.default_model
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(provider.models):
                    selected = provider.models[idx]
                    self._print_success(f"alreadyselect择model: {selected}")
                    self.config['model'] = selected
                    return selected
                else:
                    self._print_error(f"无效selectitem，请input 1-{len(provider.models)}")
            except ValueError:
                self._print_error("请input有效number字")
    
    def _advanced_options(self):
        """advancedconfigselectitem"""
        self._print_header("advancedconfigselectitem（可select）")
        
        print("以underconfiguse默认value即可，如需modifychange请inputnewvalue，directenterskip:")
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
        
        self._print_success("Advanced configuration saved")
    
    def _generate_env_content(self) -> str:
        """generate .env file内容"""
        provider = get_provider(self.config['provider_id'])
        
        lines = [
            "# GDELT MCP Client App config",
            "# Automatically generated by config wizard",
            "",
            "# ============================================",
            "# LLM providerconfig",
            "# ============================================",
            "",
            f"# provider: {provider.name}",
            f"LLM_PROVIDER={self.config['provider_id']}",
            "",
            f"# API Key",
            f"{provider.env_key}={self.config['api_key']}",
            "",
            "# API locationaddress",
            f"LLM_BASE_URL={provider.base_url}",
            "",
            "# model",
            f"LLM_MODEL={self.config['model']}",
            "",
            "# ============================================",
            "# MCP Server config",
            "# ============================================",
            "",
            "# transmittransportmodelpattern: stdio or sse",
            "MCP_TRANSPORT=stdio",
            "",
            "# SSE modelpattern端口（仅 transport=sse when有效）",
            "MCP_PORT=8000",
            "",
            "# ============================================",
            "# LLM paramnumberconfig",
            "# ============================================",
            "",
            f"# 温scheduleparamnumber (0.0 - 1.0)",
            f"LLM_TEMPERATURE={self.config['temperature']}",
            "",
            f"# 最大 Token number",
            f"LLM_MAX_TOKENS={self.config['max_tokens']}",
            "",
            "# ============================================",
            "# 日志config",
            "# ============================================",
            "",
            f"# 日志级别: DEBUG, INFO, WARNING, ERROR",
            f"LOG_LEVEL={self.config['log_level']}",
            "",
            "# Whether to write file logs",
            "LOG_TO_FILE=true",
            "",
            "# ============================================",
            "# 开sendconfig",
            "# ============================================",
            "",
            "# callback试modelpattern",
            "DEBUG=false",
            "",
        ]
        
        return '\n'.join(lines)
    
    def _save_config(self):
        """saveconfig到 .env file"""
        self._print_header("saveconfig")
        
        # generate内容
        content = self._generate_env_content()
        
        # backupoldconfig
        if self.env_file.exists():
            backup = self.env_file.with_suffix('.env.backup')
            backup.write_text(self.env_file.read_text(encoding='utf-8'), encoding='utf-8')
            self._print_info(f"alreadybackupoldconfig到: {backup.name}")
        
        # writeinputnewconfig
        self.env_file.write_text(content, encoding='utf-8')
        
        self._print_success(f"configalreadysave到: {self.env_file}")
        print()
        self._print("You can edit this file at any time to modify configuration", 'yellow')
    
    def run(self) -> bool:
        """
        runconfigwizard
        
        Returns:
            Whether configuration completed successfully
        """
        try:
            self._print_header("🚀 GDELT MCP Client configwizard")
            print()
            print("欢迎use！This wizard will help you configure AI 服务provider。")
            print()
            
            # step骤 1: select择provider
            provider = self._select_provider()
            
            # step骤 2: input API Key
            self._input_api_key(provider)
            
            # step骤 3: select择model
            self._select_model(provider)
            
            # advancedselectitem
            print()
            advanced = input("whetherconfigadvancedselectitem? (y/n，默认 n): ").strip().lower()
            if advanced in ('y', 'yes'):
                self._advanced_options()
            else:
                # use默认value
                self.config['temperature'] = 0.7
                self.config['max_tokens'] = 4096
                self.config['log_level'] = 'INFO'
            
            # saveconfig
            self._save_config()
            
            # completefinish
            self._print_header("configcompletefinish！")
            print()
            self._print_success("You can now run: python run.py")
            print()
            
            return True
            
        except KeyboardInterrupt:
            print()
            print()
            self._print_error("configalreadyfetchmessage")
            return False
        except Exception as e:
            logger.exception(f"configwizarderror: {e}")
            self._print_error(f"configfailed: {e}")
            return False
    
    def check_and_prompt(self) -> bool:
        """
        Check if configuration exists，Start wizard if not exists
        
        Returns:
            configwhetherready
        """
        # Try to load existing configuration
        from dotenv import load_dotenv
        
        if self.env_file.exists():
            load_dotenv(self.env_file)
        else:
            load_dotenv()
        
        # Check if there is anyprovider API Key
        has_config = any(
            os.getenv(provider.env_key)
            for provider in LLM_PROVIDERS.values()
        )
        
        if has_config:
            return True
        
        # 没有config，startwizard
        print()
        self._print("⚠️  未detect到有效 API Key config", 'yellow', bold=True)
        print()
        
        response = input("Whether to start configuration wizard? (y/n，默认 y): ").strip().lower()
        if response in ('', 'y', 'yes'):
            return self.run()
        else:
            self._print_error("缺少config，unablestartapplication")
            return False
