# Nota: script CLI de desarrollo / análisis.
# Toda la lógica de negocio viene de analytics.market_core.


import argparse
from pathlib import Path
from typing import List, Tuple
from datetime import datetime
import statistics

import matplotlib.pyplot as plt

from utils.db import get_connection, DB_PATH
from analytics.market_core import fetch_runs_for_keyword, fetch_mean_median_series

PLOTS_DIR = Path("plots")


def fetch_prices_for_keyword(keyword: str) -> List[float]:
    """
    Devuelve TODOS los precios de la BD para un keyword (todas las runs).
    Se usa para el histograma global.
    """
    if not DB_PATH.is_file():
        print(f"No existe la base de datos: {DB_PATH}")
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT price
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL;
        """,
        (keyword,),
    )
    rows = cur.fetchall()
    conn.close()

    return [r[0] for r in rows]


def plot_price_histogram(keyword: str):
    """
    Histograma de TODOS los precios recopilados para un keyword.
    Mezcla todas las runs.
    """
    precios = fetch_prices_for_keyword(keyword)
    if not precios:
        print(f"No hay precios en BD para '{keyword}'.")
        return

    PLOTS_DIR.mkdir(exist_ok=True)
    plt.figure()
    plt.hist(precios, bins=20)
    plt.title(f"Histograma de precios — {keyword}")
    plt.xlabel("Precio (€)")
    plt.ylabel("Número de anuncios")

    outfile = PLOTS_DIR / f"{keyword.replace(' ', '_')}_hist.png"
    plt.tight_layout()
    plt.savefig(outfile)
    print(f"Histograma guardado en: {outfile}")
    plt.show()


def plot_mean_price_over_time(keyword: str):
    """
    Gráfico de la evolución del PRECIO MEDIO por run (scraped_at).
    Usa fetch_runs_for_keyword del núcleo.
    """
    rows = fetch_runs_for_keyword(keyword)
    if not rows:
        print(f"No hay runs en BD para '{keyword}'.")
        return

    scraped_at_str = [r[0] for r in rows]
    avg_prices = [r[2] for r in rows]

    scraped_at_dt = [datetime.fromisoformat(s) for s in scraped_at_str]

    PLOTS_DIR.mkdir(exist_ok=True)
    plt.figure()
    plt.plot(scraped_at_dt, avg_prices, marker="o")
    plt.title(f"Evolución del precio medio — {keyword}")
    plt.xlabel("Fecha de scraping")
    plt.ylabel("Precio medio (€)")
    plt.xticks(rotation=45)

    outfile = PLOTS_DIR / f"{keyword.replace(' ', '_')}_mean_over_time.png"
    plt.tight_layout()
    plt.savefig(outfile)
    print(f"Gráfico de precio medio guardado en: {outfile}")
    plt.show()


def plot_mean_median_over_time(keyword: str):
    """
    Dibuja un gráfico de cómo varían el PRECIO MEDIO y MEDIANO
    a lo largo del tiempo (una run = un scraped_at).

    Reutiliza fetch_mean_median_series de analytics.market_core
    para no duplicar lógica.
    """
    serie = fetch_mean_median_series(keyword)
    if not serie:
        print(f"No hay datos en BD para keyword = '{keyword}'.")
        return

    fechas = sorted(serie.keys())
    medias = [serie[f]["media"] for f in fechas]
    medianas = [serie[f]["mediana"] for f in fechas]

    PLOTS_DIR.mkdir(exist_ok=True)
    plt.figure()
    plt.plot(fechas, medias, marker="o", label="Media")
    plt.plot(fechas, medianas, marker="s", linestyle="--", label="Mediana")
    plt.title(f"Evolución precio medio y mediano — {keyword}")
    plt.xlabel("Fecha de scraping")
    plt.ylabel("Precio (€)")
    plt.xticks(rotation=45)
    plt.legend()

    outfile = PLOTS_DIR / f"{keyword.replace(' ', '_')}_mean_median_over_time.png"
    plt.tight_layout()
    plt.savefig(outfile)
    print(f"Gráfico media/mediana guardado en: {outfile}")
    plt.show()


def plot_boxplot_by_run(keyword: str):
    """
    Boxplot de la distribución de precios por run.

    Aquí todavía tiramos de la BD directa porque necesitamos los precios
    individuales por run; no hace falta duplicar esta función en el núcleo.
    """
    rows = fetch_runs_for_keyword(keyword)
    if not rows:
        print(f"No hay runs en BD para '{keyword}'.")
        return

    if not DB_PATH.is_file():
        print(f"No existe la base de datos: {DB_PATH}")
        return

    conn = get_connection()
    cur = conn.cursor()

    precios_por_run: List[List[float]] = []
    labels: List[str] = []

    for scraped_at, _, _, _, _ in rows:
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
        if precios:
            precios_por_run.append(precios)
            labels.append(scraped_at)

    conn.close()

    if not precios_por_run:
        print("No se han encontrado precios por run para boxplot.")
        return

    PLOTS_DIR.mkdir(exist_ok=True)
    plt.figure()
    plt.boxplot(precios_por_run)
    plt.title(f"Distribución de precios por run — {keyword}")
    plt.xlabel("Run (scraped_at)")
    plt.ylabel("Precio (€)")
    plt.xticks(range(1, len(labels) + 1), labels, rotation=45)

    outfile = PLOTS_DIR / f"{keyword.replace(' ', '_')}_box_by_run.png"
    plt.tight_layout()
    plt.savefig(outfile)
    print(f"Boxplot por run guardado en: {outfile}")
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Plotter de precios a partir de la base de datos"
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacta usada al guardar (ej. 'iphone 12 128gb')",
    )
    parser.add_argument(
        "--kind",
        choices=["hist", "mean", "box", "stats"],
        default="hist",
        help=(
            "Tipo de gráfico: "
            "hist (histograma), "
            "mean (precio medio en el tiempo), "
            "box (boxplot por run), "
            "stats (media y mediana en el tiempo)"
        ),
    )

    args = parser.parse_args()

    if args.kind == "hist":
        plot_price_histogram(args.keyword)
    elif args.kind == "mean":
        plot_mean_price_over_time(args.keyword)
    elif args.kind == "box":
        plot_boxplot_by_run(args.keyword)
    elif args.kind == "stats":
        plot_mean_median_over_time(args.keyword)


if __name__ == "__main__":
    main()
