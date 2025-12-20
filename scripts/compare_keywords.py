# Nota: script CLI de desarrollo / análisis.
# Toda la lógica de negocio viene de analytics.market_core.


import argparse
from datetime import datetime
from typing import Dict, List

import matplotlib.pyplot as plt

from analytics.market_core import fetch_mean_median_series


def fetch_mean_price_by_run(keyword: str) -> Dict[datetime, float]:
    """
    Para un keyword, devuelve un diccionario:
        { scraped_at_datetime: precio_medio_en_esa_run }
    Ordenado por fecha.
    Usa la serie del núcleo (media/mediana) y se queda con la media.
    """
    serie = fetch_mean_median_series(keyword)
    if not serie:
        return {}

    # serie: { datetime: {"media": float, "mediana": float} }
    resultado: Dict[datetime, float] = {}
    for dt, info in serie.items():
        resultado[dt] = info["media"]

    return dict(sorted(resultado.items(), key=lambda x: x[0]))


def plot_keywords(keywords: List[str]):
    """
    Dibuja en un mismo gráfico la evolución del precio medio
    para varios keywords.
    """
    if not keywords:
        print("No se ha proporcionado ningún keyword.")
        return

    series = {}
    for kw in keywords:
        data = fetch_mean_price_by_run(kw)
        if not data:
            print(f"Sin datos en BD para keyword = '{kw}', se omite.")
            continue
        series[kw] = data

    if not series:
        print("No hay datos suficientes para ninguno de los keywords.")
        return

    plt.figure()
    for kw, data in series.items():
        fechas = sorted(data.keys())
        medias = [data[f] for f in fechas]
        plt.plot(fechas, medias, marker="o", label=kw)

    plt.title("Evolución del precio medio por keyword")
    plt.xlabel("Fecha de scraping")
    plt.ylabel("Precio medio (€)")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Compara la evolución del precio medio en el tiempo para varios keywords "
            "usando los datos de la base de datos."
        )
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        required=True,
        help="Lista de keywords exactos (ej: --keywords 'iphone 11' 'iphone 12')",
    )

    args = parser.parse_args()
    plot_keywords(args.keywords)


if __name__ == "__main__":
    main()
