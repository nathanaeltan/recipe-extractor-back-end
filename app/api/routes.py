from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import json
from app.models.models import User, Recipe as RecipeModel, MealPlan as MealPlanModel
from recipe_scrapers import scrape_me, SCRAPERS
from app.schemas.schemas import RecipeURL, ExtractedRecipe, UserCreate, Recipe, MealPlanCreate, MealPlan
from app.database import SessionLocal
from fastapi.security import OAuth2PasswordRequestForm
from app.utils.auth import get_password_hash, authenticate_user, create_access_token, get_current_user
from app.utils.youtube_utils import extract_youtube_video_details
import os
from typing import List
from datetime import date
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/signup")
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, name=user.name, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"email": db_user.email, "name": db_user.name}


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/supported-sites", response_model=List[str])
async def get_supported_sites():
    """
    Returns a list of all valid sites supported by the recipe-scrapers library.
    """
    return list(SCRAPERS.keys())

@router.post("/extract-recipe")
async def extract_recipe(recipe_url: RecipeURL, current_user: User = Depends(get_current_user)):
    """
    Attempts to extract a recipe using recipe-scrapers.
    If the website isn't supported, falls back to using GPT.
    """
    try:
        if "youtube.com" in recipe_url.url or "youtu.be" in recipe_url.url:
            # Extract the YouTube video description
            ALLOWED_GPT_EMAILS = os.getenv("ALLOWED_GPT_EMAILS", "").split(",")
            if current_user.email not in ALLOWED_GPT_EMAILS:
                raise HTTPException(status_code=403, detail="You are not allowed to use this feature.")
            return extract_youtube_video_details(recipe_url.url)
        else:
            scraper = scrape_me(recipe_url.url)
            title = scraper.title()
            ingredients = scraper.ingredients()
            raw_instructions = scraper.instructions()
            image_url = scraper.image()
            instructions = [step.strip() for step in raw_instructions.split("\n") if step.strip()]
            return ExtractedRecipe(title=title, ingredients=ingredients, instructions=instructions, original_url=recipe_url.url, image_url=image_url)
    except Exception as e:
        error_msg = str(e).lower()
        print(error_msg, "ERROR MESSAGE")
        if "not supported" in error_msg:
            raise HTTPException(status_code=400, detail=f"This website is not supported right now. Please try another one.")
        else:
            raise HTTPException(status_code=400, detail=f"Error extracting recipe: {str(e)}")


@router.post("/save-recipe", response_model=Recipe)
async def save_recipe(
    recipe: ExtractedRecipe,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_recipe = RecipeModel(
        title=recipe.title,
        ingredients=json.dumps(recipe.ingredients),
        instructions=json.dumps(recipe.instructions),
        owner_email=current_user.email,
        original_url=recipe.original_url,
        image_url=recipe.image_url,
    )

    db.add(db_recipe)
    db.commit()
    db.refresh(db_recipe)

    return Recipe(
        id=db_recipe.id,
        title=db_recipe.title,
        ingredients=recipe.ingredients,
        instructions=recipe.instructions,
        original_url=recipe.original_url,
        image_url=recipe.image_url,
    )

@router.get("/recipes", response_model=List[Recipe])
async def get_user_recipes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    recipes = db.query(RecipeModel).filter(
        RecipeModel.owner_email == current_user.email
    ).all()

    return [
        Recipe(
            id=recipe.id,
            title=recipe.title,
            ingredients=json.loads(recipe.ingredients),
            instructions=json.loads(recipe.instructions),
            original_url=recipe.original_url,
            image_url=recipe.image_url,
        )
        for recipe in recipes
    ]


@router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes a recipe by its ID if it belongs to the current user.
    """
    # Query the recipe by ID and ensure it belongs to the current user
    recipe = db.query(RecipeModel).filter(
        RecipeModel.id == recipe_id,
        RecipeModel.owner_email == current_user.email
    ).first()

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Delete the recipe
    db.delete(recipe)
    db.commit()

    return {"message": "Recipe deleted successfully"}

@router.post("/meal-plans", response_model=MealPlan)
async def create_meal_plan(
    meal_plan: MealPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_meal_plan = MealPlanModel(
        user_email=current_user.email,
        date=meal_plan.date,
        meal_type=meal_plan.meal_type,
        recipe_id=meal_plan.recipe_id,
    )
    db.add(db_meal_plan)
    db.commit()
    db.refresh(db_meal_plan)
    return db_meal_plan

@router.get("/meal-plans", response_model=List[MealPlan])
async def get_meal_plans(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    meal_plans = db.query(MealPlanModel).filter(
        MealPlanModel.user_email == current_user.email,
        MealPlanModel.date >= start_date,
        MealPlanModel.date <= end_date
    ).all()
    return [
        MealPlan(
            id=meal_plan.id,
            date=meal_plan.date,
            meal_type=meal_plan.meal_type,
            recipe_id=meal_plan.recipe_id,
            recipe_title=meal_plan.recipe.title if meal_plan.recipe else None
        )
        for meal_plan in meal_plans
    ]

@router.delete("/meal-plans/{meal_plan_id}")
async def delete_meal_plan(
    meal_plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    meal_plan = db.query(MealPlanModel).filter(
        MealPlanModel.id == meal_plan_id,
        MealPlanModel.user_email == current_user.email
    ).first()
    if not meal_plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    db.delete(meal_plan)
    db.commit()
    return {"message": "Meal plan deleted successfully"}
@router.get("/health")
async def health_check():
    return {"status": "healthy"}
