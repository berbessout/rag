from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from typing import Literal

# These functions are designed to be used in LangGraph workflows

def should_continue(state) -> Literal["tools", "final"]:
    """
    Determines whether to call tools or proceed to finalization.
    """
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return "final"


def call_model(state, model):
    """
    Calls the main model which can decide to use RAG tools.
    """
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}


def call_final_model(state, final_model):
    """
    Finalizes the response by polishing the result or converting ToolMessages.
    """
    messages = state["messages"]
    last_message = messages[-1]

    # If it's a ToolMessage, we need to let the LLM process it
    if isinstance(last_message, ToolMessage):
        response = final_model.invoke(messages)
        return {"messages": [response]}

    # If it's already an AIMessage, polish it with the final model
    response = final_model.invoke([
        SystemMessage("Provide a clear, well-formatted response based on the conversation context."),
        HumanMessage(last_message.content)
    ])
    response.id = last_message.id  # Preserve ID for Chainlit
    return {"messages": [response]} 