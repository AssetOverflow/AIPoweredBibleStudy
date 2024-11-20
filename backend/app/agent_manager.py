import logging
from typing import List, Dict, Optional, Union, AsyncGenerator
from agent import Agent
from rate_limiter import RateLimiter
from chat_state import ChatState
from model_manager import create_model_manager

logger = logging.getLogger(__name__)

class AgentManager:
    """Manages interactions between the Master Agent and delegated agents."""
    def __init__(self, agent_library: List[Agent], rate_limiter: RateLimiter, agent_library_path: str, model_type: str = "ollama", api_key: Optional[str] = None):
        self.agent_library = agent_library
        self.rate_limiter = rate_limiter
        self.model_manager = create_model_manager(model_type, agent_library_path, api_key)
        self.response_token_limit = 500  # Default token limit for responses

    def set_response_token_limit(self, limit: int):
        """Set the token limit for agent responses."""
        self.response_token_limit = limit

    def generate_response(self, agent_name: str, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Generates a response from the given messages using the appropriate model."""
        tokens_used = sum(len(msg['content']) for msg in messages) // 4
        self.rate_limiter.check(tokens_used)

        response = self.model_manager.chat(agent_name, messages, stream=stream)
        
        if stream:
            full_response = ""
            for chunk in response:
                full_response += chunk['message']['content']
            response_content = full_response
        else:
            response_content = response['message']['content']
            
        response_tokens = len(response_content) // 4
        self.rate_limiter.check(response_tokens)

        return response_content

    def delegate(self, user_message: str, agents_to_delegate: List[Agent]) -> str:
        """Handles delegation to specific agents."""
        aggregated_responses = []

        for agent in agents_to_delegate:
            logger.info(f"Delegating to {agent.name}...")
            agent_prompt = [
                {"role": "system", "content": agent.system_message},
                {"role": "user", "content": user_message},
            ]
            agent_response = self.generate_response(agent.name, agent_prompt)
            aggregated_responses.append(f"**{agent.name}**: {agent_response}")

        return "\n\n".join(aggregated_responses)

    async def delegate_async(self, user_message: str, agents_to_delegate: List[Agent], stream: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        """Handles delegation to specific agents asynchronously."""
        if not stream:
            return await self._delegate_non_streaming(user_message, agents_to_delegate)
        else:
            return self._delegate_streaming(user_message, agents_to_delegate)

    async def _delegate_streaming(self, user_message: str, agents_to_delegate: List[Agent]) -> AsyncGenerator[str, None]:
        """Handle streaming delegation."""
        async def generate():
            for agent in agents_to_delegate:
                logger.info(f"Delegating to {agent.name}...")
                agent_prompt = [
                    {"role": "system", "content": f"{agent.system_message}\n\nIMPORTANT: Please provide a concise response within approximately {self.response_token_limit} tokens. Focus on the most relevant information while maintaining clarity and completeness."},
                    {"role": "user", "content": user_message},
                ]
                
                async for chunk in await self.model_manager.async_chat(agent.name, agent_prompt, stream=True):
                    if isinstance(chunk, dict) and 'message' in chunk and 'content' in chunk['message']:
                        yield chunk['message']['content']
                    elif isinstance(chunk, str):
                        yield chunk
                    
        return generate()

    async def _delegate_non_streaming(self, user_message: str, agents_to_delegate: List[Agent]) -> str:
        """Handle non-streaming delegation."""
        responses = []
        for agent in agents_to_delegate:
            logger.info(f"Delegating to {agent.name}...")
            agent_prompt = [
                {"role": "system", "content": f"{agent.system_message}\n\nIMPORTANT: Please provide a concise response within approximately {self.response_token_limit} tokens. Focus on the most relevant information while maintaining clarity and completeness."},
                {"role": "user", "content": user_message},
            ]
            response = await self.model_manager.async_chat(agent.name, agent_prompt)
            
            if isinstance(response, dict) and 'message' in response and 'content' in response['message']:
                responses.append(response['message']['content'])
            elif isinstance(response, str):
                responses.append(response)
                
        return "\n\n".join(responses)

    def handle_message(self, user_message: str, chat_state: ChatState, stream: bool = False) -> str:
        """Processes a user message and determines whether delegation is required."""
        chat_state.add_message("user", user_message)

        master_agent = next(agent for agent in self.agent_library if agent.name == "Master Agent")
        master_prompt = [
            {"role": "system", "content": master_agent.system_message + "\nIMPORTANT: Your task is ONLY to determine which specialized agents should handle this query. Do not provide an answer yourself. Instead, specify which agents to delegate to based on the query's nature."},
        ] + chat_state.chat_history

        master_response = self.generate_response("Master Agent", master_prompt, stream=False)
        logger.info("Master Agent Delegation Decision: %s", master_response)

        agents_to_delegate = self.detect_delegation_need(user_message, master_response)
        if not agents_to_delegate:
            agents_to_delegate = ["Biblical Theologian"]
            
        delegated_agents = [
            agent for agent in self.agent_library if agent.name in agents_to_delegate
        ]
        combined_response = self.delegate(user_message, delegated_agents)
        chat_state.add_message("assistant", combined_response)
        return combined_response

    async def handle_message_async(self, user_message: str, chat_state: ChatState, stream: bool = False) -> Union[str, AsyncGenerator[str, None]]:
        """Processes a user message asynchronously."""
        chat_state.add_message("user", user_message)

        master_agent = next(agent for agent in self.agent_library if agent.name == "Master Agent")
        
        master_prompt = [
            {"role": "system", "content": master_agent.system_message + "\nIMPORTANT: Analyze the user's question and determine which single agent's expertise best matches the core focus of the query. Each agent specializes in different aspects of biblical study:\n\n" + 
            "- Biblical Theologian: Core biblical interpretation, general scriptural understanding, and broad biblical knowledge\n" +
            "- Geographical Strategist: Physical aspects of the biblical world - terrain, places, regions, spatial relationships\n" +
            "- Historical Contextualizer: Events, time periods, cultural significance, historical impact and meaning\n" +
            "- Linguistic Expert: Language analysis, word studies, translation, original text interpretation\n" +
            "- Literary Analyst: Textual composition, writing techniques, narrative elements, biblical genres\n\n" +
            "Consider what aspect of biblical study the question primarily relates to, then select the ONE most appropriate agent.\n\n" +
            "Respond ONLY with the single most relevant agent name. No explanations."},
            {"role": "user", "content": user_message}
        ]

        master_response = await self.model_manager.async_chat("Master Agent", master_prompt)
        
        if isinstance(master_response, dict) and 'message' in master_response:
            agent_name = master_response['message']['content'].strip()
        else:
            agent_name = str(master_response).strip()
            
        selected_agent = next((agent for agent in self.agent_library if agent.name == agent_name), None)
        
        # Fallback to Biblical Theologian if no agent was selected or if the selected agent doesn't exist
        if not selected_agent:
            selected_agent = next((agent for agent in self.agent_library if agent.name == "Biblical Theologian"), None)
            
        selected_agents = [selected_agent] if selected_agent else []
        
        # Add token limit instruction to the agent's system message
        if selected_agent:
            token_instruction = f"\n\nIMPORTANT: Please provide a concise response within approximately {self.response_token_limit} tokens. Focus on the most relevant information while maintaining clarity and completeness."
            selected_agent.system_message += token_instruction
        
        if stream:
            return await self._delegate_streaming(user_message, selected_agents)
        else:
            response = await self._delegate_non_streaming(user_message, selected_agents)
            chat_state.add_message("assistant", response)
            return response

    def detect_delegation_need(self, user_message: str, master_response: str) -> Optional[List[str]]:
        """Determines if the query should be delegated and to which agents."""
        delegation_keywords = {
            "Biblical Theologian": ["scripture", "bible", "verse", "passage", "chapter", "testament", "doctrine", "theology", "belief", "interpretation", "meaning", "spiritual"],
            "Geographical Strategist": ["where", "location", "region", "place", "map", "geography", "land"],
            "Historical Contextualizer": ["when", "timeline", "history", "period", "era", "date", "time", "historical"],
            "Linguistic Expert": ["word", "meaning", "translation", "language", "hebrew", "greek", "aramaic"],
            "Literary Analyst": ["genre", "style", "structure", "literary", "narrative", "poetry", "metaphor"],
        }

        # Extract agent names from master response
        agents = []
        for agent in delegation_keywords.keys():
            if agent.lower() in master_response.lower():
                agents.append(agent)

        # If no specific agents were mentioned, check keywords
        if not agents:
            message = user_message.lower()
            for agent, keywords in delegation_keywords.items():
                if any(keyword in message for keyword in keywords):
                    agents.append(agent)

        return agents if agents else None