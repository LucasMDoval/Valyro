import argparse
import json
from datetime import datetime
from pathlib import Path

from crawler.wallapop_client import fetch_products


def main():
    parser = argparse.ArgumentParser(description="Scraper Wallapop")
    parser.add_argument("keyword", help="Texto a buscar (ej. 'iphone 12')")

    parser.add_argument(
        "--order_by",
        choices=["most_relevance", "price_low_to_high", "price_high_to_low", "newest"],
        default="most_relevance",
        help=(
            "Orden de resultados en Wallapop: "
            "most_relevance | price_low_to_high | price_high_to_low | newest"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Máximo de productos a recoger (0–1000)",
    )

    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Cadena que debe aparecer en titulo+descripcion (por defecto, keyword)",
    )

    parser.add_argument(
        "--min_price",
        type=float,
        default=None,
        help="Precio mínimo (usado en min_sale_price nativo de Wallapop)",
    )

    parser.add_argument(
        "--max_price",
        type=float,
        default=None,
        help="Precio máximo (usado en max_sale_price nativo de Wallapop)",
    )

    args = parser.parse_args()

    limit = max(0, min(args.limit, 1000))
    substring_filter = args.filter or args.keyword

    min_price = args.min_price
    max_price = args.max_price

    if min_price is not None and max_price is not None and min_price > max_price:
        print(f"Ojo: min_price ({min_price}) > max_price ({max_price}), los intercambio.")
        min_price, max_price = max_price, min_price

    print(
        f"Buscando '{args.keyword}' "
        f"(orden={args.order_by}, límite={limit}, filtro='{substring_filter}', "
        f"min_price={min_price}, max_price={max_price})"
    )

    productos = fetch_products(
        keyword=args.keyword,
        order_by=args.order_by,
        limit=limit,
        substring_filter=substring_filter,
        min_price=min_price,
        max_price=max_price,
    )

    Path("data").mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = args.keyword.replace(" ", "_")
    filename = Path("data") / f"wallapop_{slug}_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)

    if productos:
        print(f"\nGuardados {len(productos)} productos en: {filename}")
    else:
        print(
            f"\nNo se ha guardado ningún producto (0 resultados). "
            f"Archivo creado igualmente: {filename}"
        )


if __name__ == "__main__":
    main()
