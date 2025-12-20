import os
import json
import time
import random
from datetime import datetime, date
from pathlib import Path
import argparse

from crawler.wallapop_client import fetch_products
from storage.db import save_products

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
KEYWORDS_FILE = DATA_DIR / "daily_keywords.txt"

STATE_PATH = DATA_DIR / "daily_scrape_state.json"
LOCK_PATH = DATA_DIR / "daily_scrape.lock"
DEFAULTS_PATH = DATA_DIR / "daily_scrape_config.json"  # opcional: defaults globales

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
    cfg = {
        "order_by": "most_relevance",
        "limit": 300,
        "min_price": None,
        "max_price": None,
    }
    try:
        if DEFAULTS_PATH.is_file():
            data = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if data.get("order_by") in ALLOWED_ORDERS:
                    cfg["order_by"] = data["order_by"]
                if data.get("limit") is not None:
                    try:
                        cfg["limit"] = int(data["limit"])
                    except Exception:
                        pass
                cfg["min_price"] = _num_or_none(data.get("min_price"))
                cfg["max_price"] = _num_or_none(data.get("max_price"))
    except Exception:
        pass

    # clamp
    cfg["limit"] = max(1, min(1000, int(cfg["limit"] or 300)))

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
    }

    for token in parts[1:]:
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        k = k.strip().lower()
        v = v.strip()

        if k == "order_by":
            if v in ALLOWED_ORDERS:
                cfg["order_by"] = v

        elif k == "limit":
            try:
                cfg["limit"] = max(1, min(1000, int(v)))
            except Exception:
                pass

        elif k in ("min", "min_price"):
            cfg["min_price"] = _num_or_none(v)

        elif k in ("max", "max_price"):
            cfg["max_price"] = _num_or_none(v)

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

    for attempt in range(1, max_retries + 1):
        print(f"\n[{datetime.now().isoformat()}] Keyword='{kw}' intento {attempt}/{max_retries}")
        print(f"Config kw: order_by={order_by}, limit={limit}, min={min_price}, max={max_price}")

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
