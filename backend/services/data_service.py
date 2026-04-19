"""
Data Service — Thin wrapper around MCP tools (core_tools_v2).

No SQL is written here. All queries go through the MCP Server's registered tools,
ensuring a single source of truth for data logic.

For Dashboard use, tools are called with format="json" to receive structured data.
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional

from mcp_app.client import MCPClient
from mcp_app.config import load_config
from mcp_app.logger import get_logger

logger = get_logger("data_service")


class DataService:
    """
    Lightweight data service that delegates all queries to MCP tools.
    
    Maintains a persistent MCP connection for reuse across requests.
    """
    
    def __init__(self):
        self._mcp: Optional[MCPClient] = None
        self._connected = False
    
    async def initialize(self):
        """Connect to MCP Server (stdio mode)."""
        if self._connected:
            return
        
        config = load_config()
        self._mcp = MCPClient(
            server_path=config.mcp_server_path,
            transport=config.mcp_transport,
            port=config.mcp_port,
        )
        
        ok = await self._mcp.connect()
        if not ok:
            raise RuntimeError("Failed to connect to MCP Server")
        
        await self._mcp.discover_tools()
        self._connected = True
        logger.info(f"DataService connected to MCP Server ({len(self._mcp.tools)} tools)")
    
    async def close(self):
        """Close MCP connection."""
        if self._mcp:
            await self._mcp.close()
            self._mcp = None
            self._connected = False
            logger.info("DataService disconnected")
    
    async def _call_tool(self, name: str, arguments: dict) -> Any:
        """Call an MCP tool and parse JSON response."""
        if not self._connected or not self._mcp:
            raise RuntimeError("MCP not connected")
        
        start = time.time()
        result_text = await self._mcp.call_tool(name, arguments)
        elapsed_ms = round((time.time() - start) * 1000, 2)
        
        # Try to parse as JSON (format="json" returns JSON string)
        try:
            data = json.loads(result_text)
            if isinstance(data, dict):
                data["_elapsed_ms"] = elapsed_ms
            return data
        except json.JSONDecodeError:
            # Fallback: return raw text wrapped in dict
            return {"_raw": result_text, "_elapsed_ms": elapsed_ms}
    
    # ========================================================================
    # Dashboard APIs (format="json" for structured data)
    # ========================================================================
    
    async def get_dashboard(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Call get_dashboard tool with JSON output."""
        return await self._call_tool("get_dashboard", {
            "start_date": start_date,
            "end_date": end_date,
            "format": "json",
        })
    
    async def get_time_series(
        self, start_date: str, end_date: str, granularity: str = "day"
    ) -> List[Dict[str, Any]]:
        """Call analyze_time_series tool with JSON output."""
        result = await self._call_tool("analyze_time_series", {
            "start_date": start_date,
            "end_date": end_date,
            "granularity": granularity,
            "format": "json",
        })
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "_raw" in result:
            raise RuntimeError(f"Time series tool returned text: {result['_raw'][:200]}")
        return []
    
    async def get_geo_heatmap(
        self, start_date: str, end_date: str, precision: int = 2
    ) -> List[Dict[str, Any]]:
        """Call get_geo_heatmap tool with JSON output."""
        result = await self._call_tool("get_geo_heatmap", {
            "start_date": start_date,
            "end_date": end_date,
            "precision": precision,
            "format": "json",
        })
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "_raw" in result:
            raise RuntimeError(f"Geo heatmap tool returned text: {result['_raw'][:200]}")
        return []
    
    async def search_events(
        self, query: str, time_hint: Optional[str] = None,
        location_hint: Optional[str] = None, event_type: Optional[str] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """Call search_events tool with JSON output."""
        result = await self._call_tool("search_events", {
            "query": query,
            "time_hint": time_hint,
            "location_hint": location_hint,
            "event_type": event_type or "any",
            "max_results": min(max_results, 50),
            "format": "json",
        })
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        if isinstance(result, list):
            return result
        return []
    
    # ========================================================================
    # Health / Stats
    # ========================================================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Return placeholder stats (MCP handles caching internally)."""
        return {"mode": "mcp", "note": "Caching handled by MCP Server"}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MCP connection health."""
        if not self._connected:
            return {"status": "unhealthy", "error": "MCP not connected"}
        try:
            start = time.time()
            # Lightweight ping via search_events with tiny limit
            await self._call_tool("search_events", {
                "query": "test", "max_results": 1, "format": "json"
            })
            latency_ms = round((time.time() - start) * 1000, 2)
            return {"status": "healthy", "latency_ms": latency_ms}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
data_service = DataService()
