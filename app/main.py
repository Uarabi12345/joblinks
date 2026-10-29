from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app import routes

# This is safe. It creates tables only if they don't exist.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="JobLinks")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(routes.router)