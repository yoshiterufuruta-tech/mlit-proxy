from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://www.land.mlit.go.jp/webland/api"
HEADERS = {"User-Agent": "mlit-proxy/1.0"}


@app.get("/")
def root():
    return {"status": "ok", "message": "MLIT Proxy Running on Render"}


# -----------------------------
# 安全な API ラッパ（例外を握りつぶす）
# -----------------------------
def safe_get(url, timeout=10):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return r.json()
    except Exception as e:
        print("ERROR:", url, e)
        return {"data": []}


def fetch_prefectures():
    return safe_get(f"{BASE_URL}/XIT0010").get("data", [])


def fetch_cities(pref_code: str):
    return safe_get(f"{BASE_URL}/XIT002?pref={pref_code}").get("data", [])


def fetch_transactions(city_code: str, year: int, quarter: int):
    return safe_get(
        f"{BASE_URL}/XIT001?city={city_code}&year={year}&quarter={quarter}",
        timeout=15
    ).get("data", [])


# -----------------------------
# 正規化（例外を完全に防ぐ）
# -----------------------------
def _to_float(x):
    try:
        return float(x)
    except:
        return None


def _to_int(x):
    try:
        return int(x)
    except:
        return None


def normalize_record(r):
    return {
        "pref": r.get("pref"),
        "city": r.get("city"),
        "type": r.get("Type"),
        "area": _to_float(r.get("Area")),
        "building_year": _to_int(r.get("BuildingYear")),
        "walk": _to_int(r.get("Walk")),
        "price": _to_float(r.get("TradePrice")),
        "lat": _to_float(r.get("Latitude")),
        "lng": _to_float(r.get("Longitude")),
    }


# -----------------------------
# AI 推定（軽量）
# -----------------------------
def estimate_price(features):
    base = 2000.0
    if features.get("area"):
        base *= features["area"] / 50.0

    if features.get("walk") is not None:
        base *= max(0.6, 1.2 - features["walk"] * 0.02)

    if features.get("building_age") is not None:
        base *= max(0.5, 1.0 - features["building_age"] * 0.01)

    return {
        "median": base,
        "ci95": [base * 0.8, base * 1.2],
    }


# -----------------------------
# 都道府県単位の推定（例外に強い）
# -----------------------------
@app.get("/estimate")
def estimate(year: int = 2024, quarter: int = 4, pref: int = None):
    if pref is None:
        return {"error": "pref パラメータを指定してください（例: /estimate?pref=23）"}

    results = []

    prefectures = fetch_prefectures()
    target = [p for p in prefectures if int(p["id"]) == pref]

    if not target:
        return {"error": f"都道府県コード {pref} は存在しません"}

    pref_code = target[0]["id"]
    pref_name = target[0]["name"]

    cities = fetch_cities(pref_code)

    for city in cities:
        city_code = city["id"]
        city_name = city["name"]

        raw = fetch_transactions(city_code, year, quarter)
        if not raw:
            continue

        for r in raw:
            try:
                r["pref"] = pref_name
                r["city"] = city_name

                item = normalize_record(r)
                fv = build_feature_vector(item)
                pred = estimate_price(fv)

                results.append({
                    "pref": item["pref"],
                    "city": item["city"],
                    "lat": item["lat"],
                    "lng": item["lng"],
                    "predicted_price": pred["median"],
                    "ci95": pred["ci95"],
                    "raw": item,
                })
            except Exception as e:
                print("SKIP RECORD:", e)
                continue

        time.sleep(0.3)  # ← 0.15 → 0.3 に増やして安定化

    return {"count": len(results), "data": results}
