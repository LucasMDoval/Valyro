from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time

import socket
import urllib.request


from datetime import datetime
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    jsonify,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from analytics.export_html_report import generar_grafico_mean_median, generar_html_report
from analytics.market_core import fetch_runs_for_keyword, get_last_run_stats, get_sell_speed_summary
from utils.db import DB_PATH, delete_all_for_keyword, delete_run, get_connection
from web.api import api_bp
from web.legal import LEGAL_NOTICE


# =============================================================================
# Proyecto root (modo normal y modo .exe PyInstaller)
# =============================================================================
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# App + Config
# =============================================================================
app = Flask(__name__)
app.secret_key = "cambia_esta_clave_si_quieres"

# API REST bajo /api/v1
app.register_blueprint(api_bp, url_prefix="/api/v1")

DATA_DIR = PROJECT_ROOT / "data"
KEYWORDS_FILE = DATA_DIR / "daily_keywords.txt"
PLOTS_DIR = PROJECT_ROOT / "plots"
LOGS_DIR = PROJECT_ROOT / "logs"
# === Rutas de datos (añade REPORTS_DIR) ===
REPORTS_DIR = PROJECT_ROOT / "reports"


from web.progress_state import SCRAPE_PROGRESS



# =============================================================================
# Utilidades: keywords / DB
# =============================================================================
def load_keywords_from_file() -> list[str]:
    if not KEYWORDS_FILE.is_file():
        return []
    contenido = KEYWORDS_FILE.read_text(encoding="utf-8")
    lineas = [l.strip() for l in contenido.splitlines()]
    kws: list[str] = []
    for l in lineas:
        if not l or l.startswith("#"):
            continue
        # Permite formato "keyword | key=value ..." (nos quedamos con el keyword)
        kw = l.split("|", 1)[0].strip()
        if kw:
            kws.append(kw)
    return kws


def load_keywords_from_db() -> list[str]:
    if not DB_PATH.is_file():
        return []
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT keyword
        FROM products
        ORDER BY keyword;
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


# =============================================================================
# Daily keywords: defaults + preview por keyword (líneas con formato)
#   - keyword
#   - keyword | limit=300 | order_by=newest | min_price=50 | max_price=400
# =============================================================================
DEFAULT_DAILY = {
    "order_by": "most_relevance",
    "limit": 500,
    "min_price": None,
    "max_price": None,
    # Filtros recomendados para Wallapop
    "filter_mode": "soft",  # soft|strict|off
    "exclude_bad_text": True,
}

_ALLOWED_ORDER_BY = {"most_relevance", "price_low_to_high", "price_high_to_low", "newest"}


def _parse_kv_token(token: str) -> tuple[str, str] | None:
    token = token.strip()
    if not token or "=" not in token:
        return None
    k, v = token.split("=", 1)
    return k.strip(), v.strip()


def _to_float_or_none(v: str) -> float | None:
    v = v.strip()
    if v == "":
        return None
    return float(v)


def parse_daily_keywords_file() -> tuple[list[dict[str, Any]], list[str]]:
    """
    Devuelve:
      - preview: [{keyword, limit, order_by, min_price, max_price, raw_line}]
      - warnings: [str]
    """
    preview: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not KEYWORDS_FILE.is_file():
        return preview, warnings

    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split("|") if p.strip()]
        kw = parts[0]
        cfg = dict(DEFAULT_DAILY)

        for token in parts[1:]:
            kv = _parse_kv_token(token)
            if not kv:
                warnings.append(f"Línea {i}: token inválido '{token}' (usa key=value).")
                continue

            k, v = kv
            if k in ("limit", "order_by"):
                # Por requisito: en la UI ya no se permite elegir límite ni orden.
                # Los tokens se admiten para compatibilidad, pero se ignoran.
                warnings.append(f"Línea {i}: '{k}={v}' se ignora (fijo: limit={DEFAULT_DAILY['limit']}, order_by={DEFAULT_DAILY['order_by']}).")
                continue
            elif k in ("min_price", "min"):
                try:
                    cfg["min_price"] = _to_float_or_none(v)
                except Exception:
                    warnings.append(f"Línea {i}: min_price inválido '{v}'.")
            elif k in ("max_price", "max"):
                try:
                    cfg["max_price"] = _to_float_or_none(v)
                except Exception:
                    warnings.append(f"Línea {i}: max_price inválido '{v}'.")
            elif k in ("filter", "filter_mode", "mode"):
                vv = str(v).strip().lower()
                if vv in ("soft", "strict", "off"):
                    cfg["filter_mode"] = vv
                else:
                    warnings.append(f"Línea {i}: filter_mode inválido '{v}' (usa soft|strict|off).")
            elif k in ("exclude_bad_text", "text_filter", "exclude_bad"):
                vv = str(v).strip().lower()
                if vv in ("1", "true", "yes", "on"):
                    cfg["exclude_bad_text"] = True
                elif vv in ("0", "false", "no", "off"):
                    cfg["exclude_bad_text"] = False
                else:
                    warnings.append(f"Línea {i}: exclude_bad_text inválido '{v}' (usa 1/0, true/false).")
            else:
                warnings.append(f"Línea {i}: clave desconocida '{k}' (se ignora).")

        mp = cfg.get("min_price")
        xp = cfg.get("max_price")
        if mp is not None and xp is not None and mp > xp:
            cfg["min_price"], cfg["max_price"] = xp, mp
            warnings.append(f"Línea {i}: min_price > max_price, los he intercambiado para '{kw}'.")

        preview.append(
            {
                "keyword": kw,
                "limit": cfg["limit"],
                "order_by": cfg["order_by"],
                "min_price": cfg["min_price"],
                "max_price": cfg["max_price"],
                "filter_mode": cfg.get("filter_mode", "soft"),
                "exclude_bad_text": bool(cfg.get("exclude_bad_text", True)),
                "raw_line": raw,
                "line_no": i,
                "notes": [],  # por compatibilidad si tu HTML pinta "notes"
            }
        )

    return preview, warnings


# =============================================================================
# Utilidades: scheduling Windows (Task Scheduler)
# =============================================================================
TASK_NAME = "Valyro - Daily Scrape"
PS_DIR = DATA_DIR / "ps"
PS_RUNNER = PS_DIR / "run_daily_scrape.ps1"
PS_INSTALLER = PS_DIR / "install_daily_task.ps1"
SCHEDULE_FILE = DATA_DIR / "daily_schedule.json"

_PS_RUNNER_CONTENT = r"""
param(
  [string]$Mode = "python",   # "python" o "exe"
  [string]$ProjectRoot = ""
)

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot = (Resolve-Path ".").Path
}

Set-Location $ProjectRoot

$logDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("daily_scrape_" + (Get-Date -Format "yyyyMMdd") + ".log")

"==== Valyro daily_scrape START $(Get-Date -Format o) ====" | Out-File -FilePath $logFile -Append -Encoding utf8

try {
  if ($Mode -eq "exe") {
    $exePath = Join-Path $ProjectRoot "valyro.exe"
    if (!(Test-Path $exePath)) { throw "No existe: $exePath" }

    & $exePath --daily-scrape --headless 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
    $exitCode = $LASTEXITCODE
  }
  else {
    $venvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
      $py = $venvPy
    } else {
      $pyCmd = Get-Command python -ErrorAction SilentlyContinue
      if (!$pyCmd) { throw "No encuentro python (ni .venv\Scripts\python.exe ni python en PATH)" }
      $py = $pyCmd.Source
    }

    & $py -m scripts.daily_scrape 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
    $exitCode = $LASTEXITCODE
  }

  "==== Valyro daily_scrape END $(Get-Date -Format o) exit=$exitCode ====" | Out-File -FilePath $logFile -Append -Encoding utf8
  exit $exitCode
}
catch {
  "==== Valyro daily_scrape CRASH $(Get-Date -Format o) ====" | Out-File -FilePath $logFile -Append -Encoding utf8
  $_ | Out-File -FilePath $logFile -Append -Encoding utf8
  exit 99
}
"""

_PS_INSTALLER_CONTENT = r"""
param(
  [Parameter(Mandatory=$true)]
  [string]$Time,              # "09:30"
  [string]$Mode = "python",   # "python" ahora, "exe" luego
  [string]$TaskName = "Valyro - Daily Scrape",
  [string]$ProjectRoot = ""
)

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot = (Resolve-Path ".").Path
}

$runner = Join-Path $ProjectRoot "data\ps\run_daily_scrape.ps1"
if (!(Test-Path $runner)) { throw "No existe runner PS: $runner" }

$action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Mode $Mode -ProjectRoot `"$ProjectRoot`""

schtasks /Create /F /TN "$TaskName" /TR "$action" /SC DAILY /ST "$Time" /RL HIGHEST /RU "$env:USERNAME" | Out-Null

Write-Host "OK: tarea instalada/actualizada: $TaskName a las $Time"
"""

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")



def _is_windows() -> bool:
    return os.name == "nt"


def _schedule_mode() -> str:
    return "exe" if getattr(sys, "frozen", False) else "python"


def _ensure_ps_scripts() -> None:
    PS_DIR.mkdir(parents=True, exist_ok=True)
    if not PS_RUNNER.is_file():
        PS_RUNNER.write_text(_PS_RUNNER_CONTENT, encoding="utf-8")
    if not PS_INSTALLER.is_file():
        PS_INSTALLER.write_text(_PS_INSTALLER_CONTENT, encoding="utf-8")


def _validate_time_hhmm(value: str) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not _TIME_RE.match(value):
        return None
    hh, mm = value.split(":")
    try:
        h = int(hh)
        m = int(mm)
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return f"{h:02d}:{m:02d}"


def load_schedule_time() -> str:
    try:
        if SCHEDULE_FILE.is_file():
            data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
            return str(data.get("daily_time") or "").strip()
    except Exception:
        return ""
    return ""


def save_schedule_time(t: str) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    SCHEDULE_FILE.write_text(
        json.dumps({"daily_time": t}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_task_installed() -> bool:
    if not _is_windows():
        return False
    try:
        cp = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True)
        return cp.returncode == 0
    except Exception:
        return False


def install_daily_task(time_hhmm: str) -> tuple[bool, str]:
    if not _is_windows():
        return False, "Esto solo está soportado en Windows."

    _ensure_ps_scripts()

    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS_INSTALLER),
        "-Time",
        time_hhmm,
        "-Mode",
        _schedule_mode(),
        "-TaskName",
        TASK_NAME,
        "-ProjectRoot",
        str(PROJECT_ROOT),
    ]
    cp = subprocess.run(cmd, capture_output=True, text=True)
    out = (cp.stdout or "") + "\n" + (cp.stderr or "")
    if cp.returncode == 0:
        save_schedule_time(time_hhmm)
        return True, out.strip()
    return False, out.strip() or f"Error instalando tarea (exit={cp.returncode})."


def remove_daily_task() -> tuple[bool, str]:
    if not _is_windows():
        return False, "Esto solo está soportado en Windows."
    cp = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True, text=True)
    out = (cp.stdout or "") + "\n" + (cp.stderr or "")
    if cp.returncode == 0:
        return True, out.strip()
    return False, out.strip() or f"Error eliminando tarea (exit={cp.returncode})."


def run_daily_now() -> tuple[bool, str]:
    if _is_windows():
        _ensure_ps_scripts()
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PS_RUNNER),
            "-Mode",
            _schedule_mode(),
            "-ProjectRoot",
            str(PROJECT_ROOT),
        ]
        cp = subprocess.run(cmd, capture_output=True, text=True)
        out = (cp.stdout or "") + "\n" + (cp.stderr or "")
        return (cp.returncode == 0), (out.strip() or f"Exit={cp.returncode} (mira logs/).")

    cmd = [sys.executable, "-m", "scripts.daily_scrape"]
    cp = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    out = (cp.stdout or "") + "\n" + (cp.stderr or "")
    return (cp.returncode == 0), (out.strip() or f"Exit={cp.returncode}.")


# =============================================================================
# Scrape manual desde web
# =============================================================================
def run_analyze_market_from_web(
    keyword: str,
    limit: int,
    order_by: str,
    min_price: float | None,
    max_price: float | None,
    filter_mode: str,
    exclude_bad_text: bool,
) -> int:
    global SCRAPE_PROGRESS

    # Por requisito: fijo a 500 anuncios + "más relevantes".
    limit = DEFAULT_DAILY["limit"]
    order_by = DEFAULT_DAILY["order_by"]

    SCRAPE_PROGRESS["value"] = 0
    SCRAPE_PROGRESS["status"] = "starting"

    def progress_worker():
        v = 0
        while SCRAPE_PROGRESS["status"] not in ("finished", "error"):
            if v < 80:
                v += 3
                time.sleep(0.25)
            elif v < 95:
                v += 1
                time.sleep(0.8)
            else:
                time.sleep(1.0)

            SCRAPE_PROGRESS["value"] = min(v, 95)


    threading.Thread(target=progress_worker, daemon=True).start()

    try:
        cmd = [
            sys.executable,
            "-m",
            "scripts.analyze_market",
            keyword,
            "--order_by",
            order_by,
            "--limit",
            str(limit),
            "--save_db",
        ]

        # Filtros Wallapop
        fm = (filter_mode or "soft").strip().lower()
        if fm not in ("soft", "strict", "off"):
            fm = "soft"
        cmd.extend(["--filter_mode", fm])
        if not exclude_bad_text:
            cmd.append("--no_text_filter")
        if min_price is not None:
            cmd.extend(["--min_price", str(min_price)])
        if max_price is not None:
            cmd.extend(["--max_price", str(max_price)])

        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        rc = result.returncode
    except Exception as e:
        print("[Valyro] Error al ejecutar scrape desde la web:", e)
        rc = -1

    SCRAPE_PROGRESS["value"] = 100
    SCRAPE_PROGRESS["status"] = "finished" if rc == 0 else "error"
    return rc


# =============================================================================
# Compare plot (evolución precio medio por keyword)
# =============================================================================
def generar_grafico_comparacion(selected: list[str]) -> str | None:
    if len(selected) < 2:
        return None
    if not DB_PATH.is_file():
        return None

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402
    from datetime import datetime as _dt  # noqa: E402

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT keyword, scraped_at, AVG(price) AS mean_price
        FROM products
        WHERE keyword IN ({})
          AND price IS NOT NULL
        GROUP BY keyword, scraped_at
        ORDER BY keyword, scraped_at;
        """.format(",".join("?" for _ in selected)),
        selected,
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None

    series: dict[str, list[tuple[_dt, float]]] = {}
    for kw, scraped_at, mean_price in rows:
        try:
            dt = _dt.fromisoformat(scraped_at)
            mp = float(mean_price)
        except Exception:
            continue
        series.setdefault(kw, []).append((dt, mp))

    if len(series) < 2:
        return None

    PLOTS_DIR.mkdir(exist_ok=True)
    fname = f"compare_{abs(hash(tuple(sorted(selected)))) % 10_000_000}.png"
    outpath = PLOTS_DIR / fname

    fig = plt.figure(figsize=(8.5, 4.5), dpi=160)
    ax = fig.add_subplot(111)

    for kw, pts in series.items():
        pts = sorted(pts, key=lambda x: x[0])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, marker="o", linewidth=2, label=kw)

    ax.set_title("Evolución del precio medio")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Precio medio (€)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(outpath)
    plt.close(fig)

    return str(outpath)


# =============================================================================
# Rutas estáticas / progreso
# =============================================================================
@app.route("/plots/<path:filename>")
def plots_static(filename: str):
    return send_from_directory(PLOTS_DIR, filename)


@app.route("/progress")
def progress_stream():
    def event_stream():
        last_value = None
        while True:
            data = SCRAPE_PROGRESS.copy()
            current_value = data.get("value")
            if current_value != last_value:
                last_value = current_value
                yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.2)

    return Response(event_stream(), mimetype="text/event-stream")

# =============================================================================
# API extra para el frontend React (migración de funcionalidades legacy)
# =============================================================================

def _api_error(code: str, message: str, http_status: int = 400):
    return jsonify({"error": {"code": code, "message": message}}), http_status


@app.get("/api/v1/daily")
def api_daily_get():
    schedule_time = load_schedule_time()
    task_installed = is_task_installed()
    daily_preview, daily_preview_warnings = parse_daily_keywords_file()
    return jsonify(
        {
            "task_name": TASK_NAME,
            "is_windows": _is_windows(),
            "schedule_time": schedule_time,
            "task_installed": task_installed,
            "defaults": DEFAULT_DAILY,
            "rows": daily_preview,
            "warnings": daily_preview_warnings,
        }
    )


@app.post("/api/v1/daily")
def api_daily_save():
    data = request.get_json(silent=True) or {}
    rows = data.get("rows", [])
    if not isinstance(rows, list):
        return _api_error("invalid_rows", "rows debe ser una lista", 400)

    def _num_or_none(x):
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None

    lines_out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        kw = (r.get("keyword") or "").strip()
        if not kw:
            continue

        mn = _num_or_none(r.get("min_price"))
        mx = _num_or_none(r.get("max_price"))
        if mn is not None and mx is not None and mn > mx:
            mn, mx = mx, mn

        fm = str(r.get("filter_mode") or DEFAULT_DAILY.get("filter_mode", "soft")).strip().lower()
        if fm not in ("soft", "strict", "off"):
            fm = DEFAULT_DAILY.get("filter_mode", "soft")

        exclude_bad = r.get("exclude_bad_text")
        if isinstance(exclude_bad, bool):
            pass
        elif exclude_bad is None:
            exclude_bad = bool(DEFAULT_DAILY.get("exclude_bad_text", True))
        else:
            exclude_bad = str(exclude_bad).strip().lower() in ("1", "true", "yes", "on")

        parts = [kw]
        if mn is not None:
            parts.append(f"min_price={mn:g}")
        if mx is not None:
            parts.append(f"max_price={mx:g}")
        if fm != DEFAULT_DAILY.get("filter_mode", "soft"):
            parts.append(f"filter={fm}")
        if bool(exclude_bad) != bool(DEFAULT_DAILY.get("exclude_bad_text", True)):
            parts.append(f"exclude_bad_text={'1' if exclude_bad else '0'}")

        lines_out.append(" | ".join(parts))

    DATA_DIR.mkdir(exist_ok=True)
    KEYWORDS_FILE.write_text("\n".join(lines_out) + ("\n" if lines_out else ""), encoding="utf-8")
    return jsonify({"status": "ok", "count": len(lines_out)})


@app.post("/api/v1/daily/run_now")
def api_daily_run_now():
    ok, msg = run_daily_now()
    return jsonify({"ok": bool(ok), "message": msg})


@app.post("/api/v1/daily/task/install")
def api_daily_task_install():
    data = request.get_json(silent=True) or {}
    t = _validate_time_hhmm(str(data.get("time") or ""))
    if not t:
        return _api_error("invalid_time", "Hora inválida. Usa HH:MM (ej. 09:30).", 400)
    ok, msg = install_daily_task(t)
    return jsonify({"ok": bool(ok), "message": msg, "time": t})


@app.post("/api/v1/daily/task/remove")
def api_daily_task_remove():
    ok, msg = remove_daily_task()
    return jsonify({"ok": bool(ok), "message": msg})


@app.post("/api/v1/compare")
def api_compare():
    data = request.get_json(silent=True) or {}
    kws = data.get("keywords", [])
    if not isinstance(kws, list):
        return _api_error("invalid_keywords", "keywords debe ser una lista", 400)

    selected = [str(k).strip() for k in kws if str(k).strip()]
    if len(selected) < 2:
        return _api_error("need_2_keywords", "Selecciona al menos 2 keywords.", 400)

    rows = []
    for kw in selected:
        res = get_last_run_stats(kw)
        if not res:
            continue
        scraped_at, stats = res
        q1 = stats["q1"]
        q3 = stats["q3"]
        mediana = stats["mediana"]
        rows.append(
            {
                "keyword": kw,
                "scraped_at": scraped_at,
                "n": stats["n"],
                "media": stats["media"],
                "mediana": mediana,
                "q1": q1,
                "q3": q3,
                "rango_normal": f"{q1:.0f}–{q3:.0f} €",
                "rango_rapido": f"{q1:.0f}–{mediana:.0f} €",
            }
        )

    if not rows:
        return _api_error("no_data", "No hay datos suficientes para comparar.", 404)

    plot_url = None
    try:
        p = generar_grafico_comparacion(selected)
        if p:
            plot_url = url_for("plots_static", filename=Path(p).name)
    except Exception:
        plot_url = None

    return jsonify({"comparison": rows, "plot_url": plot_url, "selected": selected})


@app.get("/api/v1/keyword/<kw>/runs")
def api_keyword_runs(kw: str):
    kw = (kw or "").strip()
    if not kw:
        return _api_error("invalid_keyword", "keyword vacío", 400)

    runs = fetch_runs_for_keyword(kw) or []
    out = []
    for scraped_at, n_items, avg_price, min_price, max_price in runs:
        out.append(
            {
                "scraped_at": scraped_at,
                "n": n_items,
                "media": avg_price,
                "minimo": min_price,
                "maximo": max_price,
            }
        )
    return jsonify({"keyword": kw, "runs": out})


@app.delete("/api/v1/keyword/<kw>/runs/<path:scraped_at>")
def api_keyword_delete_run(kw: str, scraped_at: str):
    kw = (kw or "").strip()
    scraped_at = (scraped_at or "").strip()
    if not kw or not scraped_at:
        return _api_error("invalid_params", "Falta kw o scraped_at", 400)

    deleted = delete_run(kw, scraped_at)
    return jsonify({"keyword": kw, "scraped_at": scraped_at, "deleted": int(deleted)})


@app.delete("/api/v1/keyword/<kw>")
def api_keyword_delete_all(kw: str):
    kw = (kw or "").strip()
    if not kw:
        return _api_error("invalid_keyword", "keyword vacío", 400)

    deleted = delete_all_for_keyword(kw)
    return jsonify({"keyword": kw, "deleted": int(deleted)})


@app.post("/api/v1/keyword/<kw>/report")
def api_keyword_report(kw: str):
    kw = (kw or "").strip()
    if not kw:
        return _api_error("invalid_keyword", "keyword vacío", 400)

    REPORTS_DIR.mkdir(exist_ok=True)
    outfile = REPORTS_DIR / f"valyro_report_{_slugify(kw)}.html"
    generar_html_report(kw, outfile=str(outfile))
    return jsonify({"keyword": kw, "url": url_for("reports_static", filename=outfile.name)})


@app.post("/api/v1/keyword/<kw>/plot/mean-median")
def api_keyword_plot_mean_median(kw: str):
    kw = (kw or "").strip()
    if not kw:
        return _api_error("invalid_keyword", "keyword vacío", 400)

    try:
        p = generar_grafico_mean_median(kw)
        if not p:
            return _api_error("no_data", "No hay datos para generar gráfico.", 404)
        return jsonify({"keyword": kw, "url": url_for("plots_static", filename=Path(p).name)})
    except Exception:
        return _api_error("plot_failed", "Error generando el gráfico.", 500)


@app.get("/api/v1/setup/checks")
def api_setup_checks():
    return jsonify({"checks": get_setup_checks()})


@app.post("/api/v1/setup/action")
def api_setup_action():
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()

    if action == "open_logs":
        _open_path(_logs_dir())
        return jsonify({"ok": True, "message": "Carpeta logs abierta."})

    if action == "open_data":
        _open_path(DATA_DIR)
        return jsonify({"ok": True, "message": "Carpeta data abierta."})

    if action == "fix_playwright":
        if _is_frozen():
            return jsonify({"ok": False, "message": "Modo .exe: si falla Playwright es tema del instalador."})
        rc, out, err = _run_cmd([sys.executable, "-m", "pip", "install", "--user", "playwright"], cwd=PROJECT_ROOT)
        ok = (rc == 0)
        return jsonify({"ok": ok, "message": "Playwright instalado/actualizado." if ok else "Error instalando Playwright.", "rc": rc})

    if action == "fix_browsers":
        rc, out, err = _run_cmd([sys.executable, "-m", "playwright", "install", "chromium"], cwd=PROJECT_ROOT)
        ok = (rc == 0)
        return jsonify({"ok": ok, "message": "Browsers instalados (chromium)." if ok else "Error instalando browsers.", "rc": rc})

    return _api_error("unknown_action", "Acción no reconocida", 400)


@app.get("/api/v1/legal")
def api_legal():
    return jsonify({"html": LEGAL_NOTICE})


# =============================================================================
# Rutas principales
# =============================================================================
@app.route("/legacy", methods=["GET", "POST"])

def index():
    kws_file = load_keywords_from_file()
    kws_db = load_keywords_from_db()

    seen = set()
    keywords: list[str] = []
    for kw in kws_file + kws_db:
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)

    keywords_file_raw = KEYWORDS_FILE.read_text(encoding="utf-8") if KEYWORDS_FILE.is_file() else ""

    schedule_time = load_schedule_time()
    task_installed = is_task_installed()

    # ===== ARREGLO 1: esto es lo que faltaba =====
    daily_defaults = DEFAULT_DAILY
    daily_preview, daily_preview_warnings = parse_daily_keywords_file()
    # ============================================

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "update_keywords_table":
            kws = request.form.getlist("daily_kw[]")
            mins = request.form.getlist("daily_min_price[]")
            maxs = request.form.getlist("daily_max_price[]")
            modes = request.form.getlist("daily_filter_mode[]")
            texts = request.form.getlist("daily_exclude_bad_text[]")

            lines_out = []
            # En la UI ya no se recogen límite ni orden. Se guardan solo keyword + rango.
            # Alineamos listas (si faltan valores, se usan defaults)
            max_len = max(len(kws), len(mins), len(maxs), len(modes), len(texts))
            def _get(lst, i, default=""):
                return lst[i] if i < len(lst) else default

            for i in range(max_len):
                kw = _get(kws, i)
                mn = _get(mins, i)
                mx = _get(maxs, i)
                fm = _get(modes, i, DEFAULT_DAILY.get("filter_mode", "soft"))
                et = _get(texts, i, "1")
                kw = (kw or "").strip()
                if not kw:
                    continue

                mn_v = None
                mx_v = None
                try:
                    if str(mn).strip() != "":
                        mn_v = float(mn)
                except Exception:
                    mn_v = None
                try:
                    if str(mx).strip() != "":
                        mx_v = float(mx)
                except Exception:
                    mx_v = None

                if mn_v is not None and mx_v is not None and mn_v > mx_v:
                    mn_v, mx_v = mx_v, mn_v

                # Línea compatible con daily_scrape.py (order/limit están fijados en el propio script)
                parts = [kw]
                if mn_v is not None:
                    parts.append(f"min_price={mn_v:g}")
                if mx_v is not None:
                    parts.append(f"max_price={mx_v:g}")

                fm = str(fm).strip().lower()
                if fm not in ("soft", "strict", "off"):
                    fm = DEFAULT_DAILY.get("filter_mode", "soft")
                if fm != DEFAULT_DAILY.get("filter_mode", "soft"):
                    parts.append(f"filter={fm}")

                exclude_bad = True
                try:
                    exclude_bad = str(et).strip().lower() in ("1", "true", "yes", "on")
                except Exception:
                    exclude_bad = True
                if exclude_bad != bool(DEFAULT_DAILY.get("exclude_bad_text", True)):
                    parts.append(f"exclude_bad_text={'1' if exclude_bad else '0'}")

                lines_out.append(" | ".join(parts))

            DATA_DIR.mkdir(exist_ok=True)
            KEYWORDS_FILE.write_text("\n".join(lines_out) + ("\n" if lines_out else ""), encoding="utf-8")
            flash("Configuración diaria guardada.", "success")
            return redirect(url_for("index"))


        if action == "run_daily_now":
            ok, msg = run_daily_now()
            if ok:
                flash("Scrape diario lanzado. Revisa logs/ si quieres ver el detalle.", "success")
            else:
                flash("Falló el scrape diario al probar ahora. Mira logs/.", "danger")
                print("[Valyro] run_daily_now output:\n", msg)
            return redirect(url_for("index"))

        if action == "install_daily_task":
            t = _validate_time_hhmm(request.form.get("daily_time", ""))
            if not t:
                flash("Hora inválida. Usa formato HH:MM (ej. 09:30).", "danger")
                return redirect(url_for("index"))

            ok, msg = install_daily_task(t)
            if ok:
                flash(f"Scrape diario activado/actualizado a las {t}.", "success")
            else:
                flash("No se pudo instalar la tarea automática. Revisa permisos/PowerShell.", "danger")
                print("[Valyro] install_daily_task output:\n", msg)
            return redirect(url_for("index"))

        if action == "remove_daily_task":
            ok, msg = remove_daily_task()
            if ok:
                flash("Scrape diario desactivado (tarea eliminada).", "success")
            else:
                flash("No se pudo eliminar la tarea. Revisa permisos.", "danger")
                print("[Valyro] remove_daily_task output:\n", msg)
            return redirect(url_for("index"))

        if action == "report":
            keyword = request.form.get("keyword", "").strip()
            if not keyword:
                flash("Debes elegir un keyword para generar informe.", "danger")
                return redirect(url_for("index"))

            generar_html_report(keyword, outfile=None)
            flash(f"Informe generado para '{keyword}'. Mira la carpeta 'reports/'.", "success")
            return redirect(url_for("index"))

        if action == "scrape":
            kw_manual = request.form.get("keyword_manual", "").strip()
            # Por requisito: fijo a 500 anuncios + "más relevantes".
            limit_val = DEFAULT_DAILY["limit"]
            order_by = DEFAULT_DAILY["order_by"]

            min_price_str = request.form.get("min_price_manual", "").strip()
            max_price_str = request.form.get("max_price_manual", "").strip()

            filter_mode = (request.form.get("filter_mode_manual") or DEFAULT_DAILY.get("filter_mode", "soft")).strip().lower()
            exclude_bad_text = bool(request.form.get("exclude_bad_text_manual"))

            if not kw_manual:
                flash("Debes indicar un keyword para scrapear.", "danger")
                return redirect(url_for("index"))

            # limit_val ya viene fijado

            min_price = None
            max_price = None
            try:
                if min_price_str:
                    min_price = float(min_price_str)
            except ValueError:
                min_price = None
            try:
                if max_price_str:
                    max_price = float(max_price_str)
            except ValueError:
                max_price = None

            if min_price is not None and max_price is not None and min_price > max_price:
                min_price, max_price = max_price, min_price

            rc = run_analyze_market_from_web(
                kw_manual,
                limit_val,
                order_by,
                min_price,
                max_price,
                filter_mode,
                exclude_bad_text,
            )
            if rc == 0:
                detalles_rango = ""
                if min_price is not None or max_price is not None:
                    detalles_rango = f" (rango {min_price or 0}–{max_price or '∞'} €)"
                flash(
                    f"Scrape completado para '{kw_manual}' (orden={order_by}, límite={limit_val}{detalles_rango}). "
                    f"Datos guardados en la BD.",
                    "success",
                )
            else:
                flash("Ha habido un error al ejecutar el scrape. Revisa logs/Playwright.", "danger")
            return redirect(url_for("index"))

        if action == "update_keywords":
            texto = request.form.get("keywords_text", "")
            DATA_DIR.mkdir(exist_ok=True)
            KEYWORDS_FILE.write_text(texto, encoding="utf-8")
            flash("Keywords del scrape diario actualizadas.", "success")
            return redirect(url_for("index"))

        flash("Acción no reconocida.", "danger")
        return redirect(url_for("index"))

    return render_template(
        "index.html",
        keywords=keywords,
        keywords_file_raw=keywords_file_raw,
        schedule_time=schedule_time,
        task_installed=task_installed,
        task_name=TASK_NAME,
        is_windows=_is_windows(),
        # ===== ARREGLO 1: pasar vars que usa tu index.html =====
        daily_defaults=daily_defaults,
        daily_preview=daily_preview,
        daily_preview_warnings=daily_preview_warnings,
        # =======================================================
    )

# ===== Diagnóstico / Setup =====
def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _logs_dir() -> Path:
    p = PROJECT_ROOT / "logs"
    p.mkdir(exist_ok=True)
    return p


def _open_path(path: Path) -> None:
    try:
        if _is_windows():
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
    except Exception:
        pass


def _check_logs_writable() -> tuple[bool, str]:
    try:
        d = _logs_dir()
        test = d / "_write_test.tmp"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)  # py>=3.8
        return True, str(d)
    except Exception as e:
        return False, f"No se puede escribir en logs/: {e}"


def _check_data_dir() -> tuple[bool, str]:
    try:
        DATA_DIR.mkdir(exist_ok=True)
        return True, str(DATA_DIR)
    except Exception as e:
        return False, f"No se puede crear/usar data/: {e}"


def _check_playwright_import() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True, "playwright import OK"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _guess_ms_playwright_dir() -> Path | None:
    # ubicación típica en Windows: %LOCALAPPDATA%\ms-playwright
    try:
        if _is_windows():
            local = os.environ.get("LOCALAPPDATA")
            if local:
                p = Path(local) / "ms-playwright"
                return p
    except Exception:
        pass
    return None


def _check_playwright_browsers_installed() -> tuple[bool, str]:
    # check simple y rápido (no lanza navegador)
    p = _guess_ms_playwright_dir()
    if p and p.is_dir():
        try:
            # si hay subcarpetas, algo hay instalado
            sub = [x for x in p.iterdir() if x.is_dir()]
            if sub:
                return True, f"Browsers detectados en {p}"
            return False, f"Carpeta existe pero vacía: {p}"
        except Exception:
            return False, f"No se pudo leer {p}"
    return False, "No detecto ms-playwright (probable: falta playwright install)"


def _check_scheduled_task() -> tuple[bool, str]:
    if not _is_windows():
        return True, "No aplica (no Windows)"
    try:
        cp = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME],
            capture_output=True,
            text=True,
        )
        if cp.returncode == 0:
            return True, "Tarea encontrada"
        # Mensaje útil
        msg = (cp.stderr or cp.stdout or "").strip()
        return False, msg if msg else "No existe la tarea"
    except Exception as e:
        return False, f"Error consultando schtasks: {e}"


def _run_cmd(cmd: list[str], *, cwd: Path | None = None, timeout_s: int = 900) -> tuple[int, str, str]:
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return cp.returncode, (cp.stdout or ""), (cp.stderr or "")
    except Exception as e:
        return 999, "", f"{type(e).__name__}: {e}"


def get_setup_checks() -> list[dict]:
    ok_data, det_data = _check_data_dir()
    ok_logs, det_logs = _check_logs_writable()
    ok_pw, det_pw = _check_playwright_import()
    ok_brows, det_brows = _check_playwright_browsers_installed()
    ok_task, det_task = _check_scheduled_task()

    checks = [
        {"key": "python", "label": "Python/Exe", "ok": True, "detail": sys.executable},
        {"key": "project", "label": "Proyecto", "ok": True, "detail": str(PROJECT_ROOT)},
        {"key": "data", "label": "Carpeta data/", "ok": ok_data, "detail": det_data},
        {"key": "logs", "label": "Logs escribibles", "ok": ok_logs, "detail": det_logs},
        {"key": "playwright", "label": "Playwright import", "ok": ok_pw, "detail": det_pw},
        {"key": "browsers", "label": "Browsers Playwright", "ok": ok_brows, "detail": det_brows},
        {"key": "task", "label": "Tarea programada", "ok": ok_task, "detail": det_task},
    ]
    return checks


@app.route("/setup", methods=["GET", "POST"])
def setup_page():
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "open_logs":
            _open_path(_logs_dir())
            flash("He abierto la carpeta logs.", "success")
            return redirect(url_for("setup_page"))

        if action == "open_data":
            _open_path(DATA_DIR)
            flash("He abierto la carpeta data.", "success")
            return redirect(url_for("setup_page"))

        if action == "fix_playwright":
            if _is_frozen():
                flash("Estás en modo .exe: Playwright debería venir incluido. Si falla, es de instalador.", "danger")
                return redirect(url_for("setup_page"))

            # Instalación user-level para evitar admin
            rc, out, err = _run_cmd([sys.executable, "-m", "pip", "install", "--user", "playwright"], cwd=PROJECT_ROOT)
            if rc == 0:
                flash("Playwright instalado/actualizado.", "success")
            else:
                flash(f"Error instalando playwright (rc={rc}). Mira logs/ o consola.", "danger")
                print(out[-2000:])
                print(err[-2000:])
            return redirect(url_for("setup_page"))

        if action == "fix_browsers":
            if _is_frozen():
                # Aun en exe, esto a veces funciona si Playwright está en el runtime
                pass
            rc, out, err = _run_cmd([sys.executable, "-m", "playwright", "install", "chromium"], cwd=PROJECT_ROOT)
            if rc == 0:
                flash("Browsers instalados (chromium).", "success")
            else:
                flash(f"Error en playwright install (rc={rc}). Revisa logs/.", "danger")
                print(out[-2000:])
                print(err[-2000:])
            return redirect(url_for("setup_page"))

        if action == "recheck":
            return redirect(url_for("setup_page"))

        flash("Acción no reconocida.", "danger")
        return redirect(url_for("setup_page"))

    checks = get_setup_checks()
    return render_template("setup.html", checks=checks)


@app.route("/compare", methods=["GET", "POST"])
def compare_keywords():
    kws_file = load_keywords_from_file()
    kws_db = load_keywords_from_db()

    seen = set()
    keywords: list[str] = []
    for kw in kws_file + kws_db:
        if kw not in seen:
            seen.add(kw)
            keywords.append(kw)

    comparison = None
    plot_url = None
    selected: list[str] = []

    if request.method == "POST":
        selected = request.form.getlist("keywords")
        selected = [k.strip() for k in selected if k.strip()]

        if len(selected) < 2:
            flash("Selecciona al menos 2 keywords para comparar.", "danger")
            return redirect(url_for("compare_keywords"))

        rows = []
        for kw in selected:
            res = get_last_run_stats(kw)
            if not res:
                continue
            scraped_at, stats = res
            q1 = stats["q1"]
            q3 = stats["q3"]
            mediana = stats["mediana"]
            rango_normal = f"{q1:.0f}–{q3:.0f} €"
            rango_rapido = f"{q1:.0f}–{mediana:.0f} €"

            rows.append(
                {
                    "keyword": kw,
                    "scraped_at": scraped_at,
                    "n": stats["n"],
                    "media": f"{stats['media']:.2f}",
                    "mediana": f"{mediana:.2f}",
                    "q1": f"{q1:.2f}",
                    "q3": f"{q3:.2f}",
                    "rango_normal": rango_normal,
                    "rango_rapido": rango_rapido,
                }
            )

        if not rows:
            flash("No hay datos suficientes en la BD para los keywords seleccionados.", "danger")
            return redirect(url_for("compare_keywords"))

        comparison = rows

        try:
            p = generar_grafico_comparacion(selected)
            if p:
                plot_url = url_for("plots_static", filename=Path(p).name)
        except Exception as e:
            print("[Valyro] Error generando gráfico de comparación:", e)
            plot_url = None

    return render_template(
        "compare.html",
        keywords=keywords,
        comparison=comparison,
        plot_url=plot_url,
        selected=selected,
    )


import re

def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "keyword"

@app.route("/keyword/<kw>/report")
def keyword_report(kw):
    kw = kw.strip()
    if not kw:
        abort(404)

    REPORTS_DIR.mkdir(exist_ok=True)
    outfile = REPORTS_DIR / f"valyro_report_{_slugify(kw)}.html"

    # Genera SIEMPRE el informe y lo sirve en el navegador
    generar_html_report(kw, outfile=str(outfile))

    return send_from_directory(REPORTS_DIR, outfile.name)



@app.route("/keyword/<kw>")
def keyword_detail(kw: str):
    kw = kw.strip()
    if not kw:
        abort(404)

    result = get_last_run_stats(kw)
    if not result:
        abort(404)

    scraped_at_new, stats = result

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

    plot_url = None

    sell_speed_raw = get_sell_speed_summary(kw)
    sell_speed = None
    if sell_speed_raw:
        ls = sell_speed_raw.get("lifetime_stats")
        sell_speed = {
            "total": sell_speed_raw["total_listings"],
            "desap": sell_speed_raw["desaparecidos"],
            "activos": sell_speed_raw["activos"],
            "pct_desap": f"{sell_speed_raw['pct_desaparecidos']:.1f}",
            "lifetime_mediana_dias": f"{ls['mediana']:.1f}" if ls else None,
            "lifetime_mediana_horas": f"{(ls['mediana'] * 24):.1f}" if ls else None,
        }

    try:
        grafico_path = generar_grafico_mean_median(kw)
        if grafico_path:
            filename = Path(grafico_path).name
            plot_url = url_for("plots_static", filename=filename)
    except Exception:
        plot_url = None

    return render_template(
        "keyword_detail.html",
        keyword=kw,
        scraped_at=scraped_at_new,
        n=n,
        media=f"{media:.2f}",
        mediana=f"{mediana:.2f}",
        minimo=f"{minimo:.2f}",
        maximo=f"{maximo:.2f}",
        q1=f"{q1:.2f}",
        q2=f"{q2:.2f}",
        q3=f"{q3:.2f}",
        rango_normal=rango_normal,
        rango_rapido=rango_rapido,
        rango_lento=rango_lento,
        plot_url=plot_url,
        sell_speed=sell_speed,
    )


@app.route("/keyword/<kw>/runs", methods=["GET", "POST"])
def keyword_runs(kw: str):
    kw = kw.strip()
    if not kw:
        abort(404)

    runs = fetch_runs_for_keyword(kw) or []

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "delete_one":
            scraped_at = request.form.get("scraped_at", "").strip()
            if not scraped_at:
                flash("No se ha indicado ninguna run a borrar.", "danger")
                return redirect(url_for("keyword_runs", kw=kw))

            scraped_values = {r[0] for r in runs}
            if scraped_at not in scraped_values:
                flash("La run seleccionada no existe para este keyword.", "danger")
                return redirect(url_for("keyword_runs", kw=kw))

            deleted = delete_run(kw, scraped_at)
            flash(f"Run {scraped_at} eliminada para '{kw}'. Filas borradas: {deleted}.", "success")
            return redirect(url_for("keyword_runs", kw=kw))

        if action == "delete_all":
            deleted = delete_all_for_keyword(kw)
            flash(f"Se han eliminado {deleted} filas de la BD para keyword = '{kw}'.", "success")
            return redirect(url_for("keyword_runs", kw=kw))

        flash("Acción no reconocida.", "danger")
        return redirect(url_for("keyword_runs", kw=kw))

    return render_template("keyword_runs.html", keyword=kw, runs=runs)




@app.route("/reports/<path:filename>")
def reports_static(filename):
    return send_from_directory(REPORTS_DIR, filename)





@app.route("/legal")
def legal_page():
    return render_template("legal.html", notice=LEGAL_NOTICE)


@app.route("/about")
def about_page():
    return render_template("about.html")


@app.route("/upgrade")
def upgrade_page():
    return render_template("upgrade.html")



def _find_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_http(url: str, timeout_s: int = 10) -> None:
    start = time.time()
    while True:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        if time.time() - start > timeout_s:
            return
        time.sleep(0.15)


def _start_flask_in_thread(port: int) -> None:
    def runner():
        # IMPORTANTE: sin reloader en exe
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=runner, daemon=True)
    t.start()


def _open_desktop_window(port: int) -> int:
    import webview  # pywebview

    url = f"http://127.0.0.1:{port}/"
    _wait_http(url, timeout_s=12)


    webview.create_window(
        "Valyro",
        url,
        width=1250,
        height=820,
        resizable=True,
        confirm_close=True,
    )
    # En Windows usará WebView2 (Edge) por debajo
    webview.start()
    return 0


FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def spa(path: str):
    if FRONTEND_DIST.is_dir():
        file_path = FRONTEND_DIST / path
        if path and file_path.is_file():
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")
    return redirect(url_for("index"))


# =============================================================================
# CLI para el .exe (Task Scheduler): valyro.exe --daily-scrape
# =============================================================================
def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--daily-scrape", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args, _rest = parser.parse_known_args()

    if args.daily_scrape:
        try:
            from scripts.daily_scrape import main as daily_main  # type: ignore
        except Exception as e:
            print("[Valyro] No puedo importar scripts.daily_scrape:", e)
            return 2
        return int(daily_main() or 0)

    # ===== MODO APP (ventana nativa sin navegador) =====
    port = _find_free_port()
    _start_flask_in_thread(port)
    return _open_desktop_window(port)



if __name__ == "__main__":
    raise SystemExit(main())
