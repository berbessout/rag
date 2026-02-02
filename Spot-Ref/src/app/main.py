# ================ Importing libraries ================
# Standard libraries
from typing import Dict, Any, Optional, Literal
import json
import os
import re

# Third-party libraries
import chainlit as cl
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langfuse import get_client
from langfuse.langchain import CallbackHandler

# Internal modules
from src.app.rag_architecture.metadata_based_rag import MetadataBasedRAG
from src.app.utils.agent_utils import should_continue, call_model, call_final_model

# ================ Defining variables ================
load_dotenv(override=True)
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_FINAL_MODEL_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini") 
AZURE_AGENT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o") 
QDRANT_HOST = os.environ.get("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "spot-refs-docs")
# Langfuse credentials
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")
# CHAINLIT_AUTH_SECRET = os.environ.get("CHAINLIT_AUTH_SECRET", "")

_cached_metadata_rag: MetadataBasedRAG | None = None

if LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY:
    langfuse = get_client()
    langfuse_handler = CallbackHandler()
else:
    langfuse = None
    langfuse_handler = None
    print("⚠️  Langfuse not configured – set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY in .env")

# ================ Defining tools ================

@tool
def query_docs(query: str) -> str:
    """🛠️ Recherche de documents avec métadonnées et stockage des sources"""
    global _cached_metadata_rag
    print(f"🐛 query_docs called with query: {query}")

    # Note: Tracing is handled automatically by LangGraph CallbackHandler

    if _cached_metadata_rag is None:
        print("⚙️ Initialising MetadataBasedRAG instance")
        _cached_metadata_rag = MetadataBasedRAG()

    try:
        # 4) Synthèse finale via RAG
        result = _cached_metadata_rag.search_and_synthesize(query)
        print(f"🤖 RAG synthesis result: {str(result)[:50]}...")
        
        # 3) Collect preliminary sources (all metadata hits)
        sources: Dict[str, str] = {}
        for hit in result:
            name = hit["doc_name"]
            # Prefer sharepoint_url if available, else fallback to pptx_path
            url = hit.get("sharepoint_url") or hit.get("pptx_path")
            if name and url:
                sources[name] = url
        print(f"📑 sources: {list(sources.keys())}")

        # Store filtered sources in session
        cl.user_session.set("sources", sources)
        print("💾 Stored filtered sources in user session")

        # Store the projects shown to user for future "more projects" requests
        shown_projects = cl.user_session.get("shown_projects", [])
        project_names = [hit["doc_name"] for hit in result if hit.get("doc_name")]
        shown_projects.extend(project_names)
        cl.user_session.set("shown_projects", shown_projects)
        print(f"💾 Stored shown projects: {project_names}")

        result_json = json.dumps(result, indent=2, ensure_ascii=False)
        return result_json

    except Exception as e:
        print(f"💥 [ERROR] query_docs exception: {e}")
        return f"Error: {e}"


@tool
def query_more_projects(query: str) -> str:
    """🛠️ Recherche de projets supplémentaires en excluant ceux déjà montrés"""
    global _cached_metadata_rag
    print(f"🐛 query_more_projects called with query: {query}")

    if _cached_metadata_rag is None:
        print("⚙️ Initialising MetadataBasedRAG instance")
        _cached_metadata_rag = MetadataBasedRAG()

    try:
        # Get previously shown projects
        shown_projects = cl.user_session.get("shown_projects", [])
        print(f"📝 Previously shown projects: {shown_projects}")

        # Get more results than usual to have options after filtering
        result = _cached_metadata_rag.search_and_synthesize(query, top_k=15)
        print(f"🤖 RAG synthesis result (before filtering): {len(result)} projects")

        # Filter out previously shown projects
        filtered_result = []
        for hit in result:
            if hit.get("doc_name") not in shown_projects:
                filtered_result.append(hit)
                if len(filtered_result) >= 5:  # Limit to 5 new projects
                    break

        print(f"✅ Filtered to {len(filtered_result)} new projects")

        if not filtered_result:
            return json.dumps({"message": "No more projects found that haven't been shown already."}, ensure_ascii=False)

        # Update sources and shown projects
        sources: Dict[str, str] = {}
        new_project_names = []
        for hit in filtered_result:
            name = hit["doc_name"]
            url = hit.get("sharepoint_url") or hit.get("pptx_path")
            if name and url:
                sources[name] = url
                new_project_names.append(name)

        # Update session data
        cl.user_session.set("sources", sources)
        shown_projects.extend(new_project_names)
        cl.user_session.set("shown_projects", shown_projects)
        print(f"💾 Added new projects to shown list: {new_project_names}")

        result_json = json.dumps(filtered_result, indent=2, ensure_ascii=False)
        return result_json

    except Exception as e:
        print(f"💥 [ERROR] query_more_projects exception: {e}")
        return f"Error: {e}"


def detect_more_projects_request(state: MessagesState) -> Literal["more_projects", "tools", "final"]:
    """
    Détecte si l'utilisateur demande plus de projets et route vers le noeud approprié
    """
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    # Check if the user is asking for more projects
    if isinstance(last_message, HumanMessage):
        content = last_message.content.lower()
        more_patterns = [
            r'\b(more|additional|other|different)\s+(projects?|options?)\b',
            r'\b(give|show|find)\s+me\s+(more|additional|other|different)\b',
            r'\b(what\s+about|any\s+other|anything\s+else)\b',
            r'\b(more|autres?|plus\s+de)\s+(projets?|options?)\b',  # French patterns
            r'\b(donnez?|montrez?)\s+moi\s+(plus|autres?|davantage)\b'
        ]
        
        for pattern in more_patterns:
            if re.search(pattern, content):
                print(f"🔍 Detected 'more projects' request: {content}")
                return "more_projects"
    
    return "final"


def call_more_projects_model(state: MessagesState, model) -> dict:
    """
    Calls the model specifically for more projects requests
    """
    print("🔧 call_more_projects_model invoked")
    
    # Extract the original query context from conversation history
    messages = state["messages"]
    original_query = ""
    
    # Look for the original query in the conversation
    for msg in reversed(messages[:-1]):  # Skip the last "more projects" message
        if isinstance(msg, HumanMessage):
            original_query = msg.content
            break
    
    # Create a new message that combines the original context with the more projects request
    enhanced_query = f"Based on the previous query: '{original_query}', find different/additional projects that haven't been shown yet."
    
    # Use the more projects tool
    response = model.invoke([
        HumanMessage(content=enhanced_query),
        AIMessage(content="I'll search for additional projects that haven't been shown yet.", 
                 tool_calls=[{
                     "name": "query_more_projects",
                     "args": {"query": original_query},
                     "id": "more_projects_call"
                 }])
    ])
    
    print(f"🔧 call_more_projects_model response: {getattr(response, 'content', '')[:50]}...")
    return {"messages": [response]}

# ================ Defining models ================

tools = [query_docs, query_more_projects]

model = AzureChatOpenAI(
    model_name=AZURE_AGENT_DEPLOYMENT,
    temperature=0,
    openai_api_key=AZURE_API_KEY,
    azure_endpoint=AZURE_ENDPOINT,
).bind_tools(tools)

final_model = AzureChatOpenAI(
    model_name=AZURE_FINAL_MODEL_DEPLOYMENT,
    temperature=0,
    openai_api_key=AZURE_API_KEY,
    azure_endpoint=AZURE_ENDPOINT,
).with_config(tags=["final_node"])

tool_node = ToolNode(tools=tools)

# ================ Building the graph ================

builder = StateGraph(MessagesState)

builder.add_node("agent", lambda state: call_model(state, model))
builder.add_node("tools", tool_node)
builder.add_node("more_projects", lambda state: call_more_projects_model(state, model))
builder.add_node("final", lambda state: call_final_model(state, final_model))

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", detect_more_projects_request)
builder.add_edge("tools", "agent")
builder.add_edge("more_projects", "tools")
builder.add_edge("final", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    return cl.User(identifier=username)

@cl.on_message
async def on_message(message: cl.Message):
    print(f"🐍 on_message received: {message.content}")
    user_query = message.content
    session_id = cl.context.session.id

    # Get user information for Langfuse tracking
    user = cl.context.session.user
    user_id = user.identifier if user else "anonymous"
   
    
    print(f"�� User: {user_id}")

    # Interim message with cl.step
    step = cl.Message(content="🔍 Analysing your request and generating a response…")
    await step.send()
    
    messages = [HumanMessage(content=user_query)]

    config: Dict[str, Any] = {
        "configurable": {
            "thread_id": session_id,
        }
    }

    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]

    final_answer = cl.Message(content="")
    response_content = ""
    error = None
    with langfuse.start_as_current_span(name="langchain-request") as span:
        span.update_trace(
            session_id=session_id,
            tags=["langchain"],
            input={
                "query": user_query,
                "user_id": user_id,
                "session_id": session_id
            }, metadata={
                "user_metadata": user.metadata if user else {},
                "auth_method": user.metadata.get("auth_method", "anonymous") if user else "anonymous"
            }
        )
        try:
            for msg_, metadata in graph.stream(
                {"messages": messages},
                stream_mode="messages",
                config=config,
            ):
                if (
                    msg_.content
                    and not isinstance(msg_, HumanMessage)
                    and metadata.get("langgraph_node") == "final"
                ):
                    response_content += msg_.content
                    await final_answer.stream_token(msg_.content)
        except Exception as e:
            error = str(e)
            print(f"💥 [ERROR] during graph.stream: {e}")
            await step.remove()
            await cl.Message(content=f"❌ Erreur : {error}").send()
            return
        span.update_trace(output={
            "response": response_content,
            "user_id": user_id,
            "session_id": session_id
        }, 
        metadata = {
            "response_length": len(response_content),
            "user_authenticated": user is not None
        }
        )
        await step.remove()
        await final_answer.send()
        print("✅ final answer sent")
        
# @cl.oauth_callback
# def oauth_callback(
#     provider_id: str,
#     token: str,
#     raw_user_data: Dict[str, str],
#     default_user: cl.User,
# ) -> Optional[cl.User]:
#     if provider_id == "azure-ad":
#         email = raw_user_data.get("email") or raw_user_data.get("upn")
#         if email and email.endswith("@mantu.com"):  # Replace with your org's domain to restrict access
#             default_user.identifier = email
#             default_user.name = email.split("@")[0]
#             default_user.metadata["source"] = "Azure AD"
#             return default_user
#     return None  # Deny access if not matching criteria

