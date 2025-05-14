from click import DateTime
from sqlalchemy import Column, String, Integer, ForeignKey, Enum, Date, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class User(Base):
    __tablename__ = 'users'
    email = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)

    recipes = relationship('Recipe', back_populates='owner')
    meal_plans = relationship('MealPlan', back_populates='user')

class Recipe(Base):
    __tablename__ = 'recipes'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    ingredients = Column(JSONB)
    instructions = Column(JSONB)
    owner_email = Column(String, ForeignKey('users.email'))
    original_url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner = relationship('User', back_populates='recipes')


class MealType(enum.Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"

class MealPlan(Base):
    __tablename__ = 'meal_plans'
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, ForeignKey('users.email'))
    date = Column(Date, nullable=False)
    meal_type = Column(Enum(MealType), nullable=False)
    recipe_id = Column(Integer, ForeignKey('recipes.id', ondelete="CASCADE"), nullable=True)

    user = relationship('User', back_populates='meal_plans')
    recipe = relationship('Recipe')