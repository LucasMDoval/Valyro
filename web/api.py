from pathlib import Path
import sys
from typing import Optional, Callable, Any

from flask import Blueprint, jsonify, request

# Aseguramos raíz del proyecto en sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.db import DB_PATH, get_connection
from analytics.market_core import get_last_run_stats, get_sell_speed_summary
import subprocess
import sys as _sys


# ==========================
#  CONFIG BÁSICA DE LA API
# ==========================

# Versión actual de la API
API_VERSION = "v1"

# API key muy simple para futuro SaaS.
# De momento la dejamos a None → NO se exige.
# Cuando quieras protegerla:
#   - pon aquí una cadena, o
#   - léela de un fichero de config / variable de entorno.
API_KEY: Optional[str] = None

api_bp = Blueprint("api", __name__)


# ==========================
#  HELPERS COMUNES
# ==========================

def api_error(code: str, message: str, http_status: int = 400):
    """
    Respuesta de error estándar:
    {
      "error": {
        "code": "string",
        "message": "texto"
      }
    }
    """
    payload = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    return jsonify(payload), http_status


def require_api_key(fn: Callable):
    """
    Decorador MUY sencillo de API key.

    - Si API_KEY es None -> no hace nada (auth desactivada).
    - Si API_KEY tiene valor -> exige header 'X-API-Key' igual a API_KEY.
    """
    def wrapper(*args: Any, **kwargs: Any):
        if API_KEY is not None:
            sent_key = request.headers.get("X-API-Key")
            if sent_key != API_KEY:
                return api_error("unauthorized", "API key inválida o ausente", 401)
        return fn(*args, **kwargs)

    # Mantener nombre y docstring para Flask
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _load_keywords_from_db():
    """
    Lista de keywords distintos que hay en la BD.
    """
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
) -> int:
    """
    Lanza scripts.analyze_market como hace la web.
    Siempre con --save_db.
    """
    if limit <= 0:
        limit = 50
    if limit > 1000:
        limit = 1000

    allowed_orders = {
        "most_relevance",
        "price_low_to_high",
        "price_high_to_low",
        "newest",
    }
    if order_by not in allowed_orders:
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
    """
    GET /api/v1/keywords
    Devuelve: { "keywords": ["iphone 12", "ps5", ...] }
    """
    kws = _load_keywords_from_db()
    return jsonify({"keywords": kws})


@api_bp.get("/keyword/<kw>/stats")
@require_api_key
def api_keyword_stats(kw):
    """
    GET /api/v1/keyword/<kw>/stats

    Devuelve stats de la última run, rangos de precio y velocidad de salida:
    {
      "keyword": "...",
      "scraped_at": "...",
      "stats": {...},
      "price_ranges": {...},
      "sell_speed": {...} | null
    }
    """
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


@api_bp.post("/keyword/<kw>/scrape")
@require_api_key
def api_keyword_scrape(kw):
    """
    POST /api/v1/keyword/<kw>/scrape
    Body JSON opcional:
      {
        "limit": 300,
        "order_by": "most_relevance" | "price_low_to_high" | "price_high_to_low" | "newest",
        "min_price": 50,
        "max_price": 400
      }
    """
    kw = kw.strip()
    if not kw:
        return api_error("invalid_keyword", "keyword vacío", 400)

    data = request.get_json(silent=True) or {}

    limit = data.get("limit", 300)
    order_by = data.get("order_by", "most_relevance")
    min_price = data.get("min_price", None)
    max_price = data.get("max_price", None)

    # Normalizamos tipos
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return api_error("invalid_limit", "limit debe ser un entero", 400)

    def _parse_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    min_price = _parse_float(min_price)
    max_price = _parse_float(max_price)

    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        min_price, max_price = max_price, min_price

    rc = _run_analyze_market(kw, limit, order_by, min_price, max_price)

    if rc != 0:
        return api_error(
            "scrape_failed",
            "Ha fallado la ejecución interna de analyze_market.",
            500,
        )

    return jsonify(
        {
            "keyword": kw,
            "status": "ok",
            "message": "Scrape lanzado y datos guardados en la BD.",
            "limit": limit,
            "order_by": order_by,
            "min_price": min_price,
            "max_price": max_price,
        }
    )
