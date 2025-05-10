from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import json
from app.models.models import User, Recipe as RecipeModel
from recipe_scrapers import scrape_me
from app.utils.ollama_utils import extract_recipe_via_ollama
from app.schemas.schemas import RecipeURL, ExtractedRecipe, UserCreate, Recipe
from app.database import SessionLocal
from fastapi.security import OAuth2PasswordRequestForm
from app.utils.auth import get_password_hash, authenticate_user, create_access_token, get_current_user
from typing import List
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



@router.post("/extract-recipe")
async def extract_recipe(recipe_url: RecipeURL):
    """
    Attempts to extract a recipe using recipe-scrapers.
    If the website isn't supported, falls back to using Ollama.
    """
    try:
        scraper = scrape_me(recipe_url.url)
        title = scraper.title()
        ingredients = scraper.ingredients()
        raw_instructions = scraper.instructions()
        instructions = [step.strip() for step in raw_instructions.split("\n") if step.strip()]
        return ExtractedRecipe(title=title, ingredients=ingredients, instructions=instructions)
    except Exception as e:
        error_msg = str(e).lower()
        if "not supported" in error_msg:
            try:
                return extract_recipe_via_ollama(recipe_url.url)
            except Exception as llm_e:
                raise HTTPException(status_code=500, detail=f"Fallback LLM extraction failed: {str(llm_e)}")
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
        owner_email=current_user.email  # determined securely via JWT
    )

    db.add(db_recipe)
    db.commit()
    db.refresh(db_recipe)

    return Recipe(
        id=db_recipe.id,
        title=db_recipe.title,
        ingredients=recipe.ingredients,
        instructions=recipe.instructions
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
            instructions=json.loads(recipe.instructions)
        )
        for recipe in recipes
    ]

@router.get("/health")
async def health_check():
    return {"status": "healthy"}
