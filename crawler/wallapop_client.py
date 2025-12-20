from typing import List, Dict, Optional
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import re
import random
import os

from utils.logger import get_logger

log = get_logger("scraper")

DEFAULT_SCRAPER_MODE = "respectful"

SCRAPER_SETTINGS = {
    "respectful": {
        "INITIAL_WAIT_MS": 2500,
        "AFTER_CLICK_WAIT_MS": 2600,
        "AFTER_SCROLL_WAIT_MS": 2600,
        "MAX_EMPTY_ITERATIONS": 5,
        "SCROLL_DELTA": 7000,
    },
    "fast": {
        "INITIAL_WAIT_MS": 1200,
        "AFTER_CLICK_WAIT_MS": 1400,
        "AFTER_SCROLL_WAIT_MS": 1400,
        "MAX_EMPTY_ITERATIONS": 3,
        "SCROLL_DELTA": 6000,
    },
}


def matches_filter(substring: str, text: str) -> bool:
    q = (substring or "").lower().strip()
    t = (text or "").lower()

    if not q:
        return True
    if q in t:
        return True

    tokens = q.split()
    if len(tokens) < 3:
        return False

    t_tokens = t.split()

    for i in range(len(t_tokens) - 1):
        first_ok = tokens[0] in t_tokens[i]
        second_ok = tokens[1] in t_tokens[i + 1]
        if not (first_ok and second_ok):
            continue

        j = i + 2
        ok = True
        for qt in tokens[2:]:
            found = False
            while j < len(t_tokens):
                if qt in t_tokens[j]:
                    found = True
                    j += 1
                    break
                j += 1
            if not found:
                ok = False
                break

        if ok:
            return True

    return False


def _normalize_item(item: Dict) -> Dict:
    precio = item.get("precio")
    try:
        precio = float(precio) if precio is not None else None
    except (TypeError, ValueError):
        precio = None

    return {
        "platform": "wallapop",
        "id": str(item.get("id")) if item.get("id") is not None else None,
        "titulo": (item.get("titulo") or "").strip(),
        "descripcion": (item.get("descripcion") or "").strip(),
        "precio": precio,
        "ciudad": (item.get("ciudad") or "").strip(),
        "created_at": item.get("created_at"),
        "url": item.get("url"),
    }


def fetch_products(
    keyword: str,
    order_by: str = "most_relevance",
    limit: int = 100,
    substring_filter: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    *,
    headless: bool = False,
    strict: bool = False,
) -> List[Dict]:
    cfg = SCRAPER_SETTINGS.get(DEFAULT_SCRAPER_MODE, SCRAPER_SETTINGS["respectful"])
    INITIAL_WAIT_MS = cfg["INITIAL_WAIT_MS"]
    AFTER_CLICK_WAIT_MS = cfg["AFTER_CLICK_WAIT_MS"]
    AFTER_SCROLL_WAIT_MS = cfg["AFTER_SCROLL_WAIT_MS"]
    MAX_EMPTY_ITERATIONS = cfg["MAX_EMPTY_ITERATIONS"]
    SCROLL_DELTA = cfg["SCROLL_DELTA"]

    substring = substring_filter or keyword

    base = "https://es.wallapop.com/search"
    params = [
        "source=search_box",
        f"keywords={quote_plus(keyword)}",
        "category_id=24200",
        f"order_by={order_by}",
    ]

    if min_price is not None:
        params.append(f"min_sale_price={int(min_price)}")
    if max_price is not None:
        params.append(f"max_sale_price={int(max_price)}")

    url = base + "?" + "&".join(params)

    productos: List[Dict] = []
    vistos = set()
    search_hits = {"count": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        def handle_response(response):
            nonlocal productos

            if len(productos) >= limit:
                return
            if "api/v3/search" not in response.url:
                return

            search_hits["count"] += 1

            try:
                data = response.json()
            except Exception:
                return

            section = data.get("data", {}).get("section", {})
            payload = section.get("payload", {})
            items = payload.get("items", [])

            for item in items:
                if len(productos) >= limit:
                    break

                item_id = item.get("id")
                if not item_id or item_id in vistos:
                    continue
                vistos.add(item_id)

                titulo = (item.get("title") or "").strip()
                descripcion = (item.get("description") or "").strip()
                texto = titulo + " " + descripcion

                if substring and not matches_filter(substring, texto):
                    continue

                precio = item.get("price", {}).get("amount")
                ciudad = item.get("location", {}).get("city")
                created_at = item.get("created_at")

                web_slug = item.get("web_slug")
                url_publica = f"https://es.wallapop.com/item/{web_slug}" if web_slug else None

                productos.append(
                    {
                        "platform": "wallapop",
                        "id": item_id,
                        "titulo": titulo,
                        "descripcion": descripcion,
                        "precio": precio,
                        "ciudad": ciudad,
                        "created_at": created_at,
                        "url": url_publica,
                    }
                )

        page.on("response", handle_response)

        try:
            log.info(
                f"Buscando '{keyword}' (orden={order_by}, límite={limit}, filtro='{substring}', "
                f"min_price={min_price}, max_price={max_price}, headless={headless}, strict={strict})"
            )
            log.info(f"Modo scraper: {DEFAULT_SCRAPER_MODE}")
            log.info(f"Abriendo URL: {url}")

            loaded = False
            for attempt in range(2):
                try:
                    page.goto(url, wait_until="networkidle", timeout=15000)
                    loaded = True
                    break
                except PlaywrightTimeoutError as e:
                    log.warning(f"Timeout al cargar la página (intento {attempt+1}): {e}")
                    page.wait_for_timeout(2000)
                except Exception as e:
                    log.warning(f"Error al cargar la página (intento {attempt+1}): {e}")
                    page.wait_for_timeout(2000)

            if not loaded:
                try:
                    page.goto(url, timeout=15000)
                except Exception as e:
                    log.error(f"No se pudo cargar la página de búsqueda: {e}", exc_info=True)
                    return []

            page.wait_for_timeout(INITIAL_WAIT_MS)

            try:
                btn_cookie = page.get_by_role("button", name=re.compile("aceptar", re.IGNORECASE))
                btn_cookie.click(timeout=2000)
                log.info("Cookies aceptadas automáticamente.")
            except Exception:
                log.info("No se pudo clicar cookies (quizá no hay overlay).")

            page.wait_for_timeout(INITIAL_WAIT_MS)

            intentos_sin_nuevos = 0
            prev_len = len(productos)

            while len(productos) < limit and intentos_sin_nuevos < MAX_EMPTY_ITERATIONS:
                clicked = False
                try:
                    load_more = page.get_by_role("button", name=re.compile("cargar más", re.IGNORECASE))
                    if load_more.is_visible():
                        for attempt in range(2):
                            try:
                                load_more.click(timeout=2500)
                                clicked = True
                                log.info("Click en 'Cargar más'")
                                break
                            except Exception as e:
                                log.warning(f"Fallo al clicar 'Cargar más' (intento {attempt+1}): {e}")
                                page.wait_for_timeout(1000)
                except Exception:
                    clicked = False

                if not clicked:
                    page.mouse.wheel(0, SCROLL_DELTA)
                    log.info("Scroll (no hay botón 'Cargar más').")

                base_wait = AFTER_CLICK_WAIT_MS if clicked else AFTER_SCROLL_WAIT_MS
                wait_ms = base_wait + random.randint(-400, 400)
                if wait_ms < 800:
                    wait_ms = 800
                page.wait_for_timeout(wait_ms)

                ahora = len(productos)
                if ahora == prev_len:
                    intentos_sin_nuevos += 1
                else:
                    intentos_sin_nuevos = 0
                    prev_len = ahora

                log.info(f"Productos que pasan el filtro: {ahora}/{limit} (vacías seguidas={intentos_sin_nuevos})")

            log.info(f"Scraping terminado. Total productos crudos: {len(productos)}")

            if search_hits["count"] == 0:
                msg = (
                    "No se ha recibido ninguna respuesta 'api/v3/search'. "
                    "Posible captcha/cambio/bloqueo."
                )
                log.warning(msg)
                if strict:
                    raise RuntimeError(msg)

        finally:
            browser.close()

    productos_normalizados = [_normalize_item(p) for p in productos]
    log.info(f"Total productos normalizados: {len(productos_normalizados)}")
    return productos_normalizados
