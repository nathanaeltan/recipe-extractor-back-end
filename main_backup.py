from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import ollama
import json
import re
from typing import List, Optional
import threading

app = FastAPI(title="Recipe Extractor API")

# Works with allrecipes, recipetineats
class RecipeURL(BaseModel):
    url: str

class Recipe(BaseModel):
    title: str
    ingredients: List[str]
    instructions: List[str]

# Add a timeout to Ollama requests
def ollama_chat_with_timeout(model, messages, timeout=30):
    """Run Ollama chat with a timeout"""
    result = {"success": False, "response": None, "error": None}

    def target():
        try:
            result["response"] = ollama.chat(model=model, messages=messages)
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

def clean_ingredients(ingredients):
    """Clean up ingredient formatting"""
    cleaned = []
    for ingredient in ingredients:
        # Remove special characters like ▢, □, etc.
        ingredient = re.sub(r'[▢□■►•◆]', '', ingredient)
        # Fix missing spaces between numbers and units
        ingredient = re.sub(r'(\d+)([a-zA-Z])', r'\1 \2', ingredient)
        # Fix missing spaces between units and words
        ingredient = re.sub(r'([a-zA-Z])([A-Z])', r'\1 \2', ingredient)
        # Fix common measurement abbreviations
        ingredient = re.sub(r'(\d+)tbsp', r'\1 tbsp', ingredient)
        ingredient = re.sub(r'(\d+)tsp', r'\1 tsp', ingredient)
        ingredient = re.sub(r'(\d+)cup', r'\1 cup', ingredient)
        ingredient = re.sub(r'(\d+)g', r'\1 g', ingredient)
        ingredient = re.sub(r'(\d+)oz', r'\1 oz', ingredient)
        ingredient = re.sub(r'(\d+)ml', r'\1 ml', ingredient)
        ingredient = re.sub(r'(\d+)lb', r'\1 lb', ingredient)
        # Remove extra spaces
        ingredient = re.sub(r'\s+', ' ', ingredient).strip()
        cleaned.append(ingredient)
    return cleaned

def filter_instructions(instructions: List[str], ingredients: List[str]) -> List[str]:
    """Remove instructions that duplicate ingredients or include nutritional info."""
    filtered = []
    for instr in instructions:
        # Skip if the instruction exactly matches any ingredient (case-insensitive)
        if any(instr.strip().lower() == ing.strip().lower() for ing in ingredients):
            continue
        # Skip if instruction appears to be nutritional information
        if re.match(r'^(kcal|fat|saturates|carbs|sugars|fibre|protein|salt)', instr, re.IGNORECASE):
            continue
        filtered.append(instr)
    return filtered

def preprocess_html(html_content):
    """Extract just the relevant parts of the HTML to reduce noise"""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove script, style, and other non-content elements
    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
        tag.extract()

    # Try to find the main content using common selectors
    main_content = None
    for selector in ['main', 'article', '.recipe', '#recipe', '.recipe-content', '.wprm-recipe']:
        content = soup.select_one(selector)
        if content:
            main_content = content
            break

    # If no main content is found, use the whole body
    if not main_content:
        main_content = soup.body

    # Extract text with formatting for headings and list items
    lines = []
    for element in main_content.find_all(['h1', 'h2', 'h3', 'p', 'li', 'div']):
        text = element.get_text(strip=True)
        if text:
            tag = element.name
            if tag == 'h1':
                lines.append(f"# {text}")
            elif tag == 'h2':
                lines.append(f"## {text}")
            elif tag == 'h3':
                lines.append(f"### {text}")
            elif tag == 'li':
                lines.append(f"- {text}")
            else:
                lines.append(text)
    return "\n".join(lines)

def extract_recipe_from_html(html_content):
    """Try to extract recipe information directly from HTML structure"""
    soup = BeautifulSoup(html_content, 'html.parser')
    recipe_data = {
        "title": "",
        "ingredients": [],
        "instructions": []
    }

    # Try to find the recipe title from a few candidate elements
    title_candidates = [
        soup.find('h1', class_=lambda c: c and 'recipe' in c.lower()),
        soup.find('h1', class_=lambda c: c and 'title' in c.lower()),
        soup.find('h1'),
        soup.find('meta', {'property': 'og:title'}),
        soup.find('meta', {'name': 'title'})
    ]
    for candidate in title_candidates:
        if candidate and (candidate.string or candidate.get('content')):
            recipe_data["title"] = (candidate.string or candidate.get('content')).strip()
            break

    # Try to find ingredients from candidate lists
    ingredients_lists = [
        soup.find('ul', class_=lambda c: c and 'ingredient' in c.lower()),
        soup.find('div', class_=lambda c: c and 'ingredient' in c.lower()),
        soup.find_all('li', class_=lambda c: c and 'ingredient' in c.lower())
    ]
    for ingredient_list in ingredients_lists:
        if ingredient_list:
            if isinstance(ingredient_list, list):
                recipe_data["ingredients"] = [item.get_text(strip=True) for item in ingredient_list]
            else:
                items = ingredient_list.find_all('li')
                if items:
                    recipe_data["ingredients"] = [item.get_text(strip=True) for item in items]
            if recipe_data["ingredients"]:
                recipe_data["ingredients"] = clean_ingredients(recipe_data["ingredients"])
                break

    # Try to find instructions from candidate lists
    instruction_lists = [
        soup.find('ol', class_=lambda c: c and 'instruction' in c.lower()),
        soup.find('div', class_=lambda c: c and 'instruction' in c.lower()),
        soup.find_all('li', class_=lambda c: c and ('instruction' in c.lower() or 'step' in c.lower()))
    ]
    for instruction_list in instruction_lists:
        if instruction_list:
            if isinstance(instruction_list, list):
                recipe_data["instructions"] = [item.get_text(strip=True) for item in instruction_list]
            else:
                items = instruction_list.find_all('li')
                if items:
                    recipe_data["instructions"] = [item.get_text(strip=True) for item in items]
            if recipe_data["instructions"]:
                break

    # Return recipe data if we have a title plus at least one of ingredients or instructions
    if recipe_data["title"] and (recipe_data["ingredients"] or recipe_data["instructions"]):
        return recipe_data
    else:
        return None

def parse_unstructured_recipe_text(text):
    """Parse recipe information from unstructured text when JSON parsing fails."""
    recipe_data = {
        "title": "",
        "ingredients": [],
        "instructions": []
    }

    # Extract title
    title_patterns = [
        r'(?:Recipe Name:|Title:|Recipe:)\s*([^\n]+)',
        r'\*\*(?:Recipe Name:|Title:|Recipe:)\*\*\s*([^\n]+)',
        r'#\s*([^\n]+)',  # Markdown H1
        r'(.*?)(?:\n|$)'  # Fallback: first line
    ]
    for pattern in title_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            recipe_data["title"] = match.group(1).strip()
            break

    # Extract ingredients section
    ingredients_section = None
    ingredients_patterns = [
        r'(?:Ingredients:|INGREDIENTS:)(.+?)(?:Instructions:|INSTRUCTIONS:|Directions:|NOTES:|$)',
        r'\*\*(?:Ingredients:|INGREDIENTS:)\*\*(.+?)(?:\*\*(?:Instructions:|INSTRUCTIONS:|Directions:|NOTES:)|$)',
        r'##\s*Ingredients(.+?)(?:##|$)',  # Markdown H2
    ]
    for pattern in ingredients_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            ingredients_section = match.group(1).strip()
            break
    if ingredients_section:
        ingredients = re.findall(r'(?:^|\n)(?:\d+\.|\*|\-)\s*([^\n]+)', ingredients_section)
        if ingredients:
            recipe_data["ingredients"] = clean_ingredients([item.strip() for item in ingredients])
        else:
            recipe_data["ingredients"] = clean_ingredients([item.strip() for item in ingredients_section.split('\n') if item.strip()])

    # Extract instructions section
    instructions_section = None
    instructions_patterns = [
        r'(?:Instructions:|INSTRUCTIONS:|Directions:|DIRECTIONS:|Method:|PREPARATION:)(.+?)(?:Notes:|NOTES:|To Serve:|$)',
        r'\*\*(?:Instructions:|INSTRUCTIONS:|Directions:|DIRECTIONS:|Method:|PREPARATION:)\*\*(.+?)(?:\*\*(?:Notes:|NOTES:|To Serve:)|$)',
        r'##\s*(?:Instructions|Directions|Method|Preparation)(.+?)(?:##|$)',  # Markdown H2
    ]
    for pattern in instructions_patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            instructions_section = match.group(1).strip()
            break
    if instructions_section:
        instructions = re.findall(r'(?:^|\n)(?:\d+\.|\*|\-)\s*([^\n]+)', instructions_section)
        if instructions:
            recipe_data["instructions"] = [item.strip() for item in instructions]
        else:
            recipe_data["instructions"] = [item.strip() for item in instructions_section.split('\n') if item.strip()]

    return recipe_data

def extract_recipe_from_llm_response(llm_response):
    """Try multiple approaches to extract recipe data from LLM response."""
    # First approach: Try to parse as JSON
    try:
        json_pattern = r'\{[\s\S]*?\}'
        matches = re.findall(json_pattern, llm_response)
        for potential_json in matches:
            try:
                fixed_json = potential_json.replace('\n', ' ')
                fixed_json = re.sub(r',\s*}', '}', fixed_json)
                fixed_json = re.sub(r',\s*]', ']', fixed_json)
                recipe_data = json.loads(fixed_json)
                if "title" in recipe_data and "ingredients" in recipe_data and "instructions" in recipe_data:
                    recipe_data["ingredients"] = clean_ingredients(recipe_data["ingredients"])
                    return recipe_data
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return parse_unstructured_recipe_text(llm_response)

@app.post("/extract-recipe", response_model=Recipe)
async def extract_recipe(recipe_url: RecipeURL):
    """Extract recipe details from a URL using a locally hosted LLM."""
    try:
        response = requests.get(recipe_url.url, headers={
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/91.0.4472.124 Safari/537.36')
        })
        response.raise_for_status()

        # Preprocess HTML to text
        preprocessed_text = preprocess_html(response.text)

        # Send *all* the text to the LLM
        prompt = f"""
Extract the recipe information from the content below.
YOU MUST RETURN ONLY VALID JSON in this exact format:
{{
  "title": "Recipe Title",
  "ingredients": ["ingredient 1", "ingredient 2", ...],
  "instructions": ["step 1", "step 2", ...]
}}

Ensure that:
- The ingredients list contains every section of ingredients (duck, curry sauce, garnishes, etc.).
- Do not include nutritional info.
- Do not include cooking steps in the ingredient list.
- The instructions are only step-by-step directions (no repeated ingredients).
- Format quantities properly (e.g., "1 cup flour", not "1cup flour").

Content:
{preprocessed_text[:4000]}
"""

        llm_result = ollama_chat_with_timeout(
            model="llama2:13b-chat-q4_0",
            messages=[
                {
                    "role": "system",
                    "content": ("You are a recipe extraction assistant. "
                                "You ONLY respond with valid JSON following the specified format.")
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            timeout=45
        )

        if not llm_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=f"LLM processing failed: {llm_result.get('error', 'Unknown error')}"
            )

        llm_response = llm_result["response"]["message"]["content"]
        recipe_data_from_llm = extract_recipe_from_llm_response(llm_response)

        # Clean up & filter
        final_recipe = {
            "title": recipe_data_from_llm.get("title", ""),
            "ingredients": clean_ingredients(recipe_data_from_llm.get("ingredients", [])),
            "instructions": filter_instructions(
                recipe_data_from_llm.get("instructions", []),
                recipe_data_from_llm.get("ingredients", [])
            ),
        }

        return Recipe(**final_recipe)

    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e.__class__.__name__}: {str(e)}")

@app.get("/health")
async def health_check():
    """Check if Ollama is running and accessible."""
    try:
        models = ollama.list()
        return {"status": "healthy", "ollama_connected": True, "models": models}
    except Exception as e:
        return {"status": "unhealthy", "ollama_connected": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
