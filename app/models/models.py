from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = 'users'
    email = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)

    recipes = relationship('Recipe', back_populates='owner')

class Recipe(Base):
    __tablename__ = 'recipes'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    ingredients = Column(JSONB)
    instructions = Column(JSONB)
    owner_email = Column(String, ForeignKey('users.email'))

    owner = relationship('User', back_populates='recipes')
