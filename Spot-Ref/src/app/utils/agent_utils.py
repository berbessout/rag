"""
Agent workflow utility functions for LangGraph/Chainlit orchestration.
"""

# Standard library imports
from typing import Literal, Any

# Third-party imports
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage  
from langgraph.graph.message import MessagesState
from src.utils.prompt_list import PROMPT_SYSTEM


def should_continue(state: MessagesState) -> Literal["tools", "final"]:
    """
    Determines whether to call tools or proceed to finalization based on the last message's tool_calls.

    Args:
        state (MessagesState): The current state containing messages.

    Returns:
        Literal["tools", "final"]: Next step in the workflow.
    """
    last = state["messages"][-1]
    return "tools" if last.tool_calls else "final"


def call_model(state: MessagesState, model: Any) -> dict:
    """
    Calls the main model and ensures the response is an AIMessage. Logs key steps.

    Args:
        state (MessagesState): The current state containing messages.
        model (Any): The model instance to invoke.

    Returns:
        dict: Dictionary with updated messages.
    """
    
    response = model.invoke(state["messages"])
    print(f"🔧 call_model tool_calls: {getattr(response, 'tool_calls', None)}")
    print(f"🔧 call_model response received: {getattr(response, 'content', '')[:50]}...")
    # Force typing in AIMessage if needed
    if not isinstance(response, AIMessage):
        response = AIMessage(content=response.content, additional_kwargs=getattr(response, "additional_kwargs", {}))
    return {"messages": [response]}


def call_final_model(state: MessagesState, final_model: Any) -> dict:
    """
    Calls the final model to polish the last AI message. Logs key steps.

    Args:
        state (MessagesState): The current state containing messages.
        final_model (Any): The final model instance to invoke.

    Returns:
        dict: Dictionary with updated messages.
    """

    real_user_messages = get_real_user_messages(state)
    last_ai = state["messages"][-1]
    response = final_model.invoke([
        SystemMessage(content=PROMPT_SYSTEM),
        real_user_messages[-1],
        HumanMessage(content=last_ai.content),
    ])
    response.id = last_ai.id
    print(f"🔧 call_final_model response received: {getattr(response, 'content', '')[:50]}...")
    return {"messages": [response]}


def get_real_user_messages(state: MessagesState):
    """
    Get the real user messages from the messages list.

    Args:
        state (MessagesState): The current state containing messages.

    Returns:
        list: The list of real user messages.   
    """
    #Real user messages are at indices where (i % 4 == 0)
    return [msg for i, msg in enumerate(state["messages"]) if isinstance(msg, HumanMessage) and i % 4 == 0]



    