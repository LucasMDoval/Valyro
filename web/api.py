from pathlib import Path
import sys
from typing import Optional, Callable, Any

from flask import Blueprint, jsonify, request

# Aseguramos raíz del proyecto en sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.db import DB_PATH, get_connection
from analytics.market_core import get_last_run_stats, get_sell_speed_summary, fetch_mean_median_series
import subprocess
import sys as _sys


# ==========================
#  CONFIG BÁSICA DE LA API
# ==========================

# Versión actual de la API
API_VERSION = "v1"

# API key muy simple para futuro SaaS.
API_KEY: Optional[str] = None

api_bp = Blueprint("api", __name__)


# ==========================
#  HELPERS COMUNES
# ==========================

def api_error(code: str, message: str, http_status: int = 400):
    payload = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    return jsonify(payload), http_status


def require_api_key(fn: Callable):
    def wrapper(*args: Any, **kwargs: Any):
        if API_KEY is not None:
            sent_key = request.headers.get("X-API-Key")
            if sent_key != API_KEY:
                return api_error("unauthorized", "API key inválida o ausente", 401)
        return fn(*args, **kwargs)

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _load_keywords_from_db():
    if not DB_PATH.is_file():
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT keyword
        FROM products
        ORDER BY keyword;
        """
    )
    rows = cur.fetchall()
    conn.close()

    return [r[0] for r in rows]


def _run_analyze_market(
    keyword: str,
    limit: int,
    order_by: str,
    min_price: Optional[float],
    max_price: Optional[float],
    filter_mode: str,
    exclude_bad_text: bool,
    category_id: Optional[int],
    intent_mode: str,
) -> int:
    # Por requisito: el usuario no puede elegir límite ni orden desde API.
    limit = 500
    order_by = "most_relevance"

    cmd = [
        _sys.executable,
        "-m",
        "scripts.analyze_market",
        keyword,
        "--order_by",
        order_by,
        "--limit",
        str(limit),
        "--save_db",
    ]

    if category_id is not None:
        cmd.extend(["--category_id", str(int(category_id))])

    im = (intent_mode or "any").strip().lower()
    if im not in ("any", "primary", "console", "auto"):
        im = "any"
    if im != "any":
        cmd.extend(["--intent_mode", im])

    fm = (filter_mode or "soft").strip().lower()
    if fm not in ("soft", "strict", "off"):
        fm = "soft"
    cmd.extend(["--filter_mode", fm])
    if not exclude_bad_text:
        cmd.append("--no_text_filter")

    if min_price is not None:
        cmd.extend(["--min_price", str(min_price)])
    if max_price is not None:
        cmd.extend(["--max_price", str(max_price)])

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except Exception:
        return -1


# ==========================
#  ENDPOINTS
# ==========================

@api_bp.get("/keywords")
@require_api_key
def api_list_keywords():
    kws = _load_keywords_from_db()
    return jsonify({"keywords": kws})


@api_bp.get("/keyword/<kw>/stats")
@require_api_key
def api_keyword_stats(kw):
    kw = kw.strip()
    if not kw:
        return api_error("invalid_keyword", "keyword vacío", 400)

    result = get_last_run_stats(kw)
    if not result:
        return api_error("not_found", "No hay datos para ese keyword", 404)

    scraped_at, stats = result

    n = stats["n"]
    media = stats["media"]
    mediana = stats["mediana"]
    minimo = stats["minimo"]
    maximo = stats["maximo"]
    q1 = stats["q1"]
    q2 = stats["q2"]
    q3 = stats["q3"]

    price_ranges = {
        "normal": {"from": q1, "to": q3},
        "fast": {"from": q1, "to": mediana},
        "slow": {"from": mediana, "to": q3},
    }

    sell_speed_raw = get_sell_speed_summary(kw)
    sell_speed = None
    if sell_speed_raw:
        ls = sell_speed_raw.get("lifetime_stats")
        sell_speed = {
            "total_listings": sell_speed_raw["total_listings"],
            "desaparecidos": sell_speed_raw["desaparecidos"],
            "activos": sell_speed_raw["activos"],
            "pct_desaparecidos": sell_speed_raw["pct_desaparecidos"],
            "lifetime_mediana_dias": ls["mediana"] if ls else None,
        }

    payload = {
        "keyword": kw,
        "scraped_at": scraped_at,
        "stats": {
            "n": n,
            "media": media,
            "mediana": mediana,
            "minimo": minimo,
            "maximo": maximo,
            "q1": q1,
            "q2": q2,
            "q3": q3,
        },
        "price_ranges": price_ranges,
        "sell_speed": sell_speed,
    }

    return jsonify(payload)


@api_bp.get("/keyword/<kw>/series")
@require_api_key
def api_keyword_series(kw):
    """
    GET /api/v1/keyword/<kw>/series
    {
      "keyword": "...",
      "series": [
        { "scraped_at": "...", "media": 0.0, "mediana": 0.0 },
        ...
      ]
    }
    """
    kw = kw.strip()
    if not kw:
        return api_error("invalid_keyword", "keyword vacío", 400)

    serie = fetch_mean_median_series(kw)  # { datetime: {media, mediana}, ... }
    if not serie:
        return api_error("not_found", "No hay histórico para ese keyword", 404)

    out = []
    for dt, v in serie.items():
        out.append(
            {
                "scraped_at": dt.isoformat(),
                "media": float(v.get("media", 0.0)),
                "mediana": float(v.get("mediana", 0.0)),
            }
        )

    return jsonify({"keyword": kw, "series": out})


@api_bp.post("/keyword/<kw>/scrape")
@require_api_key
def api_keyword_scrape(kw):
    kw = kw.strip()
    if not kw:
        return api_error("invalid_keyword", "keyword vacío", 400)

    data = request.get_json(silent=True) or {}

    # limit y order_by: ignorados (fijos por requisito)
    limit = 500
    order_by = "most_relevance"
    min_price = data.get("min_price", None)
    max_price = data.get("max_price", None)
    category_id = data.get("category_id", None)
    intent_mode = (data.get("intent_mode") or "any")
    filter_mode = (data.get("filter_mode") or "soft")
    exclude_bad_text = data.get("exclude_bad_text")

    def _parse_int(val):
        if val is None:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    def _parse_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    min_price = _parse_float(min_price)
    max_price = _parse_float(max_price)
    category_id = _parse_int(category_id)
    if category_id is None:
        category_id = 24200

    fm = str(filter_mode).strip().lower()
    if fm not in ("soft", "strict", "off"):
        fm = "soft"
    filter_mode = fm

    im = str(intent_mode).strip().lower()
    if im not in ("any", "primary", "console", "auto"):
        im = "any"
    intent_mode = im

    if isinstance(exclude_bad_text, bool):
        pass
    elif exclude_bad_text is None:
        exclude_bad_text = True
    else:
        exclude_bad_text = str(exclude_bad_text).strip().lower() in ("1", "true", "yes", "on")

    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    rc = _run_analyze_market(kw, limit, order_by, min_price, max_price, filter_mode, bool(exclude_bad_text), category_id, intent_mode)

    if rc != 0:
        return api_error("scrape_failed", "Ha fallado la ejecución interna de analyze_market.", 500)

    return jsonify(
        {
            "keyword": kw,
            "status": "ok",
            "message": "Scrape lanzado y datos guardados en la BD.",
            "limit": 500,
            "order_by": "most_relevance",
            "min_price": min_price,
            "max_price": max_price,
            "category_id": category_id,
            "intent_mode": intent_mode,
            "filter_mode": filter_mode,
            "exclude_bad_text": bool(exclude_bad_text),
        }
    )
