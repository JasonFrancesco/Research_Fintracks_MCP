import sys
from pathlib import Path

# Memastikan folder backend terdaftar di sys.path agar uvicorn menemukan modul app
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.routes import auth, transactions, chat, gatling
from app.database import engine
from app.models.models import Base


# Buat tabel jika belum ada (untuk backup jika manual create gagal)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FinTracks API")

gatling_assets_dir = os.path.join(backend_dir, "gatling_template")
if os.path.exists(gatling_assets_dir):
    app.mount("/gatling-assets", StaticFiles(directory=gatling_assets_dir), name="gatling-assets")

# Konfigurasi CORS agar Frontend React bisa akses Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Daftarkan Routes
app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(chat.router)
app.include_router(gatling.router)

@app.get("/")
def root():
    return {"message": "Welcome to FinTracks API!"}
