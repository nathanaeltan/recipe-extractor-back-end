from fastapi import FastAPI
from app.api.routes import router as api_router
from app.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware


Base.metadata.create_all(engine)

app = FastAPI(title="Recipe Extractor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include our routes.
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
