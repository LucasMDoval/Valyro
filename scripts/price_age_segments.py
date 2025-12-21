# AVISO: script legacy de análisis / debug.
# Puede quedar desfasado respecto a analytics.market_core y la web.
# Úsalo solo como herramienta de desarrollo.


import argparse
from datetime import datetime, timezone
import statistics
from typing import List, Tuple, Optional

from utils.db import get_connection, DB_PATH


def parse_created_at(value) -> Optional[datetime]:
    """
    Intenta interpretar created_at_api en varios formatos posibles:
    - entero/float epoch (segundos o milisegundos)
    - string ISO-8601 (2025-11-21T17:00:00Z, 2025-11-21T17:00:00, etc.)

    Devuelve datetime en UTC o None si no se puede parsear.
    """
    if value is None:
        return None

    # Epoch numérico
    if isinstance(value, (int, float)):
        ts = float(value)
        # Si parece milisegundos, lo pasamos a segundos
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None

    # Cadena de texto
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return None

        # Quitar sufijo Z si lo tiene
        if v.endswith("Z"):
            v = v[:-1]

        # Intentar ISO directo
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(v, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        # Último intento: fromisoformat "a pelo"
        try:
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    return None


def parse_scraped_at(value: str) -> Optional[datetime]:
    """
    scraped_at lo guardas como datetime.utcnow().isoformat().
    Lo parseamos como ISO y lo ponemos en UTC.
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_price_age_for_keyword(keyword: str) -> List[Tuple[float, float]]:
    """
    Devuelve una lista de (precio, edad_dias) para un keyword:

    edad_dias = (scraped_at - created_at_api).days + fracción
    """
    if not DB_PATH.is_file():
        print(f"No existe la base de datos: {DB_PATH}")
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT price, created_at_api, scraped_at
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL
          AND created_at_api IS NOT NULL;
        """,
        (keyword,),
    )
    rows = cur.fetchall()
    conn.close()

    resultados: List[Tuple[float, float]] = []
    for price, created_at_raw, scraped_at_raw in rows:
        dt_created = parse_created_at(created_at_raw)
        dt_scraped = parse_scraped_at(scraped_at_raw)
        if not dt_created or not dt_scraped:
            continue

        # Edad en días como float
        delta = dt_scraped - dt_created
        edad_dias = delta.total_seconds() / 86400.0
        if edad_dias < 0:
            # Si por lo que sea la fecha viene rara, la ignoramos
            continue

        resultados.append((float(price), edad_dias))

    return resultados


def calcular_cuartiles(precios: List[float]):
    """
    Devuelve (q1, q2, q3) o None si no hay suficientes datos.
    """
    if len(precios) < 4:
        return None, None, None
    q1, q2, q3 = statistics.quantiles(precios, n=4)
    return q1, q2, q3


def agrupar_por_segmentos(price_age: List[Tuple[float, float]]):
    """
    Recibe lista de (precio, edad_dias)
    Devuelve:
      - cuartiles (q1, q2, q3)
      - dict con segmentos:
          "barato"   : [(price, edad_dias), ...]  (precio < q1)
          "normal1"  : entre q1 y q2
          "normal2"  : entre q2 y q3
          "caro"     : > q3
    Si no hay suficientes datos para cuartiles, devuelve segmentos vacíos.
    """
    if not price_age or len(price_age) < 4:
        return (None, None, None), {
            "barato": [],
            "normal1": [],
            "normal2": [],
            "caro": [],
        }

    precios = [p for (p, _) in price_age]
    q1, q2, q3 = calcular_cuartiles(precios)
    if q1 is None:
        return (None, None, None), {
            "barato": [],
            "normal1": [],
            "normal2": [],
            "caro": [],
        }

    segmentos = {
        "barato": [],
        "normal1": [],
        "normal2": [],
        "caro": [],
    }

    for price, edad in price_age:
        if price < q1:
            segmentos["barato"].append((price, edad))
        elif price < q2:
            segmentos["normal1"].append((price, edad))
        elif price <= q3:
            segmentos["normal2"].append((price, edad))
        else:
            segmentos["caro"].append((price, edad))

    return (q1, q2, q3), segmentos


def stats_edad(segmento: List[Tuple[float, float]]):
    """
    Dado un segmento [(price, edad), ...], devuelve dict con estadísticas de edad.
    """
    if not segmento:
        return None

    edades = [e for (_, e) in segmento]
    n = len(edades)
    media = sum(edades) / n
    mediana = statistics.median(edades)
    minimo = min(edades)
    maximo = max(edades)

    return {
        "n": n,
        "media": media,
        "mediana": mediana,
        "minimo": minimo,
        "maximo": maximo,
    }


def imprimir_segmento(nombre: str, etiqueta_precio: str, stats: Optional[dict]):
    print(f"\n=== SEGMENTO: {nombre} ({etiqueta_precio}) ===")
    if not stats:
        print("Sin datos suficientes para este segmento.")
        return

    print(f"Anuncios en el segmento: {stats['n']}")
    print(f"Edad media:              {stats['media']:.1f} días")
    print(f"Edad mediana:            {stats['mediana']:.1f} días")
    print(f"Edad mínima:             {stats['minimo']:.1f} días")
    print(f"Edad máxima:             {stats['maximo']:.1f} días")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Analiza, para un keyword, cómo varía la edad de los anuncios según el tramo de precio."
        )
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacta usada al guardar (ej. 'iphone 12 128gb')",
    )

    args = parser.parse_args()
    keyword = args.keyword

    price_age = fetch_price_age_for_keyword(keyword)
    if not price_age:
        print(f"No hay datos con precio + created_at_api para keyword = '{keyword}'.")
        return

    print(f"\nKeyword: '{keyword}'")
    print(f"Total anuncios considerados: {len(price_age)}")

    (q1, q2, q3), segmentos = agrupar_por_segmentos(price_age)
    if q1 is None:
        print("\nNo hay suficientes datos para calcular cuartiles y segmentos de precio.")
        return

    print("\nCuartiles de precio (en EUR):")
    print(f"  Q1 (25%): {q1:.2f} €")
    print(f"  Q2 (50%): {q2:.2f} €")
    print(f"  Q3 (75%): {q3:.2f} €")

    # Etiquetas legibles de cada segmento
    etiqueta_barato = f"< {q1:.0f} €"
    etiqueta_normal1 = f"{q1:.0f}–{q2:.0f} €"
    etiqueta_normal2 = f"{q2:.0f}–{q3:.0f} €"
    etiqueta_caro = f"> {q3:.0f} €"

    stats_barato = stats_edad(segmentos["barato"])
    stats_normal1 = stats_edad(segmentos["normal1"])
    stats_normal2 = stats_edad(segmentos["normal2"])
    stats_caro = stats_edad(segmentos["caro"])

    imprimir_segmento("BARATO", etiqueta_barato, stats_barato)
    imprimir_segmento("NORMAL (parte baja)", etiqueta_normal1, stats_normal1)
    imprimir_segmento("NORMAL (parte alta)", etiqueta_normal2, stats_normal2)
    imprimir_segmento("CARO", etiqueta_caro, stats_caro)

    print("\nInterpretación básica:")
    print(
        "- Segmentos con edad mediana BAJA (~pocos días) suelen ser zonas de precio donde los anuncios son recientes "
        "y hay movimiento."
    )
    print(
        "- Segmentos con edad mediana ALTA (muchos días) indican rangos de precio donde los anuncios se quedan más "
        "tiempo sin moverse."
    )
    print(
        "- Esto no es todavía 'probabilidad de venta', pero ya te da una idea de qué tramos están saturados de "
        "anuncios viejos."
    )
    print()


if __name__ == "__main__":
    main()
