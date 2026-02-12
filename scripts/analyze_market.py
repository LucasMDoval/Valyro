from pathlib import Path
import sys
import json
import argparse
from datetime import datetime
import statistics

# Aseguramos que la raíz del proyecto está en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.wallapop_client import fetch_products
from utils.db import save_products
from utils.listing_filters import apply_listing_filters


def calcular_estadisticas(productos):
    precios = [p["precio"] for p in productos if p.get("precio") is not None]
    if not precios:
        return None, None

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
    }, precios


def imprimir_resumen(stats, productos, precios):
    n = stats["n"]
    media = stats["media"]
    mediana = stats["mediana"]
    minimo = stats["minimo"]
    maximo = stats["maximo"]
    q1 = stats["q1"]
    q2 = stats["q2"]
    q3 = stats["q3"]

    print("\n=== RESUMEN DE MERCADO ===")
    print(f"Anuncios analizados con precio válido: {n}")
    print(f"Precio medio:        {media:.2f} €")
    print(f"Mediana:             {mediana:.2f} €")
    print(f"Mínimo:              {minimo:.2f} €")
    print(f"Máximo:              {maximo:.2f} €")
    print(f"Q1 (25%):            {q1:.2f} €")
    print(f"Q2 / mediana:        {q2:.2f} €")
    print(f"Q3 (75%):            {q3:.2f} €")

    def etiqueta(p):
        if p < q1:
            return "barato"
        elif p > q3:
            return "caro"
        return "normal"

    conteo = {"barato": 0, "normal": 0, "caro": 0}
    for p in precios:
        conteo[etiqueta(p)] += 1

    print("\nDistribución por tramos:")
    total = sum(conteo.values())
    for k in ["barato", "normal", "caro"]:
        v = conteo[k]
        pct = (v / total) * 100 if total else 0
        print(f"  {k:7}: {v:4d} anuncios ({pct:5.1f}%)")

    print("\n=== RECOMENDACIÓN DE PRECIO ===")
    print(f"- Rango razonable para anunciar: ~{q1:.0f}–{q3:.0f} € (zona 'normal')")
    print(f"- Para vender relativamente rápido: ~{q1:.0f}–{mediana:.0f} €")
    print(f"- Más margen (asumiendo tardar más): ~{mediana:.0f}–{q3:.0f} €")

    productos_ordenados = sorted(
        [p for p in productos if p.get("precio") is not None],
        key=lambda p: p["precio"],
    )

    print("\nTop 5 más baratos:")
    for p in productos_ordenados[:5]:
        print(f"  {p['precio']:7.2f} € — {p['titulo'][:60]}" + (f" — {p['url']}" if p.get("url") else ""))

    print("\nTop 5 más caros:")
    for p in productos_ordenados[-5:]:
        print(f"  {p['precio']:7.2f} € — {p['titulo'][:60]}" + (f" — {p['url']}" if p.get("url") else ""))

    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape + análisis de mercado Wallapop en un solo paso")
    parser.add_argument("keyword", help="Texto a buscar (ej. 'iphone 12 128gb')")

    parser.add_argument(
        "--order_by",
        choices=["most_relevance", "price_low_to_high", "price_high_to_low", "newest"],
        default="most_relevance",
    )
    parser.add_argument("--limit", type=int, default=300, help="Máximo de productos a recoger (0–1000)")
    parser.add_argument("--filter", type=str, default=None, help="(OPCIONAL) tokens que deben aparecer en titulo+descripcion")
    parser.add_argument("--min_price", type=float, default=None, help="Precio mínimo")
    parser.add_argument("--max_price", type=float, default=None, help="Precio máximo")
    parser.add_argument("--save_raw", action="store_true", help="Guarda JSON crudo en data/")
    parser.add_argument("--save_db", action="store_true", help="Guarda en SQLite")

    # Filtros (recomendado en Wallapop)
    parser.add_argument(
        "--filter_mode",
        choices=["soft", "strict", "off"],
        default="soft",
        help="Preset de limpieza de precios: soft (recomendado), strict, off",
    )
    parser.add_argument(
        "--no_text_filter",
        action="store_true",
        help="No excluye anuncios rotos/para piezas/solo caja/busco/etc.",
    )

    parser.add_argument("--headless", action="store_true", help="Ejecuta navegador en modo headless")
    parser.add_argument("--strict", action="store_true", help="Si no hay señales de JSON con items, falla con exit code != 0")

    args = parser.parse_args()

    limit = max(0, min(args.limit, 1000))

    # ⚠️ IMPORTANTE: NO autofiltrar por keyword (Wallapop ya filtra por keyword).
    # Solo filtra si el usuario pasa --filter
    substring_filter = args.filter

    min_price = args.min_price
    max_price = args.max_price

    if min_price is not None and max_price is not None and min_price > max_price:
        print(f"Ojo: min_price ({min_price}) > max_price ({max_price}), los intercambio.")
        min_price, max_price = max_price, min_price

    print(
        f"Buscando '{args.keyword}' "
        f"(orden={args.order_by}, límite={limit}, filtro='{substring_filter}', min_price={min_price}, max_price={max_price}, "
        f"headless={args.headless}, strict={args.strict})"
    )

    productos = fetch_products(
        keyword=args.keyword,
        order_by=args.order_by,
        limit=limit,
        substring_filter=substring_filter,
        min_price=min_price,
        max_price=max_price,
        headless=args.headless,   # ✅ NUNCA None
        strict=args.strict,
    )

    if not productos:
        print("\nNo se han obtenido productos. Revisa bloqueo / captcha / filtros.")
        return 2  # para que daily_scrape pueda reintentar

    # --- Limpieza Wallapop: texto + mínimo absoluto + outliers por mediana ---
    productos, meta = apply_listing_filters(
        productos,
        mode=args.filter_mode,
        exclude_bad_text=(not args.no_text_filter),
    )

    if meta.total_in != meta.kept:
        msg = (
            f"[Filtros] mode={meta.mode} | text_filter={'on' if meta.exclude_bad_text else 'off'} | "
            f"min_valid={meta.min_valid_price:.0f}€ | "
            f"quitados: texto={meta.removed_text}, <=min={meta.removed_min_price}"
        )
        if meta.applied_median_filter and meta.median_raw and meta.lower_bound and meta.upper_bound:
            msg += (
                f", mediana={meta.median_raw:.2f}€ rango=({meta.lower_bound:.2f}–{meta.upper_bound:.2f})€ "
                f"fuera: bajos={meta.removed_low}, altos={meta.removed_high}"
            )
        print(msg)

    if args.save_raw:
        Path("data").mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = args.keyword.replace(" ", "_")
        filename = Path("data") / f"wallapop_{slug}_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(productos, f, ensure_ascii=False, indent=2)
        print(f"\nGuardados {len(productos)} productos crudos en: {filename}")

    if args.save_db:
        inserted = save_products(args.keyword, productos)
        print(f"\nGuardados {inserted} productos en la BD (data/market_analyzer.db).")

    stats, precios = calcular_estadisticas(productos)
    if not stats:
        print("No hay precios válidos en los productos obtenidos.")
        return 3

    imprimir_resumen(stats, productos, precios)
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as e:
        print(f"[ERROR] analyze_market: {e}")
        rc = 1
    raise SystemExit(rc)
