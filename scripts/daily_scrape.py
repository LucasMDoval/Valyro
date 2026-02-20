import os
import json
import time
import random
from datetime import datetime, date
from pathlib import Path
import argparse

from crawler.wallapop_client import fetch_products
from utils.db import save_products
from utils.listing_filters import apply_listing_filters

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
KEYWORDS_FILE = DATA_DIR / "daily_keywords.txt"

STATE_PATH = DATA_DIR / "daily_scrape_state.json"
LOCK_PATH = DATA_DIR / "daily_scrape.lock"
DEFAULTS_PATH = DATA_DIR / "daily_scrape_config.json"  # opcional: defaults globales (solo min/max)

# === Fijos por requisito del proyecto ===
FIXED_ORDER_BY = "most_relevance"
FIXED_LIMIT = 500

ALLOWED_ORDERS = {"most_relevance", "price_low_to_high", "price_high_to_low", "newest"}


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


def load_defaults() -> dict:
    """
    Defaults globales opcionales (si existe daily_scrape_config.json).
    Si no existe, usa defaults razonables.
    """
    # En este proyecto, order_by y limit NO son configurables por el usuario:
    # siempre se usa 500 + "most_relevance".
    cfg = {
        "order_by": FIXED_ORDER_BY,
        "limit": FIXED_LIMIT,
        "min_price": None,
        "max_price": None,
        # Filtros recomendados para Wallapop
        "filter_mode": "soft",
        "exclude_bad_text": True,
    }
    try:
        if DEFAULTS_PATH.is_file():
            data = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # order_by y limit: ignorados a propósito (fijos)
                cfg["min_price"] = _num_or_none(data.get("min_price"))
                cfg["max_price"] = _num_or_none(data.get("max_price"))
                fm = str(data.get("filter_mode") or "").strip().lower()
                if fm in ("soft", "strict", "off"):
                    cfg["filter_mode"] = fm
                ebt = data.get("exclude_bad_text")
                if isinstance(ebt, bool):
                    cfg["exclude_bad_text"] = ebt
    except Exception:
        pass

    # clamp (por seguridad)
    cfg["limit"] = max(1, min(1000, int(cfg["limit"] or FIXED_LIMIT)))

    # swap if needed
    if cfg["min_price"] is not None and cfg["max_price"] is not None and cfg["min_price"] > cfg["max_price"]:
        cfg["min_price"], cfg["max_price"] = cfg["max_price"], cfg["min_price"]

    return cfg


def parse_keyword_line(line: str, defaults: dict) -> dict | None:
    """
    Formato:
      keyword | order_by=newest | limit=300 | min=100 | max=500
    Devuelve dict con keyword + overrides aplicados sobre defaults.
    """
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None

    parts = [p.strip() for p in raw.split("|") if p.strip()]
    if not parts:
        return None

    kw = parts[0]
    cfg = {
        "keyword": kw,
        "order_by": defaults["order_by"],
        "limit": defaults["limit"],
        "min_price": defaults["min_price"],
        "max_price": defaults["max_price"],
        "filter_mode": defaults.get("filter_mode", "soft"),
        "exclude_bad_text": bool(defaults.get("exclude_bad_text", True)),
    }

    for token in parts[1:]:
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        k = k.strip().lower()
        v = v.strip()

        # order_by y limit: ignorados a propósito (fijos)
        if k in ("order_by", "limit"):
            continue

        elif k in ("min", "min_price"):
            cfg["min_price"] = _num_or_none(v)

        elif k in ("max", "max_price"):
            cfg["max_price"] = _num_or_none(v)

        elif k in ("filter", "filter_mode", "mode"):
            vv = str(v).strip().lower()
            if vv in ("soft", "strict", "off"):
                cfg["filter_mode"] = vv

        elif k in ("exclude_bad_text", "text_filter", "exclude_bad"):
            vv = str(v).strip().lower()
            if vv in ("1", "true", "yes", "on"):
                cfg["exclude_bad_text"] = True
            elif vv in ("0", "false", "no", "off"):
                cfg["exclude_bad_text"] = False

    if cfg["min_price"] is not None and cfg["max_price"] is not None and cfg["min_price"] > cfg["max_price"]:
        cfg["min_price"], cfg["max_price"] = cfg["max_price"], cfg["min_price"]

    return cfg


def load_keywords_with_cfg() -> list[dict]:
    defaults = load_defaults()

    if not KEYWORDS_FILE.is_file():
        return []

    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    for ln in lines:
        item = parse_keyword_line(ln, defaults)
        if item:
            out.append(item)
    return out


def load_state() -> dict:
    try:
        if STATE_PATH.is_file():
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"last_run_date": None, "keywords": {}}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def acquire_lock() -> bool:
    DATA_DIR.mkdir(exist_ok=True)
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"pid={os.getpid()}\nstarted_at={datetime.now().isoformat()}\n")
        return True
    except FileExistsError:
        return False


def release_lock() -> None:
    try:
        if LOCK_PATH.is_file():
            LOCK_PATH.unlink()
    except Exception:
        pass


def run_one_keyword(item: dict, *, max_retries: int, base_backoff_s: int) -> bool:
    kw = item["keyword"]
    order_by = item["order_by"]
    limit = item["limit"]
    min_price = item["min_price"]
    max_price = item["max_price"]
    filter_mode = item.get("filter_mode", "soft")
    exclude_bad_text = bool(item.get("exclude_bad_text", True))

    for attempt in range(1, max_retries + 1):
        print(f"\n[{datetime.now().isoformat()}] Keyword='{kw}' intento {attempt}/{max_retries}")
        print(
            f"Config kw: order_by={order_by}, limit={limit}, min={min_price}, max={max_price}, "
            f"filter_mode={filter_mode}, text_filter={'on' if exclude_bad_text else 'off'}"
        )

        try:
            productos = fetch_products(
                keyword=kw,
                order_by=order_by,
                limit=limit,
                substring_filter=kw,
                min_price=min_price,
                max_price=max_price,
            )

            if not productos:
                raise RuntimeError("0 resultados devueltos (o fallo silencioso).")

            # Limpieza Wallapop: texto + mínimo absoluto + outliers por mediana
            productos, meta = apply_listing_filters(
                productos,
                mode=filter_mode,
                exclude_bad_text=exclude_bad_text,
            )
            if meta.total_in != meta.kept:
                msg = (
                    f"[Filtros] mode={meta.mode} | text_filter={'on' if meta.exclude_bad_text else 'off'} | "
                    f"min_valid={meta.min_valid_price:.0f}€ | "
                    f"quitados: texto={meta.removed_text}, intent={getattr(meta, 'removed_intent', 0)}, <=min={meta.removed_min_price}"
                )
                if meta.applied_median_filter and meta.median_raw and meta.lower_bound and meta.upper_bound:
                    msg += (
                        f", mediana={meta.median_raw:.2f}€ rango=({meta.lower_bound:.2f}–{meta.upper_bound:.2f})€ "
                        f"fuera: bajos={meta.removed_low}, altos={meta.removed_high}"
                    )
                print(msg)

            inserted = save_products(kw, productos)
            print(f"✅ OK '{kw}' (insertados {inserted})")
            return True

        except Exception as e:
            print(f"⚠️ FAIL '{kw}': {e}")
            if attempt < max_retries:
                sleep_s = base_backoff_s * (2 ** (attempt - 1)) + random.randint(0, 10)
                print(f"Reintentando en {sleep_s}s...")
                time.sleep(sleep_s)

    return False


def main():
    parser = argparse.ArgumentParser(description="Daily scrape por keyword (nativo Wallapop)")
    parser.add_argument("--force", action="store_true", help="Ejecuta aunque ya se haya ejecutado hoy")
    parser.add_argument("--max_retries", type=int, default=3, help="Reintentos por keyword (default=3)")
    parser.add_argument("--base_backoff_s", type=int, default=15, help="Backoff base en segundos (default=15)")
    parser.add_argument("--jitter_s", type=int, default=60, help="Espera aleatoria inicial 0..jitter_s (default=60)")
    args = parser.parse_args()

    if args.jitter_s > 0:
        j = random.randint(0, args.jitter_s)
        print(f"[Valyro] Jitter inicial: durmiendo {j}s")
        time.sleep(j)

    if not acquire_lock():
        print("[Valyro] Ya hay un daily_scrape en ejecución (lock activo). Salgo.")
        return 0

    try:
        state = load_state()
        today = date.today().isoformat()

        if (not args.force) and state.get("last_run_date") == today:
            print(f"[Valyro] Ya se ejecutó hoy ({today}). Salgo (usa --force para forzar).")
            return 0

        items = load_keywords_with_cfg()
        if not items:
            print("[Valyro] No hay keywords configuradas en data/daily_keywords.txt. Salgo.")
            return 0

        print(f"=== DAILY SCRAPE INICIADO: {datetime.now().isoformat()} ===")
        print(f"Total keywords: {len(items)}")
        print("============================================================")

        ok_all = True
        for item in items:
            kw = item["keyword"]
            ok = run_one_keyword(
                item,
                max_retries=max(1, args.max_retries),
                base_backoff_s=max(1, args.base_backoff_s),
            )

            state.setdefault("keywords", {}).setdefault(kw, {})
            state["keywords"][kw]["last_attempt_at"] = datetime.now().isoformat()
            state["keywords"][kw]["last_ok"] = bool(ok)
            if ok:
                state["keywords"][kw]["last_success_at"] = datetime.now().isoformat()
            else:
                ok_all = False

            save_state(state)

        state["last_run_date"] = today
        state["last_run_finished_at"] = datetime.now().isoformat()
        state["last_run_ok"] = bool(ok_all)
        save_state(state)

        print(f"\n=== DAILY SCRAPE TERMINADO: {datetime.now().isoformat()} (ok_all={ok_all}) ===")
        return 0 if ok_all else 10

    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
