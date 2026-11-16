from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_indexes
from app.routers import assistant, auth, repos


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_indexes()
    yield


app = FastAPI(
    title="CodeLens AI",
    description="AI-powered code intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

app.include_router(auth.router)
app.include_router(repos.router)
app.include_router(assistant.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/ui/")


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok"}
