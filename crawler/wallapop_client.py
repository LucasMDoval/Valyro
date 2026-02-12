from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

import random
import re
import json

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
    """
    Filtro tolerante:
    - Si substring está vacío => True.
    - Si todos los tokens aparecen en el texto (en cualquier orden) => True.
    """
    q = (substring or "").lower().strip()
    t = (text or "").lower()

    if not q:
        return True

    tokens = q.split()
    return all(tok in t for tok in tokens)


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
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


def _looks_like_listing_items(items: Any) -> bool:
    """Heurística: lista de dicts con pinta de producto Wallapop."""
    if not isinstance(items, list) or not items:
        return False
    first = items[0]
    if not isinstance(first, dict):
        return False
    return (
        "id" in first
        and ("title" in first or "description" in first)
        and ("price" in first or "web_slug" in first)
    )


def _extract_items_from_json(data: Any) -> Optional[List[Dict[str, Any]]]:
    """
    Devuelve la lista de productos (items) desde respuestas Wallapop.

    Rutas soportadas:
    - NUEVA (la que tú has visto): data.section.items
    - Antigua del proyecto: data.section.payload.items
    - Otros casos: items / payload.items / data.items
    - Fallback recursivo
    """

    # Descarta JSON de Next.js (UI/i18n)
    if isinstance(data, dict) and "pageProps" in data:
        pp = data.get("pageProps")
        if isinstance(pp, dict) and "i18nMessages" in pp:
            return None

    if isinstance(data, dict):
        # ✅ NUEVO: data.section.items (tu caso)
        try:
            sec = (data.get("data") or {}).get("section")
            if isinstance(sec, dict):
                items = sec.get("items")
                if _looks_like_listing_items(items):
                    return items  # type: ignore[return-value]
        except Exception:
            pass

        # Ruta "antigua": data.section.payload.items
        try:
            items = (
                (((data.get("data") or {}).get("section") or {}).get("payload") or {}).get("items")
            )
            if _looks_like_listing_items(items):
                return items  # type: ignore[return-value]
        except Exception:
            pass

        # Rutas comunes
        for candidate in (
            data.get("items"),
            (data.get("payload") or {}).get("items") if isinstance(data.get("payload"), dict) else None,
            (data.get("data") or {}).get("items") if isinstance(data.get("data"), dict) else None,
        ):
            if _looks_like_listing_items(candidate):
                return candidate  # type: ignore[return-value]

        # Búsqueda recursiva
        for v in data.values():
            found = _extract_items_from_json(v)
            if found:
                return found

    elif isinstance(data, list):
        # Si el JSON ya es una lista de items
        if _looks_like_listing_items(data):
            return data  # type: ignore[return-value]

        for v in data:
            found = _extract_items_from_json(v)
            if found:
                return found

    return None


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
) -> List[Dict[str, Any]]:
    cfg = SCRAPER_SETTINGS.get(DEFAULT_SCRAPER_MODE, SCRAPER_SETTINGS["respectful"])
    INITIAL_WAIT_MS = cfg["INITIAL_WAIT_MS"]
    AFTER_CLICK_WAIT_MS = cfg["AFTER_CLICK_WAIT_MS"]
    AFTER_SCROLL_WAIT_MS = cfg["AFTER_SCROLL_WAIT_MS"]
    MAX_EMPTY_ITERATIONS = cfg["MAX_EMPTY_ITERATIONS"]
    SCROLL_DELTA = cfg["SCROLL_DELTA"]

    # ⚠️ IMPORTANTE: no autofiltrar por keyword; solo filtrar si el usuario lo pasa
    substring = (substring_filter or "").strip() or None

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

    productos: List[Dict[str, Any]] = []
    vistos: set[str] = set()
    search_hits = {"count": 0}
    logged_endpoint = {"done": False}

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

            u = response.url

            # Ignora terceros (amplitude, sentry, etc.)
            if "wallapop.com" not in u:
                return

            # Reducimos ruido: solo endpoints típicos donde sale el JSON de items
            if not ("section?" in u or "search?" in u or "/api/" in u or "_next" in u):
                return

            if response.status != 200:
                return

            # Parse JSON (aunque el content-type venga raro)
            try:
                data = response.json()
            except Exception:
                try:
                    txt = response.text()
                    if not txt or not txt.lstrip().startswith(("{", "[")):
                        return
                    data = json.loads(txt)
                except Exception:
                    return

            items = _extract_items_from_json(data)
            if not items:
                return

            search_hits["count"] += 1
            if not logged_endpoint["done"]:
                logged_endpoint["done"] = True
                log.info(f"Endpoint de items detectado: {response.status} {u}")

            for item in items:
                if len(productos) >= limit:
                    break
                if not isinstance(item, dict):
                    continue

                item_id = item.get("id")
                if not item_id:
                    continue
                item_id_str = str(item_id)
                if item_id_str in vistos:
                    continue
                vistos.add(item_id_str)

                titulo = (item.get("title") or "").strip()
                descripcion = (item.get("description") or "").strip()
                texto = (titulo + " " + descripcion).strip()

                if substring and not matches_filter(substring, texto):
                    continue

                precio = None
                try:
                    precio = (item.get("price") or {}).get("amount")
                except Exception:
                    precio = None

                loc = item.get("location") or {}
                ciudad = loc.get("city") if isinstance(loc, dict) else None
                created_at = item.get("created_at")

                web_slug = item.get("web_slug")
                url_publica = f"https://es.wallapop.com/item/{web_slug}" if web_slug else None

                productos.append(
                    {
                        "platform": "wallapop",
                        "id": item_id_str,
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

                log.info(
                    f"Productos que pasan el filtro: {ahora}/{limit} (vacías seguidas={intentos_sin_nuevos})"
                )

            log.info(f"Scraping terminado. Total productos crudos: {len(productos)}")

            if search_hits["count"] == 0:
                msg = (
                    "No se ha detectado ninguna respuesta JSON con items de búsqueda. "
                    "Posible cambio de endpoint/estructura, bloqueo (403/429) o respuesta no-JSON (captcha)."
                )
                log.warning(msg)
                if strict:
                    raise RuntimeError(msg)

        finally:
            browser.close()

    productos_normalizados = [_normalize_item(p) for p in productos]
    log.info(f"Total productos normalizados: {len(productos_normalizados)}")
    return productos_normalizados
