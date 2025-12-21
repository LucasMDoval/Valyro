# AVISO: script legacy de análisis / debug.
# Puede quedar desfasado respecto a analytics.market_core y la web.
# Úsalo solo como herramienta de desarrollo.


import argparse
from datetime import datetime
import statistics
from typing import List, Dict, Any, Optional, Tuple

from utils.db import get_connection, DB_PATH


def parse_scraped_at(value: str) -> Optional[datetime]:
    """
    scraped_at lo guardas como datetime.utcnow().isoformat().
    Lo parseamos como ISO.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def fetch_rows_for_keyword(keyword: str) -> List[Tuple[str, float, str]]:
    """
    Devuelve (external_id, price, scraped_at) para un keyword.
    """
    if not DB_PATH.is_file():
        print(f"No existe la base de datos: {DB_PATH}")
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


def build_listings(rows: List[Tuple[str, float, str]]) -> List[Dict[str, Any]]:
    """
    A partir de (external_id, price, scraped_at) construye una lista de anuncios:

    [
      {
        "external_id": ...,
        "price": ... (media),
        "first_seen": datetime,
        "last_seen": datetime,
        "n_runs": int,
      },
      ...
    ]
    """
    by_id: Dict[str, Dict[str, Any]] = {}

    for external_id, price, scraped_at_str in rows:
        dt = parse_scraped_at(scraped_at_str)
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


def annotate_status_and_lifetime(listings: List[Dict[str, Any]]) -> None:
    """
    Añade a cada listing:
      - "lifetime_days": (last_seen - first_seen) en días (float)
      - "status": "ACTIVO" (si last_seen es el último scrape global) o "DESAPARECIDO"
    """
    if not listings:
        return

    # Último scraped_at entre todos los anuncios
    max_last_seen = max(l["last_seen"] for l in listings)

    for l in listings:
        delta = l["last_seen"] - l["first_seen"]
        lifetime_days = delta.total_seconds() / 86400.0
        if lifetime_days < 0:
            lifetime_days = 0.0

        l["lifetime_days"] = lifetime_days
        l["status"] = "ACTIVO" if l["last_seen"] == max_last_seen else "DESAPARECIDO"


def calcular_cuartiles_precios(listings: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Calcula Q1, Q2, Q3 de precios sobre una lista de listings.
    """
    precios = [l["price"] for l in listings]
    if len(precios) < 4:
        return None, None, None
    q1, q2, q3 = statistics.quantiles(precios, n=4)
    return q1, q2, q3


def segmentar_por_precio(listings: List[Dict[str, Any]], q1: float, q2: float, q3: float):
    """
    Segmenta listings en cuatro grupos por precio:
      - barato   : price < q1
      - normal1  : q1 <= price < q2
      - normal2  : q2 <= price <= q3
      - caro     : price > q3
    """
    segmentos = {
        "barato": [],
        "normal1": [],
        "normal2": [],
        "caro": [],
    }

    for l in listings:
        p = l["price"]
        if p < q1:
            segmentos["barato"].append(l)
        elif p < q2:
            segmentos["normal1"].append(l)
        elif p <= q3:
            segmentos["normal2"].append(l)
        else:
            segmentos["caro"].append(l)

    return segmentos


def stats_lifetime(listings: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """
    Calcula estadísticas de lifetime_days para una lista de listings.
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


def imprimir_segmento(nombre: str, etiqueta_precio: str, desaparecidos: List[Dict[str, Any]], activos: List[Dict[str, Any]]):
    print(f"\n=== SEGMENTO: {nombre} ({etiqueta_precio}) ===")

    stats = stats_lifetime(desaparecidos)
    total_desap = len(desaparecidos)
    total_act = len(activos)
    total = total_desap + total_act

    print(f"Anuncios totales en el segmento:    {total}")
    print(f"  - Desaparecidos (posible venta):  {total_desap}")
    print(f"  - Activos (siguen apareciendo):   {total_act}")

    if total > 0:
        pct_desap = (total_desap / total) * 100
        print(f"Porcentaje desaparecidos:           {pct_desap:5.1f} %")
    else:
        print("Porcentaje desaparecidos:           N/A (sin anuncios)")

        if not stats:
            print("Sin datos suficientes de lifetime para desaparecidos.")
        return

    # stats['...'] están en días; calculamos también en horas
    media_d = stats["media"]
    mediana_d = stats["mediana"]
    minimo_d = stats["minimo"]
    maximo_d = stats["maximo"]

    media_h = media_d * 24
    mediana_h = mediana_d * 24
    minimo_h = minimo_d * 24
    maximo_h = maximo_d * 24

    print("\nLifetime (sólo desaparecidos):")
    print(f"  - Media:   {media_d:.2f} días  (~{media_h:.1f} h)")
    print(f"  - Mediana: {mediana_d:.2f} días  (~{mediana_h:.1f} h)")
    print(f"  - Mínimo:  {minimo_d:.2f} días  (~{minimo_h:.1f} h)")
    print(f"  - Máximo:  {maximo_d:.2f} días  (~{maximo_h:.1f} h)")



def main():
    parser = argparse.ArgumentParser(
        description=(
            "Estima la 'velocidad de salida' de anuncios para un keyword, "
            "agrupando por segmentos de precio."
        )
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacta usada al guardar (ej. 'iphone 12 128gb')",
    )

    args = parser.parse_args()
    keyword = args.keyword

    rows = fetch_rows_for_keyword(keyword)
    if not rows:
        print(f"No hay datos en BD para keyword = '{keyword}'.")
        return

    listings = build_listings(rows)
    if not listings:
        print("No se han podido construir listings con scraped_at válidos.")
        return

    annotate_status_and_lifetime(listings)

    # Separamos desaparecidos vs activos
    desaparecidos = [l for l in listings if l["status"] == "DESAPARECIDO"]
    activos = [l for l in listings if l["status"] == "ACTIVO"]

    print(f"\nKeyword: '{keyword}'")
    print(f"Total anuncios únicos (por external_id): {len(listings)}")
    print(f"  - Desaparecidos: {len(desaparecidos)}")
    print(f"  - Activos      : {len(activos)}")

    if len(desaparecidos) < 4:
        print("\nHay menos de 4 anuncios desaparecidos; no se pueden calcular cuartiles fiables.")
        return

    q1, q2, q3 = calcular_cuartiles_precios(desaparecidos)
    if q1 is None:
        print("\nNo se han podido calcular cuartiles de precio sobre los desaparecidos.")
        return

    print("\nCuartiles de precio (sólo desaparecidos):")
    print(f"  Q1 (25%): {q1:.2f} €")
    print(f"  Q2 (50%): {q2:.2f} €")
    print(f"  Q3 (75%): {q3:.2f} €")

    seg_desap = segmentar_por_precio(desaparecidos, q1, q2, q3)
    seg_act = segmentar_por_precio(activos, q1, q2, q3)

    etiqueta_barato = f"< {q1:.0f} €"
    etiqueta_normal1 = f"{q1:.0f}–{q2:.0f} €"
    etiqueta_normal2 = f"{q2:.0f}–{q3:.0f} €"
    etiqueta_caro = f"> {q3:.0f} €"

    imprimir_segmento("BARATO", etiqueta_barato, seg_desap["barato"], seg_act["barato"])
    imprimir_segmento("NORMAL (parte baja)", etiqueta_normal1, seg_desap["normal1"], seg_act["normal1"])
    imprimir_segmento("NORMAL (parte alta)", etiqueta_normal2, seg_desap["normal2"], seg_act["normal2"])
    imprimir_segmento("CARO", etiqueta_caro, seg_desap["caro"], seg_act["caro"])

    print("\nInterpretación:")
    print(
        "- 'Desaparecidos' = anuncios que ya NO aparecían en el último scrape para este keyword "
        "(pueden ser vendidos, reservados o borrados)."
    )
    print(
        "- Segmentos con alto % de desaparecidos y lifetimes bajos indican zonas de precio donde los anuncios "
        "tienden a salir rápido del mercado."
    )
    print(
        "- Segmentos con bajo % de desaparecidos y lifetimes altos indican zonas donde los anuncios se quedan "
        "mucho tiempo sin desaparecer."
    )
    print()


if __name__ == "__main__":
    main()
