import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langdetect import detect
from src.utils.prompt_list import TRANSLATE_TO_ENGLISH_PROMPT


load_dotenv()


def is_english(input_text: str) -> bool:
    """Detect if the given text is in English using langdetect.

    Args:
        text (str): The text to check.
    Returns:
        bool: True if text is English, False otherwise.
    """
    try:
        lang = detect(input_text)
        return lang == "en"
    except (FileNotFoundError, UnicodeDecodeError) as e:
        print(f"🛑 Fail to detect language :{e}")
        # Return False if file can't be read or decoded
        return False
    except Exception:
        # Catching all exceptions to ensure function returns False on any read/detect error
        return False

def translate_file(input_text : str) -> str:
    """Translate a .txt file to English using Azure OpenAI and return the result as a string.

    Args:
        input_path (Path): Path to the input .txt file in French.

    Returns:
        str: The translated English text.

    Raises:
        RuntimeError: If environment variables are missing or LLM call fails.
    """

    try:
        api_key = os.environ["AZURE_OPENAI_API_KEY"]
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        model = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    except KeyError as e:
        raise RuntimeError(f"Missing environment variable: {e}") from e

    llm = AzureChatOpenAI(
        model_name=model, temperature=0, openai_api_key=api_key, azure_endpoint=endpoint
    )

    prompt = TRANSLATE_TO_ENGLISH_PROMPT.format(text=input_text)
    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
    except Exception as exc:
        raise RuntimeError(f"Error during LLM call: {exc}") from exc

    if isinstance(response.content, str):
        translated = response.content.strip()
    else:
        raise RuntimeError("Unexpected response from LLM.")

    return translated
