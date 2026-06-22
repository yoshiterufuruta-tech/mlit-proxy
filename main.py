from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

app = FastAPI()

# CORS 設定（これがないとブラウザからアクセスできない）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 必要なら ["https://teruteruboz.nobu-naga.net"] に変更
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MLIT_API_KEY = os.getenv("MLIT_API_KEY")
