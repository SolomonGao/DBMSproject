"""MCP Client pool for connection management."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from gdelt_api.config import Settings
from gdelt_api.core.logging import get_logger
from gdelt_api.mcp.client import MCPClient

logger = get_logger(__name__)


class MCPPool:
    """Pool of MCP client connections."""
    
    def __init__(
        self,
        settings: Settings,
        pool_size: int = 3,
    ) -> None:
        self.settings = settings
        self.pool_size = pool_size
        self._clients: list[MCPClient] = []
        self._semaphore: asyncio.Semaphore | None = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the pool with connections."""
        if self._initialized:
            return
        
        logger.info("initializing_mcp_pool", size=self.pool_size)
        
        self._semaphore = asyncio.Semaphore(self.pool_size)
        
        # Create and connect clients
        for i in range(self.pool_size):
            client = MCPClient(self.settings)
            try:
                await client.connect()
                self._clients.append(client)
                logger.debug("mcp_client_created", index=i)
            except Exception as e:
                logger.error("failed_to_create_client", index=i, error=str(e))
                # Continue with partial pool
        
        if not self._clients:
            raise RuntimeError("Failed to create any MCP clients")
        
        self._initialized = True
        logger.info("mcp_pool_initialized", active_clients=len(self._clients))
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[MCPClient, None]:
        """Acquire a client from the pool."""
        if not self._initialized:
            raise RuntimeError("Pool not initialized")
        
        if self._semaphore is None:
            raise RuntimeError("Pool not initialized")
        
        async with self._semaphore:
            # Simple round-robin
            client = self._clients.pop(0)
            self._clients.append(client)
            
            try:
                yield client
            except Exception:
                # If client failed, try to reconnect
                try:
                    await client.close()
                    await client.connect()
                except Exception as e:
                    logger.error("client_reconnect_failed", error=str(e))
                raise
    
    async def close(self) -> None:
        """Close all clients in the pool."""
        logger.info("closing_mcp_pool")
        
        for i, client in enumerate(self._clients):
            try:
                await client.close()
                logger.debug("client_closed", index=i)
            except Exception as e:
                logger.error("failed_to_close_client", index=i, error=str(e))
        
        self._clients = []
        self._initialized = False
        logger.info("mcp_pool_closed")
