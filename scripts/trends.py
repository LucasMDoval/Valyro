# Nota: script CLI de desarrollo / análisis.
# Toda la lógica de negocio viene de analytics.market_core.


import argparse
from datetime import datetime
from typing import List, Tuple, Dict, Any

from analytics.market_core import fetch_runs_for_keyword


RunRow = Tuple[str, int, float, float, float]


def obtener_tendencias(keyword: str) -> List[RunRow]:
    """
    Devuelve las runs para un keyword ordenadas de MÁS ANTIGUA a MÁS RECIENTE.

    Cada run es:
        (scraped_at, n_items, avg_price, min_price, max_price)
    """
    runs_desc = fetch_runs_for_keyword(keyword)  # DESC (más reciente primero)
    runs_asc = list(reversed(runs_desc))         # ASC (más antigua primero)
    return runs_asc


def imprimir_tendencias(keyword: str, runs: List[RunRow]) -> None:
    if not runs:
        print(f"No hay datos en BD para keyword = '{keyword}'.")
        return

    print(f"\n=== TENDENCIAS DE PRECIO — '{keyword}' ===")
    print(f"Total de runs: {len(runs)}\n")

    print(f"{'Fecha':25s} | {'Anuncios':>8s} | {'Media':>8s} | {'Mín':>6s} | {'Máx':>6s}")
    print("-" * 70)
    for scraped_at, n_items, avg_price, min_price, max_price in runs:
        print(
            f"{scraped_at:25s} | "
            f"{n_items:8d} | "
            f"{avg_price:8.2f} | "
            f"{min_price:6.2f} | "
            f"{max_price:6.2f}"
        )

    if len(runs) < 2:
        print("\n(No hay suficientes runs para analizar tendencia.)")
        return

    # Comparamos primera (más antigua) y última (más reciente)
    scraped_old, n_old, avg_old, _, _ = runs[0]
    scraped_new, n_new, avg_new, _, _ = runs[-1]

    diff = avg_new - avg_old
    pct = (diff / avg_old * 100) if avg_old else 0.0

    print("\n--- Resumen de tendencia (precio medio) ---")
    print(f"Primera run: {scraped_old} → media {avg_old:.2f} €")
    print(f"Última run:  {scraped_new} → media {avg_new:.2f} €")
    print(f"Diferencia:  {diff:+.2f} € ({pct:+.1f} %)")

    print("\nInterpretación rápida:")
    if abs(pct) < 3:
        print("  → Mercado bastante ESTABLE en el período analizado.")
    elif pct > 0:
        print("  → Mercado en SUBIDA clara (los precios medios han subido).")
    else:
        print("  → Mercado en BAJADA clara (los precios medios han bajado).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Muestra la tendencia de precios para un keyword a lo largo del tiempo."
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacto usado al guardar en la BD.",
    )

    args = parser.parse_args()
    keyword = args.keyword

    runs = obtener_tendencias(keyword)
    imprimir_tendencias(keyword, runs)


if __name__ == "__main__":
    main()
