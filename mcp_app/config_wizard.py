# config_wizard.py - interactive configuration wizard
"""
interactive configuration wizard：
- guide user selection LLM provider
- collect API Key andconfig
- saveto .env file
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
        """printmark题"""
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
        """printinfoinfo"""
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
            self._print_error("This field cannot be empty，please重newinput")
    
    def _select_provider(self) -> ProviderConfig:
        """stepstep 1: selectselect LLM provider"""
        self._print_header("stepstep 1/3: selectselect LLM provider")
        
        self._print("pleaseselectselect您wantuse AI serviceprovider：\n", bold=True)
        
        providers = list(LLM_PROVIDERS.items())
        for idx, (key, provider) in enumerate(providers, 1):
            marker = " ⭐" if key == "kimi_code" else ""
            self._print(f"  [{idx}] {provider.name}{marker}", 'green' if key == "kimi_code" else 'cyan')
            print(f"      defaultmodel: {provider.default_model}")
            print()
        
        while True:
            try:
                choice = input(f"pleaseinputselectitem编号 (1-{len(providers)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(providers):
                    provider_id, provider = providers[idx]
                    self.config['provider_id'] = provider_id
                    self._print_success(f"alreadyselectselect: {provider.name}")
                    return provider
                else:
                    self._print_error(f"noeffectselectitem，pleaseinput 1-{len(providers)}")
            except ValueError:
                self._print_error("pleaseinputhaseffectnumber字")
    
    def _input_api_key(self, provider: ProviderConfig) -> str:
        """stepstep 2: input API Key"""
        self._print_header("stepstep 2/3: config API Key")
        
        self._print(f"provider: {provider.name}", bold=True)
        print()
        self._print_info(provider.api_key_hint)
        print(f"gridpattern提show: {provider.api_key_pattern}")
        print()
        
        # Check if configuration already exists
        existing_key = os.getenv(provider.env_key, '')
        if existing_key and len(existing_key) > 10:
            # verifynowhas key Not log error information（simpleformcheck）
            if '|' not in existing_key and 'ERROR' not in existing_key:
                masked = f"{existing_key[:8]}...{existing_key[-4:]}"
                self._print_info(f"detecttoalreadyhas API Key: {masked}")
                keep = input("whetherusealreadyhasconfig? (y/n，default y): ").strip().lower()
                if keep in ('', 'y', 'yes'):
                    self.config['api_key'] = existing_key
                    return existing_key
            else:
                self._print_error("detecttonowhas API Key gridpatternasyncconstant，please重newinput")
        
        print()
        print("please粘贴您 API Key (inputWill not display on screen):")
        api_key = self._input_required(
            f"{provider.env_key}=", 
            hide_input=True
        )
        
        # simpleformverify
        if not self._validate_api_key(api_key, provider):
            self._print_error("API Key Format seems incorrect，butstillcontinuesave")
        else:
            self._print_success("API Key gridpatternverifynotify过")
        
        self.config['api_key'] = api_key
        return api_key
    
    def _validate_api_key(self, api_key: str, provider: ProviderConfig) -> bool:
        """simpleformverify API Key gridpattern"""
        if not api_key or len(api_key) < 10:
            return False
        
        # 根据differentproviderverifybefore缀
        if provider.env_key == "MOONSHOT_API_KEY":
            return api_key.startswith("sk-")
        elif provider.env_key == "ANTHROPIC_API_KEY":
            return api_key.startswith("sk-ant-")
        elif provider.env_key == "GEMINI_API_KEY":
            return len(api_key) > 30  # Gemini key notifyconstant较long
        
        return True
    
    def _select_model(self, provider: ProviderConfig) -> str:
        """stepstep 3: selectselectmodel"""
        self._print_header("stepstep 3/3: selectselectmodel")
        
        self._print(f"provider: {provider.name}", bold=True)
        print()
        print("availablemodellist:")
        print()
        
        for idx, model in enumerate(provider.models, 1):
            marker = " (default)" if model == provider.default_model else ""
            color = 'green' if model == provider.default_model else 'cyan'
            self._print(f"  [{idx}] {model}{marker}", color)
        
        print()
        
        while True:
            choice = input(f"pleaseselectselectmodel (1-{len(provider.models)}，directenterusedefault): ").strip()
            
            # usedefault
            if not choice:
                self._print_success(f"usedefaultmodel: {provider.default_model}")
                self.config['model'] = provider.default_model
                return provider.default_model
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(provider.models):
                    selected = provider.models[idx]
                    self._print_success(f"alreadyselectselectmodel: {selected}")
                    self.config['model'] = selected
                    return selected
                else:
                    self._print_error(f"noeffectselectitem，pleaseinput 1-{len(provider.models)}")
            except ValueError:
                self._print_error("pleaseinputhaseffectnumber字")
    
    def _advanced_options(self):
        """advancedconfigselectitem"""
        self._print_header("advancedconfigselectitem（canselect）")
        
        print("thereforeunderconfigusedefaultvalue即can，if需modifychangepleaseinputnewvalue，directenterskip:")
        print()
        
        # Temperature
        temp = input("Temperature (0.0-1.0, default 0.7): ").strip()
        self.config['temperature'] = float(temp) if temp else 0.7
        
        # Max Tokens
        max_tokens = input("Max Tokens (default 4096): ").strip()
        self.config['max_tokens'] = int(max_tokens) if max_tokens else 4096
        
        # Log Level
        print()
        print("log level: [1] DEBUG [2] INFO [3] WARNING [4] ERROR")
        log_choice = input("pleaseselectselect (default 2-INFO): ").strip()
        log_levels = {'1': 'DEBUG', '2': 'INFO', '3': 'WARNING', '4': 'ERROR'}
        self.config['log_level'] = log_levels.get(log_choice, 'INFO')
        
        self._print_success("Advanced configuration saved")
    
    def _generate_env_content(self) -> str:
        """generate .env fileinsidecontent"""
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
            "# SSE modelpatternend口（仅 transport=sse whenhaseffect）",
            "MCP_PORT=8000",
            "",
            "# ============================================",
            "# LLM paramnumberconfig",
            "# ============================================",
            "",
            f"# 温scheduleparamnumber (0.0 - 1.0)",
            f"LLM_TEMPERATURE={self.config['temperature']}",
            "",
            f"# mostbig Token number",
            f"LLM_MAX_TOKENS={self.config['max_tokens']}",
            "",
            "# ============================================",
            "# 日志config",
            "# ============================================",
            "",
            f"# log level: DEBUG, INFO, WARNING, ERROR",
            f"LOG_LEVEL={self.config['log_level']}",
            "",
            "# Whether to write file logs",
            "LOG_TO_FILE=true",
            "",
            "# ============================================",
            "# opensendconfig",
            "# ============================================",
            "",
            "# callback试modelpattern",
            "DEBUG=false",
            "",
        ]
        
        return '\n'.join(lines)
    
    def _save_config(self):
        """saveconfigto .env file"""
        self._print_header("saveconfig")
        
        # generateinsidecontent
        content = self._generate_env_content()
        
        # backupoldconfig
        if self.env_file.exists():
            backup = self.env_file.with_suffix('.env.backup')
            backup.write_text(self.env_file.read_text(encoding='utf-8'), encoding='utf-8')
            self._print_info(f"alreadybackupoldconfigto: {backup.name}")
        
        # writeinputnewconfig
        self.env_file.write_text(content, encoding='utf-8')
        
        self._print_success(f"configalreadysaveto: {self.env_file}")
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
            print("欢迎use！This wizard will help you configure AI serviceprovider。")
            print()
            
            # stepstep 1: selectselectprovider
            provider = self._select_provider()
            
            # stepstep 2: input API Key
            self._input_api_key(provider)
            
            # stepstep 3: selectselectmodel
            self._select_model(provider)
            
            # advancedselectitem
            print()
            advanced = input("whetherconfigadvancedselectitem? (y/n，default n): ").strip().lower()
            if advanced in ('y', 'yes'):
                self._advanced_options()
            else:
                # usedefaultvalue
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
        
        # nohasconfig，startwizard
        print()
        self._print("⚠️  notdetecttohaseffect API Key config", 'yellow', bold=True)
        print()
        
        response = input("Whether to start configuration wizard? (y/n，default y): ").strip().lower()
        if response in ('', 'y', 'yes'):
            return self.run()
        else:
            self._print_error("缺少config，unablestartapplication")
            return False
