import asyncio
import logging
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from bs_logging.logging_setup import setup_logging
from rate_limiter import RateLimiter
from agent_manager import AgentManager
from model_manager import ModelManager
from agent import load_agent_library
from chat_state import ChatState
from routers import chat, health, agents


# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)    

# Initialize FastAPI app
app = FastAPI(
    title="Divine Haven Bible Study",
    description="AI-powered Bible study application with multi-agent support",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize shared resources
rate_limit_tokens = int(os.getenv("RATE_LIMIT_TOKENS", "100000"))
rate_limiter = RateLimiter(tokens_per_minute=rate_limit_tokens)

# Initialize agent and model managers
agent_library_path = os.getenv("AGENT_LIBRARY_PATH", "agent_library_example.json")
agent_library = load_agent_library(agent_library_path)
api_key = os.getenv("MISTRAL_API_KEY")
model_manager = ModelManager(agent_library_path, api_key)

# Initialize agent manager
agent_manager = AgentManager(agent_library, rate_limiter, agent_library_path)
agent_manager.set_response_token_limit(500)

chat_state = ChatState()

# Pass dependencies to routers
chat.agent_manager = agent_manager
agents.agent_manager = agent_manager
agents.model_manager = model_manager

# Include routers
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])

# Request/response models
class ChatRequest(BaseModel):
    message: str
    stream: bool = False
    tokens: int = None  # Optional token limit override

class ChatResponse(BaseModel):
    response: str

# API endpoints
@app.get("/")
async def root():
    """Health check or welcome endpoint."""
    return {"message": "Welcome to the Bible Study Chat API!"}

@app.post("/chat/", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Handle a chat message.
    - If `stream` is True, a streamed response is simulated via background tasks.
    - Otherwise, a normal response is returned.
    """
    try:
        # Override token limit if provided
        if request.tokens is not None:
            agent_manager.set_response_token_limit(request.tokens)

        if request.stream:
            # Use background task to simulate streaming
            background_tasks.add_task(stream_response, request.message)
            return {"response": "Streaming response initiated. Check logs for output."}

        # Non-streaming response
        response = await agent_manager.handle_message_async(request.message, chat_state)
        return {"response": response}

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while processing your request.")

async def stream_response(message: str):
    """
    Simulate streaming a response for a message.
    Logs each chunk of the response.
    """
    try:
        response_stream = await agent_manager.handle_message_async(message, chat_state, stream=True)
        if hasattr(response_stream, '__aiter__'):
            async for chunk in response_stream:
                if isinstance(chunk, dict) and 'message' in chunk:
                    logger.info(chunk['message']['content'])
                else:
                    logger.info(chunk)
    except Exception as e:
        logger.error(f"Streaming error: {e}")

# CLI functionality remains for dual-use
async def main_async():
    """CLI entry point for the Bible Study Chat."""
    logger.info("Starting Bible Study Chat (CLI)...")
    print("Welcome to the Bible Study Chat!")
    print("Type 'exit' or 'quit' to end the session.")

    stream_mode = False

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ['exit', 'quit']:
                print("Exiting chat. Goodbye!")
                break
            elif user_input.lower() == 'stream':
                stream_mode = not stream_mode
                print(f"Streaming mode {'enabled' if stream_mode else 'disabled'}")
                continue

            if stream_mode:
                await stream_response(user_input)
            else:
                response = await agent_manager.handle_message_async(user_input, chat_state)
                print(response)

        except KeyboardInterrupt:
            print("\nExiting chat. Goodbye!")
            break
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            print("An error occurred. Please try again.")

def main():
    """Synchronous entry point that runs the async main."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nExiting chat. Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print("A fatal error occurred. Please check the logs.")

if __name__ == "__main__":
    # Set log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logging(log_level)

    if os.getenv("RUN_MODE", "cli") == "api":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        main()