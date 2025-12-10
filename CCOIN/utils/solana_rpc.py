import asyncio
import structlog
from typing import Optional, List, Any
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed, Finalized
from CCOIN.config import (
    SOLANA_RPC, 
    SOLANA_RPC_FALLBACK_1, 
    SOLANA_RPC_FALLBACK_2,
    RPC_MAX_RETRIES,
    RPC_RETRY_DELAY,
    RPC_TIMEOUT
)

logger = structlog.get_logger(__name__)

class SolanaRPCClient:
    """Solana RPC client with fallback and retry logic"""
    
    def __init__(self):
        self.endpoints = [
            SOLANA_RPC,
            SOLANA_RPC_FALLBACK_1,
            SOLANA_RPC_FALLBACK_2
        ]
        self.endpoints = [ep for ep in self.endpoints if ep and ep.strip()]
        self.current_endpoint_index = 0
        
    async def _execute_with_retry(self, func, *args, **kwargs):
        """Execute RPC call with retry logic across multiple endpoints"""
        last_error = None
        
        for attempt in range(RPC_MAX_RETRIES):
            for endpoint_idx, endpoint in enumerate(self.endpoints):
                try:
                    client = AsyncClient(endpoint, timeout=RPC_TIMEOUT)
                    logger.info(
                        "Attempting RPC call",
                        endpoint=endpoint,
                        attempt=attempt + 1,
                        function=func.__name__
                    )
                    
                    result = await func(client, *args, **kwargs)
                    await client.close()
                    
                    logger.info(
                        "RPC call successful",
                        endpoint=endpoint,
                        function=func.__name__
                    )
                    return result
                    
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "RPC call failed",
                        endpoint=endpoint,
                        error=str(e),
                        attempt=attempt + 1,
                        function=func.__name__
                    )
                    try:
                        await client.close()
                    except:
                        pass
                    
                    continue
            
            if attempt < RPC_MAX_RETRIES - 1:
                await asyncio.sleep(RPC_RETRY_DELAY * (attempt + 1))
        
        logger.error(
            "All RPC attempts failed",
            last_error=str(last_error),
            function=func.__name__
        )
        raise Exception(f"All RPC endpoints failed: {str(last_error)}")
    
    async def get_transaction(self, signature: str, encoding: str = "jsonParsed", max_supported_transaction_version: int = 0):
        """Get transaction with retry logic"""
        async def _get_tx(client, sig, enc, max_ver):
            return await client.get_transaction(sig, encoding=enc, max_supported_transaction_version=max_ver)
        
        return await self._execute_with_retry(_get_tx, signature, encoding, max_supported_transaction_version)
    
    async def get_signatures_for_address(self, pubkey, limit: int = 100):
        """Get signatures for address with retry logic"""
        async def _get_sigs(client, pk, lim):
            return await client.get_signatures_for_address(pk, limit=lim)
        
        return await self._execute_with_retry(_get_sigs, pubkey, limit)
    
    async def get_latest_blockhash(self, commitment=Finalized):
        """Get latest blockhash with retry logic"""
        async def _get_blockhash(client, comm):
            return await client.get_latest_blockhash(commitment=comm)
        
        return await self._execute_with_retry(_get_blockhash, commitment)

rpc_client = SolanaRPCClient()
