from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.router import meetings, pages

app = FastAPI(title="Meeting Calendar", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(pages.router)
app.include_router(meetings.router)


@app.on_event("startup")
def startup():
    init_db()
