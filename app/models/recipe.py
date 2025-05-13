from pydantic import BaseModel
from typing import List

class RecipeURL(BaseModel):
    url: str

class Recipe(BaseModel):
    title: str
    ingredients: List[str]
    instructions: List[str]
    original_url: str
