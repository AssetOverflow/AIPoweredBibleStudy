import json
import logging
from typing import Dict, List, Optional, Generator, AsyncGenerator, Union
import ollama
from ollama import AsyncClient

logger = logging.getLogger(__name__)

class OllamaManager:
    """Manages interactions with local Ollama models for Bible study agents."""
    
    def __init__(self, agent_library_path: str):
        """Initialize the Ollama Manager with agent library configuration."""
        self.agent_library_path = agent_library_path
        self.load_config()
        self.client = ollama.Client(host='http://localhost:11434')
        self.async_client = AsyncClient(host='http://localhost:11434')
        self.ensure_models_available()

    def load_config(self) -> None:
        """Load the agent library configuration."""
        try:
            with open(self.agent_library_path, 'r') as f:
                config = json.load(f)
                self.model_configs = config['model_configs']['ollama']
                self.agents = {agent['name']: agent for agent in config['agents']}
        except Exception as e:
            logger.error(f"Failed to load agent library: {e}")
            raise

    def get_model_for_agent(self, agent_name: str) -> str:
        """Get the appropriate model name for a specific agent."""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")
        return self.agents[agent_name]['model']

    def get_model_config(self, model_name: str) -> Dict:
        """Get the configuration for a specific model."""
        if model_name not in self.model_configs:
            raise ValueError(f"Unknown model: {model_name}")
        return self.model_configs[model_name]

    def chat(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Dict:
        """Send a chat message to the specified agent's model."""
        try:
            model = self.get_model_for_agent(agent_name)
            model_config = self.get_model_config(model)
            logger.info(f"Using {model} for agent {agent_name}")
            
            if stream:
                return self._stream_chat(model, messages, model_config)
            else:
                return self._regular_chat(model, messages, model_config)
        except Exception as e:
            logger.error(f"Chat error for agent {agent_name}: {e}")
            raise

    def _regular_chat(self, model: str, messages: List[Dict[str, str]], config: Dict) -> Dict:
        """Send a regular (non-streaming) chat message."""
        try:
            response = self.client.chat(
                model=model,
                messages=messages,
                options={
                    'temperature': config['temperature'],
                    'top_p': config['top_p']
                }
            )
            return response
        except ollama.ResponseError as e:
            if e.status_code == 404:
                logger.warning(f"Model {model} not found. Attempting to pull...")
                self.client.pull(model)
                return self._regular_chat(model, messages, config)
            raise

    def _stream_chat(self, model: str, messages: List[Dict[str, str]], config: Dict) -> Generator:
        """Send a streaming chat message."""
        try:
            stream = self.client.chat(
                model=model,
                messages=messages,
                stream=True,
                options={
                    'temperature': config['temperature'],
                    'top_p': config['top_p']
                }
            )
            for chunk in stream:
                if 'message' in chunk:
                    yield chunk['message']
                else:
                    yield {"content": chunk.get('content', '')}
        except ollama.ResponseError as e:
            if e.status_code == 404:
                logger.warning(f"Model {model} not found. Attempting to pull...")
                self.client.pull(model)
                yield from self._stream_chat(model, messages, config)
            raise

    async def _stream_chat_async(self, model: str, messages: List[Dict[str, str]], config: Dict) -> AsyncGenerator:
        """Send a streaming chat message asynchronously."""
        try:
            async for chunk in await self.async_client.chat(
                model=model,
                messages=messages,
                stream=True,
                options={
                    'temperature': config['temperature'],
                    'top_p': config['top_p']
                }
            ):
                if 'message' in chunk:
                    yield chunk['message']
                else:
                    yield {"content": chunk.get('content', '')}
        except ollama.ResponseError as e:
            if e.status_code == 404:
                logger.warning(f"Model {model} not found. Attempting to pull...")
                await self.async_client.pull(model)
                async for chunk in self._stream_chat_async(model, messages, config):
                    yield chunk
            raise

    async def async_chat(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Union[Dict, AsyncGenerator]:
        """Send an asynchronous chat message."""
        try:
            model = self.get_model_for_agent(agent_name)
            model_config = self.get_model_config(model)
            logger.debug(f"Using {model} for async chat with agent {agent_name}")
            logger.debug(f"Stream mode: {stream}")
            
            if stream:
                logger.debug("Starting streaming response")
                async def stream_wrapper():
                    try:
                        stream_response = await self.async_client.chat(
                            model=model,
                            messages=messages,
                            stream=True,
                            options={
                                'temperature': model_config['temperature'],
                                'top_p': model_config['top_p']
                            }
                        )
                        logger.debug(f"Got stream_response type: {type(stream_response)}")
                        
                        if hasattr(stream_response, '__aiter__'):
                            logger.debug("stream_response is async iterable")
                            async for chunk in stream_response:
                                logger.debug(f"Raw Ollama chunk: {chunk}")
                                yield chunk
                        else:
                            logger.error(f"stream_response is not async iterable: {stream_response}")
                            raise TypeError("Expected async iterable from Ollama streaming response")
                            
                    except Exception as e:
                        logger.error(f"Error in Ollama stream wrapper: {e}")
                        raise
                        
                logger.debug("Returning stream wrapper")
                return stream_wrapper()
            else:
                logger.debug("Starting non-streaming response")
                response = await self.async_client.chat(
                    model=model,
                    messages=messages,
                    options={
                        'temperature': model_config['temperature'],
                        'top_p': model_config['top_p']
                    }
                )
                logger.debug(f"Raw Ollama response: {response}")
                return response
                    
        except Exception as e:
            logger.error(f"Async chat error for agent {agent_name}: {e}")
            raise

    def ensure_models_available(self) -> None:
        """Ensure all required models are available locally."""
        required_models = set(config['name'] for config in self.model_configs.values())
        
        for model_name in required_models:
            try:
                self.client.show(model_name)
                logger.info(f"Model {model_name} is available")
            except ollama.ResponseError as e:
                if e.status_code == 404:
                    logger.info(f"Pulling model {model_name}...")
                    self.client.pull(model_name)
                    logger.info(f"Successfully pulled model {model_name}")
                else:
                    logger.error(f"Error checking model {model_name}: {e}")
                    raise

    def get_model_info(self, model_name: str) -> Dict:
        """Get detailed information about a specific model."""
        try:
            return self.client.show(model_name)
        except ollama.ResponseError as e:
            logger.error(f"Error getting info for model {model_name}: {e}")
            raise