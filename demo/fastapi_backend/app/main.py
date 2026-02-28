"""Demo FastAPI app entrypoint."""

from fastapi import FastAPI

from .users import router as users_router

app = FastAPI(title="Demo FastAPI Backend")
app.include_router(users_router)
