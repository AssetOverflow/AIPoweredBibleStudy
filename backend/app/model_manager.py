from __future__ import annotations
import abc
import json
import logging
from typing import Dict, List, Optional, Generator, AsyncGenerator, Union, TYPE_CHECKING
import ollama
from ollama import AsyncClient
from mistralai import Mistral
from mistralai.models import UserMessage, AssistantMessage
import asyncio

if TYPE_CHECKING:
    from typing import Type
    BaseModelManager = Type['ModelManager']

logger = logging.getLogger(__name__)

class ModelManager:
    """Manages interactions with both Ollama and Mistral models."""
    
    def __init__(self, agent_library_path: str, api_key: Optional[str] = None):
        self.agent_library_path = agent_library_path
        self.load_config()
        
        # Initialize both model managers if possible
        self.ollama_manager = OllamaModelManager(agent_library_path)
        self.mistral_manager = MistralModelManager(api_key, agent_library_path) if api_key else None

    def load_config(self) -> None:
        """Load the agent library configuration."""
        try:
            with open(self.agent_library_path, 'r') as f:
                config = json.load(f)
                self.model_configs = config['model_configs']
                self.agents = {agent['name']: agent for agent in config['agents']}
        except Exception as e:
            logger.error(f"Failed to load agent library: {e}")
            raise

    def _get_model_source(self, model_name: str) -> str:
        """Determine if a model is from Ollama or Mistral based on its name."""
        if model_name in self.model_configs['ollama']:
            return 'ollama'
        elif model_name in self.model_configs['mistral']:
            return 'mistral'
        else:
            raise ValueError(f"Unknown model: {model_name}")

    def _get_manager_for_model(self, model_name: str) -> Union[OllamaModelManager, MistralModelManager]:
        """Get the appropriate model manager for the given model."""
        source = self._get_model_source(model_name)
        if source == 'ollama':
            return self.ollama_manager
        elif source == 'mistral':
            if not self.mistral_manager:
                raise ValueError("Mistral API key not provided but attempting to use Mistral model")
            return self.mistral_manager
        else:
            raise ValueError(f"Unknown model source: {source}")

    async def async_chat(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Union[Dict, AsyncGenerator]:
        """Send an asynchronous chat message to the appropriate model."""
        try:
            model = self.agents[agent_name]['model']
            manager = self._get_manager_for_model(model)
            
            response = await manager.async_chat(agent_name, messages, stream)
            
            if stream:
                async def stream_wrapper():
                    async for chunk in response:
                        if isinstance(chunk, dict) and 'message' in chunk:
                            yield chunk
                        else:
                            yield {"message": {"content": chunk}}
                return stream_wrapper()
            else:
                if isinstance(response, dict) and 'message' in response:
                    return response
                else:
                    return {"message": {"content": response}}
                    
        except Exception as e:
            logger.error(f"Error in async_chat: {e}")
            raise

    def chat(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Union[Dict, Generator]:
        """Send a synchronous chat message to the appropriate model."""
        try:
            model = self.agents[agent_name]['model']
            manager = self._get_manager_for_model(model)
            response = manager.chat(agent_name, messages, stream)
            
            if stream:
                def stream_wrapper():
                    for chunk in response:
                        if isinstance(chunk, dict) and 'message' in chunk:
                            yield chunk
                        else:
                            yield {"message": {"content": chunk}}
                return stream_wrapper()
            else:
                if isinstance(response, dict) and 'message' in response:
                    return response
                else:
                    return {"message": {"content": response}}
                    
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            raise


class OllamaModelManager:
    """Manages interactions with local Ollama models."""
    
    def __init__(self, agent_library_path: str):
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
                self.model_configs = config['model_configs']
                self.agents = {agent['name']: agent for agent in config['agents']}
        except Exception as e:
            logger.error(f"Failed to load agent library: {e}")
            raise

    def get_model_for_agent(self, agent_name: str) -> str:
        """Get the model name for a specific agent."""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")
        return self.agents[agent_name]['model']

    def get_model_config(self, model_name: str) -> Dict:
        """Get the configuration for a specific model."""
        if model_name not in self.model_configs['ollama']:
            raise ValueError(f"Unknown model: {model_name}")
        return self.model_configs['ollama'][model_name]

    def chat(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Union[Dict, Generator]:
        """Send a chat message to the specified agent's model."""
        try:
            model = self.get_model_for_agent(agent_name)
            model_config = self.get_model_config(model)
            
            response = self.client.chat(
                model=model,
                messages=messages,
                options={
                    'temperature': model_config['temperature'],
                    'top_p': model_config['top_p']
                },
                stream=stream
            )
            
            if stream:
                return response
            return response
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            raise

    async def async_chat(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Union[Dict, AsyncGenerator]:
        """Send an asynchronous chat message to the model."""
        if stream:
            return self._stream_chat(agent_name, messages)
        else:
            return await self._regular_chat(agent_name, messages)

    async def _regular_chat(self, agent_name: str, messages: List[Dict[str, str]]) -> Dict:
        """Handle regular (non-streaming) chat."""
        try:
            model = self.get_model_for_agent(agent_name)
            model_config = self.get_model_config(model)
            
            response = await self.async_client.chat(
                model=model,
                messages=messages,
                options={
                    'temperature': model_config['temperature'],
                    'top_p': model_config['top_p']
                },
                stream=False
            )
            return response
            
        except Exception as e:
            logger.error(f"Error in async chat: {e}")
            raise

    async def _stream_chat(self, agent_name: str, messages: List[Dict[str, str]]) -> AsyncGenerator:
        """Handle streaming chat."""
        try:
            model = self.get_model_for_agent(agent_name)
            model_config = self.get_model_config(model)
            
            # First await the chat() call to get the async generator
            stream_response = await self.async_client.chat(
                model=model,
                messages=messages,
                options={
                    'temperature': model_config['temperature'],
                    'top_p': model_config['top_p']
                },
                stream=True
            )
            
            # Then use async for on the async generator
            async for chunk in stream_response:
                yield chunk
                
        except Exception as e:
            logger.error(f"Error in async chat: {e}")
            raise

    def ensure_models_available(self) -> None:
        """Ensure all required models are available locally."""
        # Get list of models used by agents configured for Ollama
        ollama_models = set()
        for agent_name, agent in self.agents.items():
            model_name = agent['model']
            # Only check Ollama models (those that don't start with 'mistral-' or 'ministral-')
            if model_name in self.model_configs['ollama']:
                ollama_models.add(model_name)
        
        for model_name in ollama_models:
            try:
                self.client.show(model_name)
            except ollama.ResponseError as e:
                if e.status_code == 404:
                    try:
                        self.client.pull(model_name)
                    except Exception as pull_error:
                        logger.error(f"Failed to pull model {model_name}: {pull_error}")
                        # Try pulling without the version tag
                        base_model = model_name.split(':')[0]
                        self.client.pull(base_model)
                else:
                    raise


class MistralModelManager:
    """Manages interactions with Mistral API models."""
    
    AVAILABLE_MODELS = [
        "mistral-small-2409",  # Current version of mistral-small-latest
        "mistral-large-2411",  # Current version of mistral-large-latest
        "open-mistral-nemo",   # Research model
        "open-mixtral-8x7b",   # Legacy model
        "ministral-8b-2410",   # Edge model
        "ministral-3b-2410"    # Edge model
    ]
    
    def __init__(self, api_key: str, agent_library_path: str):
        self.client = Mistral(api_key=api_key)
        self.agent_library_path = agent_library_path
        self.load_config()
        self.ensure_models_available()

    def load_config(self) -> None:
        """Load the agent library configuration."""
        try:
            with open(self.agent_library_path, 'r') as f:
                config = json.load(f)
                self.model_configs = config['model_configs']['mistral']
                self.agents = {agent['name']: agent for agent in config['agents']}
        except Exception as e:
            logger.error(f"Failed to load agent library: {e}")
            raise

    def ensure_models_available(self) -> None:
        """Verify that configured models are available through Mistral API."""
        mistral_models = set()
        for agent_name, agent in self.agents.items():
            model_name = agent['model']
            if model_name in self.model_configs:
                if model_name not in self.AVAILABLE_MODELS:
                    raise ValueError(f"Model {model_name} is not available in Mistral API")
                mistral_models.add(model_name)

    def _convert_to_mistral_messages(self, messages: List[Dict[str, str]]) -> List[Union[UserMessage, AssistantMessage]]:
        """Convert messages to Mistral format."""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                # Prepend system message to user's first message
                continue
            elif msg["role"] == "user":
                if chat_messages and isinstance(chat_messages[-1], UserMessage):
                    # Combine consecutive user messages
                    chat_messages[-1].content += "\n" + msg["content"]
                else:
                    # Add system message to first user message if present
                    content = msg["content"]
                    if messages[0]["role"] == "system":
                        content = f"{messages[0]['content']}\n\nUser: {content}"
                    chat_messages.append(UserMessage(content=content))
            else:
                chat_messages.append(AssistantMessage(content=msg["content"]))
        return chat_messages

    async def async_chat(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Union[Dict, AsyncGenerator]:
        """Send an asynchronous chat message using Mistral API."""
        try:
            model = self.agents[agent_name]['model']
            if model not in self.model_configs:
                raise ValueError(f"Unknown model: {model}")
            
            config = self.model_configs[model]
            chat_messages = self._convert_to_mistral_messages(messages)
            
            if stream:
                async def stream_generator():
                    response = await self.client.chat.stream_async(
                        model=model,
                        messages=chat_messages,
                        temperature=config['temperature'],
                        top_p=config['top_p']
                    )
                    async for chunk in response:
                        if chunk.data.choices[0].delta.content is not None:
                            yield {"message": {"content": chunk.data.choices[0].delta.content}}
                
                return stream_generator()
            else:
                response = await self.client.chat.async_chat(
                    model=model,
                    messages=chat_messages,
                    temperature=config['temperature'],
                    top_p=config['top_p']
                )
                return {"message": {"content": response.choices[0].message.content}}
            
        except Exception as e:
            logger.error(f"Error in Mistral async chat: {e}")
            raise

    def chat(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> Dict:
        """Send a synchronous chat message using Mistral API."""
        try:
            model = self.agents[agent_name]['model']
            if model not in self.model_configs:
                raise ValueError(f"Unknown model: {model}")
            
            config = self.model_configs[model]
            chat_messages = self._convert_to_mistral_messages(messages)
            
            if stream:
                response = self.client.chat.stream(
                    model=model,
                    messages=chat_messages,
                    temperature=config['temperature'],
                    top_p=config['top_p']
                )
                return ({"message": {"content": chunk.data.choices[0].delta.content}} 
                        for chunk in response 
                        if chunk.data.choices[0].delta.content is not None)
            else:
                response = self.client.chat(
                    model=model,
                    messages=chat_messages,
                    temperature=config['temperature'],
                    top_p=config['top_p']
                )
                return {"message": {"content": response.choices[0].message.content}}
            
        except Exception as e:
            logger.error(f"Error in Mistral chat: {e}")
            raise

def create_model_manager(config_type: str, agent_library_path: str, api_key: Optional[str] = None) -> ModelManager:
    """Factory function to create appropriate model manager."""
    if config_type.lower() == "ollama":
        return OllamaModelManager(agent_library_path)
    elif config_type.lower() == "mistral":
        if not api_key:
            raise ValueError("Mistral API key is required for Mistral model manager")
        return MistralModelManager(api_key, agent_library_path)
    else:
        raise ValueError(f"Unknown model manager type: {config_type}")