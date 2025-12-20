# scripts/delete_scrapes.py

import argparse
from typing import List, Tuple

from analytics.market_core import fetch_runs_for_keyword
from storage.db import DB_PATH, delete_run, delete_all_for_keyword

RunRow = Tuple[str, int, float, float, float]  # (scraped_at, n_items, avg, min, max)


def listar_runs(keyword: str) -> List[RunRow]:
    """
    Devuelve las runs en orden de más reciente a más antigua
    usando el núcleo de analytics.
    """
    runs = fetch_runs_for_keyword(keyword)
    return runs or []


def imprimir_runs(keyword: str, runs: List[RunRow]) -> None:
    print(f"\nRuns disponibles para keyword = '{keyword}':")
    if not runs:
        print("  (no hay runs en la BD para este keyword)")
        return

    print(f"{'Idx':>3s} | {'Fecha scraped_at':25s} | {'Anuncios':>8s} | {'Media':>8s}")
    print("-" * 60)
    for idx, (scraped_at, n_items, avg_price, _, _) in enumerate(runs):
        print(f"{idx:3d} | {scraped_at:25s} | {n_items:8d} | {avg_price:8.2f}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Elimina scrapes (runs) de la base de datos para un keyword."
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacta usada al guardar en la BD (ej. 'iphone 12 128gb').",
    )
    parser.add_argument(
        "--scraped_at",
        help="Valor scraped_at (ISO) de la run a eliminar. Si no se indica, se mostrará una lista para elegir.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Si se indica, elimina TODOS los datos de ese keyword en la BD.",
    )

    args = parser.parse_args()
    keyword = args.keyword

    if not DB_PATH.is_file():
        print(f"No existe la base de datos: {DB_PATH}")
        return 1

    if args.all:
        total = delete_all_for_keyword(keyword)
        print(f"\nSe han eliminado {total} filas de la BD para keyword = '{keyword}'.")
        return 0

    runs = listar_runs(keyword)
    if not runs:
        print(f"\nNo hay runs en la BD para keyword = '{keyword}'.")
        return 0

    # Si nos pasan scraped_at directamente, borramos esa
    if args.scraped_at:
        scraped_at_target = args.scraped_at.strip()
        # Comprobamos que existe
        existing = {r[0] for r in runs}
        if scraped_at_target not in existing:
            print(f"\nscraped_at='{scraped_at_target}' no encontrado para keyword='{keyword}'.")
            imprimir_runs(keyword, runs)
            return 1

        deleted = delete_run(keyword, scraped_at_target)
        print(
            f"\nEliminada run '{scraped_at_target}' para keyword='{keyword}'. "
            f"Filas borradas: {deleted}"
        )
        return 0

    # Modo interactivo: mostramos lista y pedimos índice
    imprimir_runs(keyword, runs)
    try:
        idx_str = input(
            "\nIntroduce el índice (Idx) de la run que quieres eliminar "
            "(o Enter para cancelar): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nOperación cancelada.")
        return 1

    if not idx_str:
        print("Operación cancelada.")
        return 0

    try:
        idx = int(idx_str)
    except ValueError:
        print("Índice no válido.")
        return 1

    if idx < 0 or idx >= len(runs):
        print("Índice fuera de rango.")
        return 1

    scraped_at_target = runs[idx][0]
    confirm = input(
        f"\nVas a eliminar la run '{scraped_at_target}' para '{keyword}'. "
        "¿Seguro? [s/N]: "
    ).strip().lower()

    if confirm not in ("s", "si", "sí", "y", "yes"):
        print("Operación cancelada.")
        return 0

    deleted = delete_run(keyword, scraped_at_target)
    print(
        f"\nEliminada run '{scraped_at_target}' para keyword='{keyword}'. "
        f"Filas borradas: {deleted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
