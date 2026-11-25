"""FastAPI application for Actual Text PDF.

In development the React/Vite frontend runs on port 5173.
In a packaged build, the compiled frontend is served by this same Uvicorn app.
"""
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes.pdf_routes import router as pdf_router

app = FastAPI(title="Actual Text PDF API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Repair-Created-Spans",
        "X-Repair-Unchanged-Spans",
        "X-Repair-Skipped",
    ],
)

app.include_router(pdf_router, prefix="/api/pdf", tags=["PDF"])

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "actual-text-pdf"}

if getattr(sys, "frozen", False):
    # PyInstaller --onedir stores data files beneath sys._MEIPASS.
    frontend_dist = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "frontend_dist"
else:
    # main.py -> app -> backend -> project root
    project_root = Path(__file__).resolve().parents[2]
    frontend_dist = project_root / "frontend" / "dist"

if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
    # Mount last so /api routes are matched first.
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
