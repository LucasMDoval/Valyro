# AVISO: script legacy de análisis / debug.
# Puede quedar desfasado respecto a analytics.market_core y la web.
# Úsalo solo como herramienta de desarrollo.


import argparse
from pathlib import Path

from storage.db import get_connection, DB_PATH


def mostrar_resumen_keyword(keyword: str, limit: int):
    if not DB_PATH.is_file():
        print(f"No existe la base de datos: {DB_PATH}")
        return

    conn = get_connection()
    cur = conn.cursor()

    # Resumen general para ese keyword
    cur.execute(
        """
        SELECT
            COUNT(*)                AS n,
            AVG(price)              AS media,
            MIN(price)              AS min_price,
            MAX(price)              AS max_price
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL;
        """,
        (keyword,),
    )
    row = cur.fetchone()
    n, media, min_price, max_price = row

    if not n:
        print(f"No hay registros para keyword = '{keyword}' en la BD.")
        return

    print(f"\n=== RESUMEN EN BD PARA: '{keyword}' ===")
    print(f"Total anuncios con precio:   {n}")
    print(f"Precio medio:                {media:.2f} €")
    print(f"Mínimo:                      {min_price:.2f} €")
    print(f"Máximo:                      {max_price:.2f} €")

    # Últimas ejecuciones (scraped_at distintos)
    cur.execute(
        """
        SELECT scraped_at, COUNT(*) AS n_items, AVG(price) AS media_price
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL
        GROUP BY scraped_at
        ORDER BY scraped_at DESC
        LIMIT 5;
        """,
        (keyword,),
    )
    runs = cur.fetchall()

    print("\nÚltimas ejecuciones guardadas para este keyword:")
    for scraped_at, n_items, media_price in runs:
        print(
            f"  {scraped_at}  ->  {n_items} anuncios, "
            f"media {media_price:.2f} €"
        )

    # Muestras concretas
    cur.execute(
        """
        SELECT
            price,
            city,
            title,
            url,
            scraped_at
        FROM products
        WHERE keyword = ?
          AND price IS NOT NULL
        ORDER BY scraped_at DESC, price ASC
        LIMIT ?;
        """,
        (keyword, limit),
    )
    rows = cur.fetchall()

    print(f"\n=== MUESTRA (hasta {limit} anuncios) ===")
    for price, city, title, url, scraped_at in rows:
        ciudad_txt = city or "Sin ciudad"
        url_txt = f" — {url}" if url else ""
        print(
            f"[{scraped_at}] {price:7.2f} € — {ciudad_txt:20} — "
            f"{title[:60]}{url_txt}"
        )

    conn.close()
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Consulta rápida de la base de datos de Valyro"
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacta con la que se guardaron los productos (ej. 'iphone 12 128gb')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Máximo de anuncios a mostrar en la muestra",
    )

    args = parser.parse_args()

    mostrar_resumen_keyword(args.keyword, args.limit)


if __name__ == "__main__":
    main()
