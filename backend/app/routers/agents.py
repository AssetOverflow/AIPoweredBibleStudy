from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json

from backend.app.agent_manager import AgentManager
from backend.app.chat_state import ChatState
from backend.app.bs_memory.redis_short_term import RedisShortTermMemory

# Models for request/response
class AgentMessage(BaseModel):
    content: str
    timestamp: datetime = datetime.now()
    metadata: Optional[Dict] = None

class AgentInteraction(BaseModel):
    from_agent: str
    to_agent: str
    message: AgentMessage
    interaction_type: str = "direct"  # direct, broadcast, query

class AgentConfig(BaseModel):
    name: str
    role: str
    capabilities: List[str]
    memory_config: Optional[Dict] = None

# Initialize router
router = APIRouter()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.agent_subscriptions: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, agent_id: str):
        await websocket.accept()
        self.active_connections[agent_id] = websocket
        self.agent_subscriptions[agent_id] = []

    def disconnect(self, agent_id: str):
        self.active_connections.pop(agent_id, None)
        self.agent_subscriptions.pop(agent_id, None)

    async def broadcast_to_subscribers(self, agent_id: str, message: str):
        for subscriber in self.agent_subscriptions.get(agent_id, []):
            if subscriber in self.active_connections:
                await self.active_connections[subscriber].send_text(message)

manager = ConnectionManager()

# Dependencies
def get_agent_manager():
    return AgentManager()  # Initialize with proper config

def get_redis_memory():
    return RedisShortTermMemory()  # Initialize with proper config

# WebSocket endpoint for real-time agent communication
@router.websocket("/ws/{agent_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    agent_id: str,
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    await manager.connect(websocket, agent_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Process message based on type
            if message.get("type") == "subscribe":
                target_agent = message.get("target_agent")
                if target_agent:
                    manager.agent_subscriptions[agent_id].append(target_agent)
            
            # Handle agent-to-agent communication
            elif message.get("type") == "agent_message":
                response = await agent_manager.handle_agent_message(
                    message.get("content"),
                    agent_id,
                    message.get("target_agent")
                )
                await manager.broadcast_to_subscribers(
                    agent_id,
                    json.dumps({"response": response})
                )
    except WebSocketDisconnect:
        manager.disconnect(agent_id)

# REST endpoints for agent management
@router.post("/agents", response_model=AgentConfig)
async def create_agent(
    config: AgentConfig,
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    """Create a new agent with specified configuration."""
    try:
        agent = await agent_manager.create_agent(config.dict())
        return agent
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/agents/{agent_id}/interact")
async def agent_interaction(
    agent_id: str,
    interaction: AgentInteraction,
    agent_manager: AgentManager = Depends(get_agent_manager),
    memory: RedisShortTermMemory = Depends(get_redis_memory)
):
    """Handle agent-to-agent interactions with memory persistence."""
    try:
        # Store interaction in memory
        await memory.store_interaction(
            agent_id,
            interaction.to_agent,
            interaction.message.dict()
        )
        
        # Process interaction
        response = await agent_manager.handle_agent_interaction(
            agent_id,
            interaction.dict()
        )
        
        # Broadcast to websocket subscribers if any
        await manager.broadcast_to_subscribers(
            agent_id,
            json.dumps({
                "type": "interaction",
                "data": response
            })
        )
        
        return JSONResponse(content=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agents/{agent_id}/memory")
async def get_agent_memory(
    agent_id: str,
    memory: RedisShortTermMemory = Depends(get_redis_memory)
):
    """Retrieve agent's memory and interaction history."""
    try:
        memory_data = await memory.get_agent_memory(agent_id)
        return JSONResponse(content=memory_data)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/agents/{agent_id}/broadcast")
async def broadcast_message(
    agent_id: str,
    message: AgentMessage,
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    """Broadcast a message to all subscribed agents."""
    try:
        await manager.broadcast_to_subscribers(
            agent_id,
            json.dumps({
                "type": "broadcast",
                "from": agent_id,
                "message": message.dict()
            })
        )
        return {"status": "broadcast sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))