# database.py (create_db.py script)
from database import engine, Base
import models.models  # noqa

Base.metadata.create_all(bind=engine)
print("Database tables created")