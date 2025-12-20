from __future__ import annotations

from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import statistics

from storage.db import get_connection, DB_PATH


RunRow = Tuple[str, int, float, float, float]


# ==========================
#  BLOQUE: STATS DE PRECIOS
# ==========================


def fetch_runs_for_keyword(keyword: str) -> List[RunRow]:
    """
    Devuelve las ejecuciones (runs) para un keyword, ordenadas de más reciente a más antigua:

    [(scraped_at, n_items, avg_price, min_price, max_price), ...]
    """
    if not DB_PATH.is_file():
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            scraped_at,
            COUNT(*)              AS n_items,
            AVG(price)            AS avg_price,
            MIN(price)            AS min_price,
            MAX(price)            AS max_price
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL
        GROUP BY scraped_at
        ORDER BY scraped_at DESC;
        """,
        (keyword,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def fetch_prices_for_run(keyword: str, scraped_at: str) -> List[float]:
    """
    Devuelve la lista de precios para un keyword en un scraped_at concreto.
    """
    if not DB_PATH.is_file():
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT price
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL
          AND scraped_at = ?;
        """,
        (keyword, scraped_at),
    )
    precios = [r[0] for r in cur.fetchall()]
    conn.close()
    return precios


def calcular_stats_precios(precios: List[float]) -> Optional[dict]:
    """
    Calcula estadísticas básicas sobre una lista de precios.
    Devuelve dict con:
      n, media, mediana, minimo, maximo, q1, q2, q3
    """
    if not precios:
        return None

    n = len(precios)
    media = sum(precios) / n
    mediana = statistics.median(precios)
    minimo = min(precios)
    maximo = max(precios)

    if len(precios) >= 4:
        q1, q2, q3 = statistics.quantiles(precios, n=4)
    else:
        q1 = q2 = q3 = mediana

    return {
        "n": n,
        "media": media,
        "mediana": mediana,
        "minimo": minimo,
        "maximo": maximo,
        "q1": q1,
        "q2": q2,
        "q3": q3,
    }


def get_last_run_stats(keyword: str) -> Optional[Tuple[str, dict]]:
    """
    Devuelve (scraped_at, stats_dict) para la run más reciente de ese keyword,
    o None si no hay datos suficientes.
    """
    runs = fetch_runs_for_keyword(keyword)
    if not runs:
        return None

    scraped_at_new, _, _, _, _ = runs[0]
    precios_new = fetch_prices_for_run(keyword, scraped_at_new)
    stats = calcular_stats_precios(precios_new)
    if not stats:
        return None

    return scraped_at_new, stats


def fetch_mean_median_series(keyword: str) -> Dict[datetime, Dict[str, float]]:
    """
    Devuelve una serie temporal:
      { fecha_datetime: { 'media': float, 'mediana': float } }
    usando TODAS las runs de ese keyword (orden cronológico).
    """
    if not DB_PATH.is_file():
        return {}

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT scraped_at, price
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL
        ORDER BY scraped_at;
        """,
        (keyword,),
    )
    rows = cur.fetchall()
    conn.close()

    precios_por_run: Dict[str, List[float]] = {}
    for scraped_at, price in rows:
        precios_por_run.setdefault(scraped_at, []).append(price)

    serie: Dict[datetime, Dict[str, float]] = {}
    for scraped_at_str, precios in precios_por_run.items():
        try:
            dt = datetime.fromisoformat(scraped_at_str)
        except Exception:
            continue
        if not precios:
            continue
        media = sum(precios) / len(precios)
        mediana = statistics.median(precios)
        serie[dt] = {"media": media, "mediana": mediana}

    return dict(sorted(serie.items(), key=lambda x: x[0]))


# ==========================================
#  BLOQUE: VELOCIDAD DE SALIDA / LIFETIME
#  (adaptado desde sell_speed.py para uso web)
# ==========================================


def _parse_scraped_at_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _fetch_rows_for_keyword(keyword: str) -> List[Tuple[str, float, str]]:
    """
    Devuelve (external_id, price, scraped_at) para un keyword.
    """
    if not DB_PATH.is_file():
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT external_id, price, scraped_at
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL;
        """,
        (keyword,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def _build_listings(rows: List[Tuple[str, float, str]]) -> List[Dict[str, Any]]:
    """
    A partir de (external_id, price, scraped_at) construye una lista de anuncios únicos:

      [
        {
          "external_id": str,
          "price": float (media),
          "first_seen": datetime,
          "last_seen": datetime,
          "n_runs": int,
        },
        ...
      ]
    """
    by_id: Dict[str, Dict[str, Any]] = {}

    for external_id, price, scraped_at_str in rows:
        dt = _parse_scraped_at_dt(scraped_at_str)
        if not dt:
            continue

        if external_id not in by_id:
            by_id[external_id] = {
                "external_id": external_id,
                "prices": [float(price)],
                "first_seen": dt,
                "last_seen": dt,
                "n_runs": 1,
            }
        else:
            entry = by_id[external_id]
            entry["prices"].append(float(price))
            if dt < entry["first_seen"]:
                entry["first_seen"] = dt
            if dt > entry["last_seen"]:
                entry["last_seen"] = dt
            entry["n_runs"] += 1

    listings: List[Dict[str, Any]] = []
    for entry in by_id.values():
        prices = entry["prices"]
        avg_price = sum(prices) / len(prices)
        listings.append(
            {
                "external_id": entry["external_id"],
                "price": avg_price,
                "first_seen": entry["first_seen"],
                "last_seen": entry["last_seen"],
                "n_runs": entry["n_runs"],
            }
        )

    return listings


def _annotate_status_and_lifetime(listings: List[Dict[str, Any]]) -> None:
    """
    Añade a cada listing:
      - lifetime_days: (last_seen - first_seen) en días (float)
      - status: "ACTIVO" (si last_seen es el último scrape global) o "DESAPARECIDO"
    """
    if not listings:
        return

    max_last_seen = max(l["last_seen"] for l in listings)

    for l in listings:
        delta = l["last_seen"] - l["first_seen"]
        lifetime_days = delta.total_seconds() / 86400.0
        if lifetime_days < 0:
            lifetime_days = 0.0

        l["lifetime_days"] = lifetime_days
        l["status"] = "ACTIVO" if l["last_seen"] == max_last_seen else "DESAPARECIDO"


def _stats_lifetime(listings: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """
    Stats de lifetime_days sobre una lista de listings.
    """
    if not listings:
        return None

    lifetimes = [l["lifetime_days"] for l in listings]
    n = len(lifetimes)
    media = sum(lifetimes) / n
    mediana = statistics.median(lifetimes)
    minimo = min(lifetimes)
    maximo = max(lifetimes)

    return {
        "n": n,
        "media": media,
        "mediana": mediana,
        "minimo": minimo,
        "maximo": maximo,
    }


def get_sell_speed_summary(keyword: str) -> Optional[dict]:
    """
    Devuelve un resumen compacto de 'velocidad de salida' para un keyword:

      {
        "total_listings": int,
        "desaparecidos": int,
        "activos": int,
        "pct_desaparecidos": float,        # 0–100
        "lifetime_stats": { ... } or None  # stats de lifetime sobre desaparecidos
      }
    """
    rows = _fetch_rows_for_keyword(keyword)
    if not rows:
        return None

    listings = _build_listings(rows)
    if not listings:
        return None

    _annotate_status_and_lifetime(listings)

    desaparecidos = [l for l in listings if l["status"] == "DESAPARECIDO"]
    activos = [l for l in listings if l["status"] == "ACTIVO"]

    total = len(listings)
    total_desap = len(desaparecidos)
    total_act = len(activos)
    pct_desap = (total_desap / total * 100.0) if total else 0.0

    lifetime_stats = _stats_lifetime(desaparecidos)

    return {
        "total_listings": total,
        "desaparecidos": total_desap,
        "activos": total_act,
        "pct_desaparecidos": pct_desap,
        "lifetime_stats": lifetime_stats,
    }
