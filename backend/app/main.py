from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import auth, transactions, chat
from .database import engine
from .models.models import Base

# Buat tabel jika belum ada (untuk backup jika manual create gagal)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FinTracks API")

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

@app.get("/")
def root():
    return {"message": "Welcome to FinTracks API!"}
