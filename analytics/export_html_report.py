from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

import matplotlib.pyplot as plt

from analytics.market_core import (
    fetch_runs_for_keyword,
    fetch_prices_for_run,
    calcular_stats_precios,
    fetch_mean_median_series,
)

# Directorios donde se guardan gráficos e informes
PLOTS_DIR = Path("plots")
REPORTS_DIR = Path("reports")


def _sanitize_keyword_for_filename(keyword: str) -> str:
    """
    Convierte un keyword en algo seguro para nombre de archivo.
    """
    base = keyword.strip().replace(" ", "_")
    # Por si acaso, quitamos caracteres raros
    return "".join(ch for ch in base if ch.isalnum() or ch in ("_", "-")) or "keyword"


def generar_grafico_mean_median(keyword: str) -> Optional[str]:
    """
    Genera un PNG con la evolución del precio medio y mediano para un keyword,
    usando TODAS las runs guardadas en la BD (fetch_mean_median_series).

    Devuelve la ruta al archivo generado (str) o None si no hay datos.
    """
    serie = fetch_mean_median_series(keyword)
    if not serie:
        print(f"[export_html_report] No hay datos para generar gráfico mean/median de '{keyword}'.")
        return None

    fechas = sorted(serie.keys())
    medias = [serie[f]["media"] for f in fechas]
    medianas = [serie[f]["mediana"] for f in fechas]

    PLOTS_DIR.mkdir(exist_ok=True)
    filename = f"{_sanitize_keyword_for_filename(keyword)}_mean_median_over_time.png"
    outfile = PLOTS_DIR / filename

    plt.figure()
    plt.plot(fechas, medias, marker="o", label="Media")
    plt.plot(fechas, medianas, marker="s", linestyle="--", label="Mediana")
    plt.title(f"Evolución precio medio y mediano — {keyword}")
    plt.xlabel("Fecha de scraping")
    plt.ylabel("Precio (€)")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outfile)
    plt.close()

    print(f"[export_html_report] Gráfico media/mediana guardado en: {outfile}")
    return str(outfile)

def generar_grafico_multi_keywords_mean(keywords: List[str]) -> Optional[str]:
    """
    Genera un PNG comparando la evolución del PRECIO MEDIO (por run) de varios keywords.
    Devuelve ruta al PNG o None si no hay datos suficientes.
    """
    import hashlib

    kws = [k.strip() for k in (keywords or []) if k and k.strip()]
    if len(kws) < 2:
        return None

    series = {}
    for kw in kws:
        runs = fetch_runs_for_keyword(kw)  # DESC
        if not runs:
            continue

        pts = []
        for scraped_at, _n, avg_price, _minp, _maxp in runs:
            try:
                dt = datetime.fromisoformat(scraped_at)
            except Exception:
                continue
            if avg_price is None:
                continue
            pts.append((dt, float(avg_price)))

        pts.sort(key=lambda x: x[0])  # cronológico
        if pts:
            series[kw] = pts

    if len(series) < 2:
        return None

    # Nombre de fichero estable y corto
    key = "|".join(sorted(series.keys()))
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:10]
    filename = f"compare_{h}_mean_over_time.png"
    outfile = PLOTS_DIR / filename

    PLOTS_DIR.mkdir(exist_ok=True)

    plt.figure()
    for kw, pts in series.items():
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        plt.plot(xs, ys, marker="o", label=kw)

    plt.title("Evolución del precio medio — comparación")
    plt.xlabel("Fecha de scraping")
    plt.ylabel("Precio medio (€)")
    plt.xticks(rotation=45)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(outfile)
    plt.close()

    return str(outfile)



def generar_html_report(keyword: str, outfile: Optional[str | Path] = None) -> Path:
    """
    Genera un informe HTML de mercado para un keyword, usando SOLO datos de la BD
    a través de analytics.market_core.

    - Usa la run más reciente para las stats principales.
    - Incluye listado de runs (overview).
    - Incorpora el gráfico de evolución media/mediana si existe.

    Devuelve la ruta al HTML generado.
    """
    runs = fetch_runs_for_keyword(keyword)
    if not runs:
        raise ValueError(f"No hay datos en BD para el keyword '{keyword}'.")

    # Run más reciente
    scraped_at_new, n_items, avg_price, min_price, max_price = runs[0]
    precios_new = fetch_prices_for_run(keyword, scraped_at_new)
    stats = calcular_stats_precios(precios_new)
    if not stats:
        raise ValueError(f"No se pudieron calcular stats para '{keyword}' en {scraped_at_new}.")

    # Stats detalladas de la última run
    n = stats["n"]
    media = stats["media"]
    mediana = stats["mediana"]
    minimo = stats["minimo"]
    maximo = stats["maximo"]
    q1 = stats["q1"]
    q2 = stats["q2"]
    q3 = stats["q3"]

    rango_normal = f"{q1:.0f}–{q3:.0f} €"
    rango_rapido = f"{q1:.0f}–{mediana:.0f} €"
    rango_lento = f"{mediana:.0f}–{q3:.0f} €"

    # Gráfico de media/mediana
    grafico_path = generar_grafico_mean_median(keyword)
    grafico_rel = None
    if grafico_path:
        # Desde reports/, la ruta relativa típica será "../plots/archivo.png"
        graf_name = Path(grafico_path).name
        grafico_rel = f"../plots/{graf_name}"

    # Tabla de overview de todas las runs
    filas_runs_html: List[str] = []
    for scraped_at, rn_items, rn_avg, rn_min, rn_max in runs:
        filas_runs_html.append(
            f"<tr>"
            f"<td>{scraped_at}</td>"
            f"<td>{rn_items}</td>"
            f"<td>{rn_avg:.2f} €</td>"
            f"<td>{rn_min:.2f} €</td>"
            f"<td>{rn_max:.2f} €</td>"
            f"</tr>"
        )

    runs_table_html = "\n".join(filas_runs_html)

    # Construimos HTML
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Informe de mercado — {keyword}</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 20px;
      max-width: 900px;
    }}
    h1, h2, h3 {{
      margin-bottom: 0.4em;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-bottom: 16px;
    }}
    th, td {{
      border: 1px solid #ccc;
      padding: 6px 8px;
      text-align: left;
    }}
    th {{
      background-color: #f2f2f2;
    }}
    .tag {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      background-color: #e5e7eb;
      font-size: 12px;
    }}
    small {{
      color: #666;
    }}
  </style>
</head>
<body>
  <h1>Informe de mercado — "{keyword}"</h1>
  <p><span class="tag">Última run: {scraped_at_new}</span></p>

  <h2>Resumen de la última ejecución</h2>
  <table>
    <tr><th>Métrica</th><th>Valor</th></tr>
    <tr><td>Anuncios con precio válido</td><td>{n}</td></tr>
    <tr><td>Precio medio</td><td>{media:.2f} €</td></tr>
    <tr><td>Mediana</td><td>{mediana:.2f} €</td></tr>
    <tr><td>Mínimo</td><td>{minimo:.2f} €</td></tr>
    <tr><td>Máximo</td><td>{maximo:.2f} €</td></tr>
    <tr><td>Q1 (25 %)</td><td>{q1:.2f} €</td></tr>
    <tr><td>Q2 / mediana (50 %)</td><td>{q2:.2f} €</td></tr>
    <tr><td>Q3 (75 %)</td><td>{q3:.2f} €</td></tr>
  </table>

  <h2>Recomendación rápida de precios</h2>
  <ul>
    <li><strong>Rango “normal” del mercado:</strong> {rango_normal}</li>
    <li><strong>Para vender relativamente rápido:</strong> {rango_rapido}</li>
    <li><strong>Si buscas más margen y aceptas tardar más:</strong> {rango_lento}</li>
  </ul>
  <p><small>Basado en los cuartiles de precio (Q1, Q2, Q3) de la última ejecución.</small></p>

  <h2>Histórico de runs</h2>
  <table>
    <tr>
      <th>Scraped at</th>
      <th>Anuncios</th>
      <th>Precio medio</th>
      <th>Mínimo</th>
      <th>Máximo</th>
    </tr>
    {runs_table_html}
  </table>
"""

    if grafico_rel:
        html += f"""
  <h2>Evolución del precio medio y mediano</h2>
  <img src="{grafico_rel}" alt="Evolución precios"
       style="max-width: 100%; height: auto; border: 1px solid #ccc; padding: 4px;">
  <p><small>Gráfico generado automáticamente a partir de todas las ejecuciones guardadas en la base de datos.</small></p>
"""

    html += """
</body>
</html>
"""

    # Salida
    REPORTS_DIR.mkdir(exist_ok=True)

    if outfile is None:
        out_name = f"{_sanitize_keyword_for_filename(keyword)}_market_report.html"
        out_path = REPORTS_DIR / out_name
    else:
        out_path = Path(outfile)

    out_path.write_text(html, encoding="utf-8")
    print(f"[export_html_report] Informe HTML generado en: {out_path}")

    return out_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generar informe HTML de mercado a partir de la BD."
    )
    parser.add_argument(
        "keyword",
        help="Keyword exacta a analizar (tal como está guardada en la BD).",
    )
    parser.add_argument(
        "--outfile",
        help="Ruta de salida del HTML (opcional). Si no se indica, se usa 'reports/<keyword>_market_report.html'.",
        default=None,
    )

    args = parser.parse_args()
    generar_html_report(args.keyword, args.outfile)
