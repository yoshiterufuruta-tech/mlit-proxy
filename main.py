#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
全国市区町村に対応した不動産価格推定パイプライン（完全版）

- 不動産情報ライブラリ API から全国データ取得
- レコード正規化
- 特徴量生成
- AI 推定（外部モデル API を呼ぶ想定）
- 結果を JSON に保存 or handler から返却
"""

import json
import time
from typing import List, Dict, Any, Optional

import requests


# =========================
# 設定
# =========================

BASE_URL = "https://www.land.mlit.go.jp/webland/api"
HEADERS = {"User-Agent": "mlit-proxy/1.0"}

# AI 推定エンドポイント（必要に応じて書き換え）
AI_ENDPOINT = "https://your-ai-endpoint.example.com/predict"


# =========================
# 不動産情報ライブラリ API ラッパ
# =========================

def fetch_prefectures() -> List[Dict[str, Any]]:
    """
    都道府県一覧取得（XIT0010）
    """
    url = f"{BASE_URL}/XIT0010"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data.get("data", [])


def fetch_cities(pref_code: str) -> List[Dict[str, Any]]:
    """
    市区町村一覧取得（XIT002）
    """
    url = f"{BASE_URL}/XIT002?pref={pref_code}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data.get("data", [])


def fetch_transactions(city_code: str, year: int, quarter: int) -> List[Dict[str, Any]]:
    """
    取引価格データ取得（XIT001）
    """
    url = f"{BASE_URL}/XIT001?city={city_code}&year={year}&quarter={quarter}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("data", [])


# =========================
# データ収集（全国市区町村）
# =========================

def collect_city_transactions(
    year: int = 2024,
    quarter: int = 4,
    sleep_sec: float = 0.2,
) -> List[Dict[str, Any]]:
    """
    全国の市区町村について取引データを収集し、
    各レコードに pref / city を付与して返す。
    """
    all_records: List[Dict[str, Any]] = []

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
                all_records.append(r)

            # API 負荷対策
            time.sleep(sleep_sec)

    return all_records


# =========================
# 正規化・特徴量生成
# =========================

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    try:
        if x is None or x == "":
            return None
        return int(x)
    except Exception:
        return None


def normalize_record(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    API レコードを AI モデルで扱いやすい形に正規化
    """
    return {
        "pref": r.get("pref"),
        "city": r.get("city"),
        "type": r.get("Type"),
        "area": _to_float(r.get("Area")),
        "building_year": _to_int(r.get("BuildingYear")),
        "use": r.get("Use"),
        "structure": r.get("Structure"),
        "walk": _to_int(r.get("Walk")),
        "price": _to_float(r.get("TradePrice")),
        "lat": _to_float(r.get("Latitude")),
        "lng": _to_float(r.get("Longitude")),
    }


def build_feature_vector(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    AI 推定用の特徴量ベクトルを構築
    （モデル仕様に合わせてここを調整）
    """
    building_age: Optional[int] = None
    if item["building_year"]:
        building_age = 2026 - item["building_year"]

    return {
        "area": item["area"],
        "building_age": building_age,
        "walk": item["walk"],
        "lat": item["lat"],
        "lng": item["lng"],
        "type": item["type"],
        # 必要なら one-hot などはサーバ側で処理
    }


# =========================
# AI 推定
# =========================

def estimate_price(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    AI モデルに特徴量を投げて推定結果を取得する。
    - ここはあなたのモデル API に合わせて書き換え。
    - 返り値は {"median": float, "ci95": [low, high]} などを想定。
    """
    # ダミー実装（外部 API がまだ無い場合の簡易版）
    # area, building_age, walk などから適当にスコアを作る例。
    if features.get("area") is None:
        base = 2000.0
    else:
        base = 2000.0 * (features["area"] / 50.0)

    if features.get("walk") is not None:
        base *= max(0.6, 1.2 - features["walk"] * 0.02)

    if features.get("building_age") is not None:
        base *= max(0.5, 1.0 - features["building_age"] * 0.01)

    # 本来はここで外部モデルに POST する
    # r = requests.post(AI_ENDPOINT, json=features, timeout=10)
    # return r.json()

    return {
        "median": base,
        "ci95": [base * 0.8, base * 1.2],
    }


# =========================
# 全国推定メイン処理
# =========================

def estimate_all_japan(
    year: int = 2024,
    quarter: int = 4,
    sleep_sec: float = 0.2,
) -> List[Dict[str, Any]]:
    """
    全国の取引データを取得し、1 レコードごとに価格推定を行う。
    """
    raw_records = collect_city_transactions(
        year=year,
        quarter=quarter,
        sleep_sec=sleep_sec,
    )

    results: List[Dict[str, Any]] = []

    for r in raw_records:
        item = normalize_record(r)
        fv = build_feature_vector(item)
        pred = estimate_price(fv)

        results.append({
            "pref": item["pref"],
            "city": item["city"],
            "lat": item["lat"],
            "lng": item["lng"],
            "predicted_price": pred.get("median"),
            "ci95": pred.get("ci95"),
            "raw": item,
        })

    return results


# =========================
# handler / CLI エントリ
# =========================

def handler(event=None, context=None) -> Dict[str, Any]:
    """
    サーバレス / API 用エントリーポイント想定。
    """
    year = 2024
    quarter = 4

    data = estimate_all_japan(year=year, quarter=quarter)

    return {
        "status": "ok",
        "count": len(data),
        "data": data,
    }


if __name__ == "__main__":
    # ローカル実行用：結果を JSON に保存
    result = handler()
    with open("japan_estimated_prices.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"saved: japan_estimated_prices.json (count={result['count']})")
