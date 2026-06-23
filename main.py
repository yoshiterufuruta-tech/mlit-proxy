from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "data"  # pref_1.json 〜 pref_47.json を置くフォルダ


@app.get("/")
def root():
    return {"status": "ok", "message": "Local JSON Mode Running on Render"}


@app.get("/estimate")
def estimate(pref: int):
    file_path = os.path.join(DATA_DIR, f"pref_{pref}.json")

    if not os.path.exists(file_path):
        return {"error": f"pref_{pref}.json が見つかりません"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"JSON 読み込みエラー: {e}"}
