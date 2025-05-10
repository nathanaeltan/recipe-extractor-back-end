from pydantic import BaseModel, EmailStr
from typing import List

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class RecipeURL(BaseModel):
    url: str

class ExtractedRecipe(BaseModel):
    title: str
    ingredients: List[str]
    instructions: List[str]

class Recipe(BaseModel):
    id: int
    title: str
    ingredients: List[str]
    instructions: List[str]

    class Config:
        orm_mode = True

class RecipeSave(BaseModel):
    user_email: EmailStr
    title: str
    ingredients: List[str]
    instructions: List[str]
