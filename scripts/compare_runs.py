# Nota: script CLI de desarrollo / análisis.
# Toda la lógica de negocio viene de analytics.market_core.


import argparse
from datetime import datetime
from typing import List, Tuple, Dict, Any

from analytics.market_core import (
    fetch_runs_for_keyword,
    fetch_prices_for_run,
    calcular_stats_precios,
)


def comparar_runs(keyword: str) -> List[Tuple[str, Dict[str, float]]]:
    """
    Devuelve una lista de:
        [(scraped_at, stats_dict), ...]
    ordenados de más reciente a más antiguo.
    """
    runs = fetch_runs_for_keyword(keyword)
    if not runs:
        return []

    comparacion = []
    for scraped_at, _, _, _, _ in runs:
        precios = fetch_prices_for_run(keyword, scraped_at)
        stats = calcular_stats_precios(precios)
        if stats:
            comparacion.append((scraped_at, stats))

    return comparacion


def imprimir_comparacion(keyword: str, comp: List[Tuple[str, Dict[str, float]]]):
    print(f"\n=== COMPARACIÓN DE RUNS — '{keyword}' ===")

    if len(comp) < 2:
        print("No hay suficientes runs en la BD para comparar (mínimo 2).")
        return

    print(f"\nTotal de runs encontradas: {len(comp)}")
    print("Orden: más reciente → más antigua\n")

    # Mostrar tabla simple
    print(f"{'Fecha':25s} | {'Media':>8s} | {'Mediana':>8s} | {'Mín':>6s} | {'Máx':>6s}")
    print("-" * 70)
    for scraped_at, stats in comp:
        print(
            f"{scraped_at:25s} | "
            f"{stats['media']:8.2f} | "
            f"{stats['mediana']:8.2f} | "
            f"{stats['minimo']:6.2f} | "
            f"{stats['maximo']:6.2f}"
        )

    # Comparación entre las dos más recientes
    newest, prev = comp[0], comp[1]

    print("\n--- Diferencia entre las 2 últimas runs ---")

    s_new = newest[1]
    s_old = prev[1]

    diff_media = s_new["media"] - s_old["media"]
    pct_media = (diff_media / s_old["media"] * 100) if s_old["media"] else 0

    diff_mediana = s_new["mediana"] - s_old["mediana"]
    pct_mediana = (diff_mediana / s_old["mediana"] * 100) if s_old["mediana"] else 0

    print(
        f"Precio medio:   {s_old['media']:.2f} → {s_new['media']:.2f} "
        f"({diff_media:+.2f}, {pct_media:+.1f} %)"
    )
    print(
        f"Mediana:         {s_old['mediana']:.2f} → {s_new['mediana']:.2f} "
        f"({diff_mediana:+.2f}, {pct_mediana:+.1f} %)"
    )

    print("\nInterpretación rápida:")
    if abs(pct_media) < 3 and abs(pct_mediana) < 3:
        print("  → Mercado ESTABLE.")
    elif pct_media > 0 and pct_mediana > 0:
        print("  → Mercado en SUBIDA.")
    elif pct_media < 0 and pct_mediana < 0:
        print("  → Mercado en BAJADA.")
    else:
        print("  → Movimiento mixto o dispersión.")


def main():
    parser = argparse.ArgumentParser(
        description="Compara todas las runs de un keyword usando datos en BD."
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacto usado al guardar en la BD.",
    )

    args = parser.parse_args()

    comp = comparar_runs(args.keyword)
    if not comp:
        print(f"No hay datos en BD para keyword '{args.keyword}'.")
        return

    imprimir_comparacion(args.keyword, comp)


if __name__ == "__main__":
    main()
