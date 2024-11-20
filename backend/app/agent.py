import json
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Agent:
    """Represents an agent with a name, system message, and model."""
    name: str
    system_message: str
    description: str
    model: str

def load_agent_library(file_path: str) -> List[Agent]:
    """Loads agent library data from a JSON file."""
    with open(file_path, "r") as f:
        data = json.load(f)
    
    if not isinstance(data, dict) or 'agents' not in data:
        raise ValueError("Invalid agent library format. Expected a dictionary with 'agents' key.")
    
    return [
        Agent(
            name=agent["name"],
            system_message=agent["system_message"],
            description=agent["description"],
            model=agent["model"]
        ) 
        for agent in data["agents"]
    ]