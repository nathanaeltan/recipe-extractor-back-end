from pydantic import BaseModel, EmailStr
from typing import List, Optional
from enum import Enum
from datetime import date

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
    original_url: Optional[str] = None
    image_url: Optional[str] = None

class Recipe(BaseModel):
    id: int
    title: str
    ingredients: List[str]
    instructions: List[str]
    original_url: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        orm_mode = True

class RecipeSave(BaseModel):
    user_email: EmailStr
    title: str
    ingredients: List[str]
    instructions: List[str]
    original_url: Optional[str] = None
    image_url: Optional[str] = None


class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"

class MealPlanCreate(BaseModel):
    date: date
    meal_type: MealType
    recipe_id: Optional[int] = None

class MealPlan(BaseModel):
    id: int
    date: date
    meal_type: MealType
    recipe_id: Optional[int] = None
    recipe_title: Optional[str] = None
    class Config:
        orm_mode = True