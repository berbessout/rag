import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
from pydantic import SecretStr
# Import absolu car Customer_txt n'est pas dans src donc on doit lancer le script avec python -m src.llm_semantic_splitter
from src.utils.prompt_list import LLMSPLITTER_PROMPT
from .translate import is_english, translate_file

load_dotenv()

AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt4o")

def semantic_split(document_source: str, raw_document_text: str, max_chunk_size: int = 1000) -> tuple[list[str], list[dict]]:
    """Splits a text into semantic segments using an Azure OpenAI LLM.

    Args:
        document_source (str): The source of the document.
        document_context (str): The context of the document.
        max_chunk_size (int, optional): Maximum size of a segment (in characters). Defaults to 1000.

    Returns:
        tuple[list[str], list[dict]]: A tuple containing the list of chunks and the list of metadata dicts.

    Raises:
        RuntimeError: If the LLM call fails or environment variables are missing or JSON parsing fails.
    """

    all_texts: List[str] = []
    all_metadata: List[Dict[str, Any]] = []

    try:
        api_key = os.environ["AZURE_OPENAI_API_KEY"]
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        version = os.environ["OPENAI_API_VERSION"]
    except KeyError as e:
        raise RuntimeError(f"Missing environment variable: {e}")

    
    llm = AzureChatOpenAI(
        azure_deployment=AZURE_OPENAI_DEPLOYMENT,
        temperature=0,
        api_key=SecretStr(api_key),
        azure_endpoint=endpoint,
        api_version=version
    )
    # Translate if not English
    if is_english(raw_document_text):
        context = raw_document_text
    else:
        print(f"🌐 Translating '{document_source}' to English...")
        context = translate_file(raw_document_text)
    
    prompt = LLMSPLITTER_PROMPT.format(
        document_source=document_source,
        document_context=context
    )
    try:
        response = llm.invoke([
            {"role": "user", "content": prompt}
        ])
    except Exception as exc:
        raise RuntimeError(f"Error during LLM call: {exc}")

   
    match response.content:
        case str() as content:
            # Nettoyage des balises ```json ``` éventuelles
            clean = re.sub(r"^```(?:json)?\s*", "", content)
            clean = re.sub(r"\s*```$", "", clean)
            try:
                data = json.loads(clean)
                chunks = data.get("chunks", [])
                metadata = data.get("metadata", [])
            except Exception as exc:
                raise RuntimeError(
                    f"Could not parse LLM response as JSON: {exc}\nResponse content: {content}"
                )
        case _:
            raise RuntimeError("Unexpected response from LLM.")
    # Aggregate
    all_texts.extend(chunks)

    for i, chunk in enumerate(chunks):
        chunk_metadata = metadata.copy()  # Create a copy of the base metadata
        chunk_metadata["chunk_id"] = i + 1
        all_metadata.append(chunk_metadata)
    return all_texts, all_metadata
