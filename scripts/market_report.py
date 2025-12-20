# Nota: script CLI de desarrollo / análisis.
# Toda la lógica de negocio viene de analytics.market_core.


import argparse
from typing import List, Optional, Tuple, Dict, Any

from analytics.market_core import (
    fetch_runs_for_keyword,
    fetch_prices_for_run,
    calcular_stats_precios,
)


def imprimir_estado_actual(
    keyword: str,
    scraped_at: str,
    stats: Dict[str, Any],
    precios: List[float],
) -> None:
    n = stats["n"]
    media = stats["media"]
    mediana = stats["mediana"]
    minimo = stats["minimo"]
    maximo = stats["maximo"]
    q1 = stats["q1"]
    q2 = stats["q2"]
    q3 = stats["q3"]

    print(f"\n=== INFORME DE MERCADO — '{keyword}' ===")
    print(f"Run analizada (más reciente): {scraped_at}")
    print("\n--- Resumen estadístico actual ---")
    print(f"Anuncios con precio válido: {n}")
    print(f"Precio medio:        {media:.2f} €")
    print(f"Mediana:             {mediana:.2f} €")
    print(f"Mínimo:              {minimo:.2f} €")
    print(f"Máximo:              {maximo:.2f} €")
    print(f"Q1 (25%):            {q1:.2f} €")
    print(f"Q2 / mediana:        {q2:.2f} €")
    print(f"Q3 (75%):            {q3:.2f} €")

    # Distribución barato / normal / caro
    def etiqueta(p: float) -> str:
        if p < q1:
            return "barato"
        elif p > q3:
            return "caro"
        else:
            return "normal"

    conteo = {"barato": 0, "normal": 0, "caro": 0}
    for p in precios:
        conteo[etiqueta(p)] += 1

    print("\n--- Distribución por tramos ---")
    total = sum(conteo.values())
    for k in ["barato", "normal", "caro"]:
        v = conteo[k]
        pct = (v / total) * 100 if total else 0
        print(f"  {k:7}: {v:4d} anuncios ({pct:5.1f}%)")

    # Recomendación de precio
    print("\n--- Recomendación de precio ---")
    print(
        f"- Rango razonable para anunciar: ~{q1:.0f} € – ~{q3:.0f} € "
        f"(zona 'normal' del mercado actual)"
    )
    print(
        f"- Para vender relativamente rápido: apunta a ~{q1:.0f}–{mediana:.0f} € "
        f"(parte baja de la zona normal)"
    )
    print(
        f"- Si te da igual tardar algo más pero quieres más margen: "
        f"~{mediana:.0f}–{q3:.0f} €"
    )


def imprimir_comparacion(runs: List[Tuple[str, int, float, float, float]], keyword: str) -> None:
    """
    Si hay al menos 2 runs, compara la más reciente con la anterior.
    """
    if len(runs) < 2:
        print("\n(No hay suficientes ejecuciones históricas para comparar tendencias.)")
        return

    scraped_at_new, _, _, _, _ = runs[0]
    scraped_at_old, _, _, _, _ = runs[1]

    precios_new = fetch_prices_for_run(keyword, scraped_at_new)
    precios_old = fetch_prices_for_run(keyword, scraped_at_old)

    stats_new = calcular_stats_precios(precios_new)
    stats_old = calcular_stats_precios(precios_old)

    if not stats_new or not stats_old:
        print("\nNo hay precios suficientes en alguna de las ejecuciones para comparar.")
        return

    media_old = stats_old["media"]
    media_new = stats_new["media"]
    mediana_old = stats_old["mediana"]
    mediana_new = stats_new["mediana"]

    diff_media = media_new - media_old
    pct_media = (diff_media / media_old * 100) if media_old else 0.0

    diff_mediana = mediana_new - mediana_old
    pct_mediana = (diff_mediana / mediana_old * 100) if mediana_old else 0.0

    print("\n--- Comparación con la ejecución anterior ---")
    print(f"Run anterior: {scraped_at_old}")
    print("\nCambio en PRECIO MEDIO:")
    print(f"  De {media_old:.2f} € a {media_new:.2f} €  ->  {diff_media:+.2f} € ({pct_media:+.1f} %)")

    print("\nCambio en MEDIANA:")
    print(
        f"  De {mediana_old:.2f} € a {mediana_new:.2f} €  "
        f"->  {diff_mediana:+.2f} € ({pct_mediana:+.1f} %)"
    )

    print("\nInterpretación rápida:")
    if abs(pct_media) < 3 and abs(pct_mediana) < 3:
        print("  El mercado está bastante ESTABLE entre las dos últimas ejecuciones.")
    elif pct_media > 0 and pct_mediana > 0:
        print("  Los precios tienden a SUBIR.")
    elif pct_media < 0 and pct_mediana < 0:
        print("  Los precios tienden a BAJAR.")
    else:
        print("  Movimiento mixto (puede haber más dispersión o cambios en el mix de anuncios).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Informe completo de mercado (estado actual + tendencia reciente) para un keyword"
    )
    parser.add_argument(
        "--keyword",
        required=True,
        help="Keyword exacta usada al guardar (ej. 'iphone 12 128gb')",
    )

    args = parser.parse_args()
    keyword = args.keyword

    runs = fetch_runs_for_keyword(keyword)
    if not runs:
        print(f"No hay datos en BD para keyword = '{keyword}'.")
        return

    scraped_at_new, _, _, _, _ = runs[0]
    precios_new = fetch_prices_for_run(keyword, scraped_at_new)
    stats_new = calcular_stats_precios(precios_new)

    if not stats_new:
        print("No hay precios válidos en la run más reciente.")
        return

    imprimir_estado_actual(keyword, scraped_at_new, stats_new, precios_new)
    imprimir_comparacion(runs, keyword)


if __name__ == "__main__":
    main()
