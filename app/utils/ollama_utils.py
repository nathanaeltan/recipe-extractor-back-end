import threading
import ollama
import json
import requests
from fastapi import HTTPException
from app.models.recipe import Recipe
from app.utils.scraping_utils import preprocess_html
import os
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

ollama_client = ollama.Client(host=OLLAMA_HOST)


def ollama_chat_with_timeout(model, messages, timeout=30):
    """Call Ollama with a timeout using a background thread."""
    result = {"success": False, "response": None, "error": None}

    def target():
        try:
            result["response"] = ollama_client.chat(model=model, messages=messages)
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        return {"success": False, "error": "Request timed out"}
    return result

def extract_recipe_via_ollama(url: str) -> Recipe:
    """Fallback extraction: Fetch page, preprocess HTML, and use LLM via Ollama."""
    try:
        response = requests.get(url, headers={
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/91.0.4472.124 Safari/537.36')
        })
        response.raise_for_status()
        text_content = preprocess_html(response.text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL for fallback: {str(e)}")

    prompt = f"""
Extract the recipe information from the text below.
YOU MUST RETURN ONLY VALID JSON in this exact format:
{{
  "title": "Recipe Title",
  "ingredients": ["ingredient 1", "ingredient 2", ...],
  "instructions": ["step 1", "step 2", ...]
}}

Ensure that:
- The ingredients list contains every section (e.g., main ingredients, sauce, garnish, etc.).
- Do not include nutritional info or cooking instructions in the ingredients list.
- The instructions are only step-by-step directions.
- Format quantities properly (e.g., "1 cup flour", not "1cup flour").

Text:
{text_content[:4000]}
"""
    llm_result = ollama_chat_with_timeout(
        model="llama2:13b-chat-q4_0",
        messages=[
            {"role": "system", "content": "You are a recipe extraction assistant. Respond only with valid JSON in the specified format."},
            {"role": "user", "content": prompt}
        ],
        timeout=45
    )
    if not llm_result["success"]:
        raise HTTPException(status_code=500, detail=f"LLM processing failed: {llm_result.get('error', 'Unknown error')}")

    llm_response = llm_result["response"]["message"]["content"]
    try:
        recipe_data = json.loads(llm_response)
        from app.models.recipe import Recipe  # local import to avoid circular dependency
        return Recipe(
            title=recipe_data.get("title", ""),
            ingredients=recipe_data.get("ingredients", []),
            instructions=recipe_data.get("instructions", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing LLM response: {str(e)}")
