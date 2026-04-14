#!/usr/bin/env python3
"""test API join - tastetrydifferent Headers falseinstall"""
import os
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

import httpx

api_key = os.getenv('KIMI_CODE_API_KEY') or os.getenv('MOONSHOT_API_KEY')
if not api_key or '|' in api_key:
    print("Error: API Key not found or invalid")
    sys.exit(1)

base_url = "https://api.kimi.com/coding/v1"

print(f"Testing API: {base_url}")
print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
print()

# Testdifferent User-Agent falseinstall
headers_options = [
    {
        "name": "Claude Code",
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "claude-code/1.0",
            "X-Client-Name": "claude-code",
        }
    },
    {
        "name": "Kimi CLI",
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "kimi-cli/1.0.0",
            "X-Client-Name": "kimi-cli",
            "X-Kimi-Cli-Version": "1.0.0",
        }
    },
    {
        "name": "Roo Code",
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Roo-Code/1.0",
            "X-Client-Name": "roo-code",
        }
    },
    {
        "name": "Kilo Code",
        "headers": {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "kilo-code/1.0",
            "X-Client-Name": "kilo-code",
        }
    },
]

data = {
    "model": "kimi-k2-0905-preview",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
}

for option in headers_options:
    print(f"\n--- Testing: {option['name']} ---")
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers=option['headers'],
            json=data,
            timeout=30.0
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"SUCCESS! Response: {response.text[:200]}")
            # printsuccess headers config
            print(f"\nWorking headers: {option['headers']}")
            break
        else:
            result = response.json()
            print(f"Error: {result.get('error', {}).get('message', 'Unknown')}")
    except Exception as e:
        print(f"Error: {e}")
