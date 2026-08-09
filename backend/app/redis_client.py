import os
import json
import asyncio
from typing import Optional, Dict, Any

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis_client = None
_local_memory_fallback: Dict[str, Any] = {}

async def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
        
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await client.ping()
        print(f"Redis: Connected to {REDIS_URL}")
        _redis_client = client
        return _redis_client
    except Exception as e:
        print(f"Redis: Connection failed ({e}). Using in-memory fallback cache.")
        _redis_client = None
        return None

async def save_session_state(call_id: str, data: Dict[str, Any], ttl_seconds: int = 3600):
    client = await get_redis_client()
    json_val = json.dumps(data)
    
    if client:
        try:
            await client.setex(f"session:{call_id}", ttl_seconds, json_val)
            return
        except Exception as e:
            print(f"Redis setex error: {e}")
            
    _local_memory_fallback[f"session:{call_id}"] = json_val

async def load_session_state(call_id: str) -> Optional[Dict[str, Any]]:
    client = await get_redis_client()
    
    if client:
        try:
            val = await client.get(f"session:{call_id}")
            if val:
                return json.loads(val)
        except Exception as e:
            print(f"Redis get error: {e}")
            
    val = _local_memory_fallback.get(f"session:{call_id}")
    return json.loads(val) if val else None

async def remove_session_state(call_id: str):
    client = await get_redis_client()
    
    if client:
        try:
            await client.delete(f"session:{call_id}")
        except Exception as e:
            print(f"Redis delete error: {e}")
            
    _local_memory_fallback.pop(f"session:{call_id}", None)

async def publish_call_event(channel: str, message: Dict[str, Any]):
    client = await get_redis_client()
    json_val = json.dumps(message)
    
    if client:
        try:
            await client.publish(channel, json_val)
        except Exception as e:
            print(f"Redis publish error: {e}")
