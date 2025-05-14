import os
from pytubefix import YouTube
import openai
import json
from app.schemas.schemas import ExtractedRecipe

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def extract_youtube_video_details(url: str):
    """
    Extract details from a YouTube video URL.
    Returns the title, description, and thumbnail URL.
    """
    try:
        yt = YouTube(url)
        title = yt.title
        description = yt.description
        thumbnail_url = yt.thumbnail_url
        openai.api_key = OPENAI_API_KEY
        prompt = f"""
        Extract the recipe information from the following YouTube video description:
        {description}

        YOU MUST RETURN ONLY VALID JSON in this exact format:
        {{
          "title": "Recipe Title",
          "ingredients": ["ingredient 1", "ingredient 2", ...],
          "instructions": ["step 1", "step 2", ...]
        }}
        """

         # Call OpenAI API
        response =  openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a recipe extraction assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        # Parse the response
        recipe_data = response.choices[0].message.content
        recipe_json = json.loads(recipe_data)

        return ExtractedRecipe(
            title=recipe_json.get("title", title),
            ingredients=recipe_json.get("ingredients", []),
            instructions=recipe_json.get("instructions", []),
            original_url=url,
            image_url=thumbnail_url,
        )

    except Exception as e:
        raise ValueError(f"Failed to extract YouTube video details: {str(e)}")