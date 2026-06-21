import os
import uuid
from langchain_core.messages import AIMessage, HumanMessage

from agent import validate_config, create_agent, get_langfuse_callback, DEFAULT_GREETING


def get_message_content(message) -> str:
    """Extracts text content from a LangChain message, handling both string and list content types."""
    content = message.content
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
        return "".join(text_parts)
    return str(content)


def run_interactive():
    """Runs a live interactive chat session with the AI agent in the terminal."""
    print("\n" + "="*50)
    print("   JACOBS PLUMBING - INTERACTIVE CALL ASSISTANT   ")
    print("="*50)
    print("Type 'exit', 'quit', or 'bye' to end the call.\n")
    
    agent_graph = create_agent()
    chat_history = []
    
    # Check Langfuse integration
    langfuse_handler = get_langfuse_callback()
    
    # Generate unique trace and session ID for Langfuse production tracing
    session_id = f"sess_{uuid.uuid4().hex[:8].upper()}"
    callbacks = []
    if langfuse_handler:
        print(f"[INFO] Langfuse tracing is active. Session ID: {session_id}")
        callbacks.append(langfuse_handler)
    
    # Config including thread_id for LangGraph checkpointers and callbacks
    graph_config = {
        "configurable": {"thread_id": session_id},
        "callbacks": callbacks,
        "run_name": "jacobs_plumbing_interactive_call",
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_user_id": "interactive_caller"
        }
    }
    
    # The agent starts the greeting according to our conversation flow (DRY greeting constant)
    print(f"\nAI: {DEFAULT_GREETING}")
    chat_history.append(AIMessage(content=DEFAULT_GREETING))
    
    # Initialize the checkpointer state with the greeting
    agent_graph.update_state(
        graph_config,
        {"messages": [AIMessage(content=DEFAULT_GREETING)]}
    )
    
    while True:
        try:
            user_input = input("Caller: ")
            if user_input.strip().lower() in ["exit", "quit", "bye"]:
                print("AI: Thank you for calling Jacobs Plumbing. Have a great day!")
                break
                
            if not user_input.strip():
                continue
                
            # Invoke the LangGraph React Agent with only the new message (history is managed by the Checkpointer)
            response = agent_graph.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=graph_config
            )
            
            ai_output = get_message_content(response["messages"][-1])
            print(f"AI: {ai_output}\n")
            
            # Update history for local tracking
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=ai_output))
            
        except KeyboardInterrupt:
            print("\nAI: Thank you for calling Jacobs Plumbing. Have a great day!")
            break
        except Exception as e:
            print(f"\n[ERROR] An error occurred: {e}\n")
            
    # Flush Langfuse traces on end of session
    if langfuse_handler:
        print("[INFO] Flushing Langfuse traces...")
        if hasattr(langfuse_handler, "langfuse"):
            langfuse_handler.langfuse.flush()
        elif hasattr(langfuse_handler, "flush"):
            langfuse_handler.flush()


if __name__ == "__main__":
    # Validate environment configuration
    validate_config()
    run_interactive()
