import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from agent.tools import tools_list
from agent import config

def load_system_prompt() -> str:
    """Loads the system prompt from Langfuse if available, otherwise falls back to a local file."""
    # Attempt to load from Langfuse if credentials are set
    if config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY:
        try:
            from langfuse import Langfuse
            langfuse = Langfuse(
                public_key=config.LANGFUSE_PUBLIC_KEY,
                secret_key=config.LANGFUSE_SECRET_KEY,
                host=config.LANGFUSE_HOST
            )
            print("[INFO] Attempting to fetch system prompt from Langfuse...")
            langfuse_prompt = langfuse.get_prompt("jacobs-plumbing-assistant")
            return langfuse_prompt.compile()
        except Exception as e:
            print(f"[WARNING] Could not fetch prompt from Langfuse: {e}. Falling back to local file.")
            
    # Local file fallback
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_path = os.path.join(base_dir, "prompts", "system_prompt.txt")
    
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] Could not load system_prompt.txt locally: {e}")
        # Default safety fallback prompt
        return (
            "You are a polite virtual assistant for Jacobs Plumbing. "
            "Help callers schedule bookings. Ask for name, address, phone number, and service type."
        )


def get_langfuse_callback():
    """Initializes and returns the Langfuse callback handler if configured."""
    if config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY:
        try:
            from langfuse.langchain import CallbackHandler
            return CallbackHandler()
        except Exception as e:
            print(f"[WARNING] Failed to initialize Langfuse CallbackHandler: {e}")
    return None


def create_agent():
    """Creates and returns the LangGraph compiled react agent graph configured with Google Gemini and tools."""
    # 1. Load system prompt (Langfuse or local)
    system_prompt = load_system_prompt()
    
    # 2. Initialize Google Gemini model
    llm = ChatGoogleGenerativeAI(
        model=config.MODEL_NAME,
        temperature=config.TEMPERATURE,
        google_api_key=config.GOOGLE_API_KEY
    )
    
    # 3. Create the agent using langgraph.prebuilt.create_react_agent with MemorySaver checkpointer
    memory = MemorySaver()
    agent_graph = create_react_agent(
        model=llm,
        tools=tools_list,
        prompt=system_prompt,
        checkpointer=memory
    )
    
    return agent_graph
