# AVISO: script legacy de análisis / debug.
# Puede quedar desfasado respecto a analytics.market_core y la web.
# Úsalo solo como herramienta de desarrollo.


import argparse
import json
from pathlib import Path
import statistics


def cargar_precios(path_json: Path):
    with open(path_json, "r", encoding="utf-8") as f:
        productos = json.load(f)

    precios = [p["precio"] for p in productos if p.get("precio") is not None]
    return productos, precios


def clasificar_precios(precios):
    if len(precios) < 4:
        return None, None, None, {}

    q1, q2, q3 = statistics.quantiles(precios, n=4)  # 25%, 50%, 75%

    def etiqueta(p):
        if p < q1:
            return "barato"
        elif p > q3:
            return "caro"
        else:
            return "normal"

    conteo = {"barato": 0, "normal": 0, "caro": 0}
    for p in precios:
        conteo[etiqueta(p)] += 1

    return q1, q2, q3, conteo


def main():
    parser = argparse.ArgumentParser(description="Análisis de precios Wallapop")
    parser.add_argument(
        "file",
        help="Ruta al JSON generado en data/ (ej: data/wallapop_iphone_12_2025....json)",
    )
    args = parser.parse_args()

    path_json = Path(args.file)
    if not path_json.is_file():
        print(f"No existe el fichero: {path_json}")
        return

    productos, precios = cargar_precios(path_json)

    if not precios:
        print("No hay precios válidos en el fichero.")
        return

    n = len(precios)
    media = sum(precios) / n
    mediana = statistics.median(precios)
    minimo = min(precios)
    maximo = max(precios)

    q1, q2, q3, conteo = clasificar_precios(precios)

    print(f"\nArchivo: {path_json}")
    print(f"Anuncios con precio válido: {n}")
    print(f"Precio medio:   {media:.2f} €")
    print(f"Mediana:        {mediana:.2f} €")
    print(f"Mínimo:         {minimo:.2f} €")
    print(f"Máximo:         {maximo:.2f} €")

    if q1 is not None:
        print(f"Q1 (25%):       {q1:.2f} €")
        print(f"Q2/mediana:     {q2:.2f} €")
        print(f"Q3 (75%):       {q3:.2f} €")
        print("\nDistribución por tramos:")
        total = sum(conteo.values())
        for k in ["barato", "normal", "caro"]:
            v = conteo[k]
            pct = (v / total) * 100 if total else 0
            print(f"  {k:7}: {v:4d} anuncios ({pct:5.1f}%)")

    # Top 5 más baratos y más caros
    productos_ordenados = sorted(
        [p for p in productos if p.get("precio") is not None],
        key=lambda p: p["precio"],
    )

    print("\nTop 5 más baratos:")
    for p in productos_ordenados[:5]:
        print(f"  {p['precio']:7.2f} € — {p['titulo'][:60]}")

    print("\nTop 5 más caros:")
    for p in productos_ordenados[-5:]:
        print(f"  {p['precio']:7.2f} € — {p['titulo'][:60]}")

    print("\n")


if __name__ == "__main__":
    main()
