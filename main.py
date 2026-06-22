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
# API ラッパ
# -----------------------------
def fetch_prefectures():
    url = f"{BASE_URL}/XIT0010"
    r = requests.get(url, headers=HEADERS, timeout=10)
    return r.json().get("data", [])


def fetch_cities(pref_code: str):
    url = f"{BASE_URL}/XIT002?pref={pref_code}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    return r.json().get("data", [])


def fetch_transactions(city_code: str, year: int, quarter: int):
    url = f"{BASE_URL}/XIT001?city={city_code}&year={year}&quarter={quarter}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    return r.json().get("data", [])


# -----------------------------
# 正規化
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


def build_feature_vector(item):
    building_age = None
    if item["building_year"]:
        building_age = 2026 - item["building_year"]

    return {
        "area": item["area"],
        "building_age": building_age,
        "walk": item["walk"],
        "lat": item["lat"],
        "lng": item["lng"],
        "type": item["type"],
    }


# -----------------------------
# AI 推定（ダミー）
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
# 全国推定
# -----------------------------
def estimate_all_japan(year=2024, quarter=4, sleep_sec=0.2):
    results = []

    prefectures = fetch_prefectures()
    for pref in prefectures:
        pref_code = pref["id"]
        pref_name = pref["name"]

        cities = fetch_cities(pref_code)
        for city in cities:
            city_code = city["id"]
            city_name = city["name"]

            raw = fetch_transactions(city_code, year, quarter)
            if not raw:
                continue

            for r in raw:
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

            time.sleep(sleep_sec)

    return results


@app.get("/estimate")
def estimate(year: int = 2024, quarter: int = 4):
    data = estimate_all_japan(year, quarter)
    return {"count": len(data), "data": data}
