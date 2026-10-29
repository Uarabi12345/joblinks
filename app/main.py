from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app import routes

# Safe creation. Will not wipe data on restart.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="JobLinks")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(routes.router)