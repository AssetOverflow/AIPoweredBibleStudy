from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from agent_manager import AgentManager
from chat_state import ChatState

# Dependencies for the router
def get_chat_state():
    # Return or initialize the chat state
    return ChatState()

# Initialize router
router = APIRouter()

# Request/response models
class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    tokens: int = None

class ChatResponse(BaseModel):
    response: str

# AgentManager will be set from main.py
agent_manager = None

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    chat_state: ChatState = Depends(get_chat_state)
):
    """Handle a chat message."""
    try:
        if request.stream:
            # Handle streaming response
            response_stream = await agent_manager.handle_message_async(
                request.message,
                chat_state,
                stream=True,
                max_tokens=request.tokens
            )
            background_tasks.add_task(stream_response, response_stream, chat_state)
            return ChatResponse(response="Streaming started")
        else:
            # Handle normal response
            response = await agent_manager.handle_message_async(
                request.message,
                chat_state,
                max_tokens=request.tokens
            )
            return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def stream_response(response_stream, chat_state: ChatState):
    """Stream a response."""
    try:
        if hasattr(response_stream, '__aiter__'):
            async for chunk in response_stream:
                if isinstance(chunk, dict) and 'message' in chunk:
                    print(chunk['message']['content'], end="", flush=True)
                else:
                    print(chunk, end="", flush=True)
            print()  # Add final newline
    except Exception as e:
        print(f"Error in stream_response: {e}")