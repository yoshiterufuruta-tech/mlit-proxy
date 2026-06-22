from fastapi import FastAPI
import requests
import os

app = FastAPI()

MLIT_API_KEY = os.getenv("MLIT_API_KEY")

def mlit_get(url, params):
    headers = {"Ocp-Apim-Subscription-Key": MLIT_API_KEY}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

@app.get("/api/xit0010")
def xit0010():
    return mlit_get("https://www.reinfolib.mlit.go.jp/api/xit0010/", {"o": "json"})

@app.get("/api/xit002")
def xit002(a: str):
    return mlit_get("https://www.reinfolib.mlit.go.jp/api/xit002/", {"o": "json", "a": a})

@app.get("/api/xit001")
def xit001(a: str = "", b: str = "", y: str = "", q: str = ""):
    return mlit_get("https://www.reinfolib.mlit.go.jp/api/xit001/", {
        "o": "json",
        "a": a,
        "b": b,
        "y": y,
        "q": q
    })
