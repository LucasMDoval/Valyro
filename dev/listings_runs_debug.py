# AVISO: script legacy de análisis / debug.
# Puede quedar desfasado respecto a analytics.market_core y la web.
# Úsalo solo como herramienta de desarrollo.


import argparse
from collections import Counter

from utils.db import get_connection, DB_PATH


def main():
    parser = argparse.ArgumentParser(
        description="Debug: cuántas veces aparece cada anuncio (external_id) para un keyword."
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacta usada al guardar (ej. 'iphone 12')",
    )
    args = parser.parse_args()
    keyword = args.keyword

    if not DB_PATH.is_file():
        print(f"No existe la base de datos: {DB_PATH}")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT external_id
        FROM products
        WHERE keyword = ?;
        """,
        (keyword,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print(f"No hay registros para keyword = '{keyword}'.")
        return

    ids = [r[0] for r in rows]
    contador = Counter(ids)

    print(f"\nKeyword: '{keyword}'")
    print(f"Total filas en products: {len(ids)}")
    print(f"Total external_id únicos: {len(contador)}")

    # Distribución de cuántas veces aparece cada external_id
    apariciones = Counter(contador.values())

    print("\nVeces que aparece cada external_id (n_runs) -> nº de anuncios")
    for n_runs in sorted(apariciones.keys()):
        print(f"  {n_runs:2d} run(s): {apariciones[n_runs]:4d} anuncios")

    # Top 10 anuncios que más se repiten
    print("\nTop 10 external_id con más apariciones:")
    for ext_id, n in contador.most_common(10):
        print(f"  {ext_id}: {n} runs")


if __name__ == "__main__":
    main()
