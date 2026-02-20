from __future__ import annotations

"""Filtros de anuncios (Wallapop) para limpiar ruido típico.

Incluye:
- Filtro por texto (roto / para piezas / solo caja / busco / servicio, etc.).
- Filtro de precios: mínimo absoluto + outliers relativos a la mediana.

Diseño:
- "mode" controla SOLO el filtro estadístico (mínimo absoluto + mediana).
- El filtro por texto se controla con exclude_bad_text.

Pensado para usarse ANTES de calcular estadísticas y ANTES de guardar en BD.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import statistics
import unicodedata


# =====================
#  Presets (UI)
# =====================

# Nota: estos valores son deliberadamente "seguros" para Wallapop.
# - min_valid_price evita los 0/1€/"precio gancho".
# - lower_factor/upper_factor recortan outliers respecto a mediana.

PRESETS: Dict[str, Dict[str, float]] = {
    # Recomendado: bastante tolerante por abajo (hay anuncios rotos/piezas) y muy tolerante por arriba.
    "soft": {"min_valid_price": 5.0, "lower_factor": 0.60, "upper_factor": 4.0},
    # Más agresivo: ideal si quieres un precio "de mercado" muy limpio y la keyword es precisa.
    "strict": {"min_valid_price": 10.0, "lower_factor": 0.75, "upper_factor": 3.0},
    # Desactiva el recorte estadístico (pero puedes mantener el filtro por texto si quieres).
    "off": {"min_valid_price": 0.0, "lower_factor": 0.0, "upper_factor": 0.0},
}


def get_preset(mode: str) -> Dict[str, float]:
    m = (mode or "").strip().lower()
    if m not in PRESETS:
        m = "soft"
    return PRESETS[m]


# =====================
#  Texto: exclusiones
# =====================

# Ojo: esta lista es intencionalmente conservadora para evitar falsos positivos.
# Mejor tener algún "ruidoso" dentro que cargarte anuncios buenos.

_BAD_PHRASES = [
    # roto / mal estado
    "roto",
    "rota",
    "averiado",
    "averiada",
    "no funciona",
    "no funciona",
    "no enciende",
    "no carga",
    "pantalla rota",
    "sin probar",
    "para piezas",
    "por piezas",
    "piezas",
    "despiece",
    "repuesto",
    # incompleto / accesorio suelto
    "solo caja",
    "caja vacia",
    "caja vacía",
    "solo mando",
    "mando suelto",
    "solo cargador",
    "cargador suelto",
    "solo funda",
    "funda suelta",
    "solo carcasa",
    "carcasa suelta",
    "incompleto",
    "sin accesorios",
    # no es el producto / no es venta normal
    "busco",
    "compro",
    "se compra",
    "cambio",
    "alquilo",
    "servicio",
    "instalacion",
    "instalación",
    "reparacion",
    "reparación",
    "cuenta",
    "suscripcion",
    "suscripción",
]


def _normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    # quitar acentos
    s = "".join(
        ch
        for ch in unicodedata.normalize("NFD", s)
        if unicodedata.category(ch) != "Mn"
    )
    return s


_BAD_PHRASES_NORM = [_normalize_text(p) for p in _BAD_PHRASES]


def is_bad_by_text(product: Dict[str, Any]) -> bool:
    titulo = product.get("titulo") or ""
    desc = product.get("descripcion") or ""
    t = _normalize_text(f"{titulo} {desc}")
    if not t:
        return False

    # Un par de reglas para reducir falsos positivos:
    # - "cambio" se considera sospechoso solo si parece oferta de intercambio.
    if "cambio" in t and ("por" in t or "x" in t or "interc" in t):
        return True

    for phrase in _BAD_PHRASES_NORM:
        if phrase == "cambio":
            continue
        # match simple por substring
        if phrase and phrase in t:
            return True

    return False



# =====================
#  Intención: producto principal vs accesorio
# =====================

# Objetivo: reducir ruido típico (accesorios/juegos/solo mando/solo funda, etc.)
# sin cargarte anuncios buenos tipo "consola + mando" o "móvil con funda".
#
# Modos:
# - any: no filtra por intención.
# - primary: filtro genérico (accesorios) para la mayoría de búsquedas.
# - console: filtro más duro pensado para consolas (PS/Xbox/Switch).
# - auto: decide "console" si el keyword parece consola, si no "primary".

_ACCESSORY_PREFIXES = [
    "mando",
    "mandos",
    "controller",
    "cable",
    "cargador",
    "funda",
    "carcasa",
    "protector",
    "protector de pantalla",
    "auriculares",
    "soporte",
    "base",
    "dock",
    "adaptador",
    "bateria",
    "batería",
    "kit",
    "juego",
    "juegos",
    "volante",
    "camara",
    "cámara",
    "vr",
    "gafas",
]

_ACCESSORY_PHRASES = [
    "solo mando",
    "mando suelto",
    "solo cable",
    "solo cargador",
    "solo funda",
    "solo carcasa",
    "solo juego",
    "solo juegos",
    "sin consola",
]

_PRIMARY_MARKERS = [
    "consola",
    "telefono",
    "teléfono",
    "movil",
    "móvil",
    "smartphone",
    "portatil",
    "portátil",
    "laptop",
    "ordenador",
    "computador",
    "pc",
    "tablet",
    "ipad",
    "camara",
    "cámara",
    "dron",
    "drone",
    "tv",
    "televisor",
    "monitor",
]

_CONSOLE_KEYWORD_MARKERS = [
    "ps4",
    "ps5",
    "playstation",
    "xbox",
    "switch",
    "nintendo",
    "wii",
    "steam deck",
]

_CONSOLE_DEVICE_MARKERS = [
    "slim",
    "pro",
    "oled",
    "lite",
    "series x",
    "series s",
    "one s",
    "one x",
    "1tb",
    "2tb",
    "500gb",
    "gb",
    "tb",
    "v2",
]


def _starts_with_any(s: str, prefixes: List[str]) -> bool:
    s = (s or "").strip()
    return any(s.startswith(p) for p in prefixes if p)


def _resolve_intent_mode(intent_mode: str, keyword: Optional[str]) -> str:
    m = (intent_mode or "any").strip().lower()
    if m in ("off", "none"):
        m = "any"
    if m != "auto":
        return m

    kw = _normalize_text(keyword or "")
    if any(tok in kw for tok in _CONSOLE_KEYWORD_MARKERS):
        return "console"
    return "primary"


def _passes_primary_intent(product: Dict[str, Any], keyword: Optional[str] = None) -> bool:
    title = _normalize_text(product.get("titulo") or "")
    desc = _normalize_text(product.get("descripcion") or "")
    text = (title + " " + desc).strip()
    if not text:
        return True

    # Si el título empieza claramente por accesorio y NO hay señales de producto principal, fuera.
    if _starts_with_any(title, _ACCESSORY_PREFIXES) and not any(m in text for m in _PRIMARY_MARKERS):
        return False

    # Frases "solo X" => normalmente accesorio suelto. Si no aparece ningún marcador de producto principal, fuera.
    if any(ph in text for ph in _ACCESSORY_PHRASES) and not any(m in text for m in _PRIMARY_MARKERS):
        return False

    return True


def _passes_console_intent(product: Dict[str, Any], keyword: Optional[str] = None) -> bool:
    title = _normalize_text(product.get("titulo") or "")
    desc = _normalize_text(product.get("descripcion") or "")
    text = (title + " " + desc).strip()
    if not text:
        return True

    kw = _normalize_text(keyword or "")
    # Detecta si el keyword apunta a consola.
    kw_is_console = any(tok in kw for tok in _CONSOLE_KEYWORD_MARKERS)

    # Señales de "consola real"
    has_console_word = "consola" in text
    has_device_marker = any(m in text for m in _CONSOLE_DEVICE_MARKERS)

    # Señales de marca/modelo (si el keyword es consola, exigimos más)
    has_brand_marker = any(tok in text for tok in _CONSOLE_KEYWORD_MARKERS)

    # Señales fuertes de accesorio/juego suelto
    accessory_prefix = _starts_with_any(title, _ACCESSORY_PREFIXES)
    accessory_only_phrase = any(ph in text for ph in _ACCESSORY_PHRASES)

    if accessory_only_phrase and not has_console_word:
        return False

    # Si empieza por accesorio y no dice "consola" ni da señales de hardware, fuera.
    if accessory_prefix and (not has_console_word) and (not has_device_marker):
        return False

    # Juegos sueltos (muy típico): si no dice "consola" ni marcador hardware, fuera.
    if ("juego" in text or "juegos" in text) and (not has_console_word) and (not has_device_marker):
        return False

    # Si el anuncio dice explícitamente "consola", lo damos por bueno.
    if has_console_word:
        return True

    # Si el keyword es consola (PS/Xbox/Switch), y aparece la marca + algún marcador de hardware => bueno.
    if kw_is_console and has_brand_marker and has_device_marker:
        return True

    # Si el keyword es consola y NO hay marcador de hardware, suele ser accesorio (mando/cable/juego).
    if kw_is_console and has_brand_marker and (not has_device_marker):
        return False

    # Si no estamos seguros (keyword no era consola), no tocamos.
    return True


def passes_intent_filter(
    product: Dict[str, Any],
    *,
    intent_mode: str = "any",
    keyword: Optional[str] = None,
) -> bool:
    m = _resolve_intent_mode(intent_mode, keyword)
    if m in ("any", ""):
        return True
    if m == "primary":
        return _passes_primary_intent(product, keyword=keyword)
    if m == "console":
        return _passes_console_intent(product, keyword=keyword)
    # modo desconocido => no filtra
    return True


# =====================
#  Metadatos
# =====================


@dataclass(frozen=True)
class ListingFilterMeta:
    mode: str
    exclude_bad_text: bool
    min_valid_price: float

    total_in: int
    kept: int

    removed_text: int
    removed_min_price: int
    removed_low: int
    removed_high: int

    applied_median_filter: bool
    median_raw: Optional[float]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    n_priced_considered: int

    # Filtro extra: intención (producto principal vs accesorio)
    intent_mode: str = "any"
    removed_intent: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "exclude_bad_text": self.exclude_bad_text,
            "min_valid_price": self.min_valid_price,
            "total_in": self.total_in,
            "kept": self.kept,
            "removed_text": self.removed_text,
            "removed_min_price": self.removed_min_price,
            "removed_low": self.removed_low,
            "removed_high": self.removed_high,
            "applied_median_filter": self.applied_median_filter,
            "median_raw": self.median_raw,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "n_priced_considered": self.n_priced_considered,
            "intent_mode": self.intent_mode,
            "removed_intent": self.removed_intent,
        }


# =====================
#  Filtro de precios
# =====================


def _to_float_or_none(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def filter_price_list(
    prices: Iterable[float],
    *,
    mode: str = "soft",
    min_n_priced: int = 10,
) -> Tuple[List[float], Dict[str, Any]]:
    """Filtra una lista de precios según el preset indicado."""

    preset = get_preset(mode)
    mode = (mode or "soft").lower().strip()

    min_valid = float(preset["min_valid_price"])
    lower_factor = float(preset["lower_factor"])
    upper_factor = float(preset["upper_factor"])

    # 1) mínimo absoluto
    cleaned = [float(p) for p in prices if p is not None]
    cleaned = [p for p in cleaned if p > min_valid]

    if mode == "off":
        meta = {
            "mode": mode,
            "min_valid_price": min_valid,
            "applied_median_filter": False,
            "median_raw": None,
            "lower_bound": None,
            "upper_bound": None,
            "n_priced_considered": len(cleaned),
        }
        return cleaned, meta

    if len(cleaned) < min_n_priced:
        meta = {
            "mode": mode,
            "min_valid_price": min_valid,
            "applied_median_filter": False,
            "median_raw": None,
            "lower_bound": None,
            "upper_bound": None,
            "n_priced_considered": len(cleaned),
        }
        return cleaned, meta

    median_raw = float(statistics.median(cleaned))
    if median_raw <= 0:
        meta = {
            "mode": mode,
            "min_valid_price": min_valid,
            "applied_median_filter": False,
            "median_raw": median_raw,
            "lower_bound": None,
            "upper_bound": None,
            "n_priced_considered": len(cleaned),
        }
        return cleaned, meta

    lower = median_raw * lower_factor
    upper = median_raw * upper_factor

    filtered = [p for p in cleaned if (p >= lower and p <= upper)]

    meta = {
        "mode": mode,
        "min_valid_price": min_valid,
        "applied_median_filter": True,
        "median_raw": median_raw,
        "lower_bound": lower,
        "upper_bound": upper,
        "n_priced_considered": len(cleaned),
    }
    return filtered, meta


# =====================
#  Filtro de anuncios
# =====================


def apply_listing_filters(
    products: List[Dict[str, Any]],
    *,
    mode: str = "soft",
    exclude_bad_text: bool = True,
    intent_mode: str = "any",
    keyword: Optional[str] = None,
    price_key: str = "precio",
    min_n_priced: int = 10,
) -> Tuple[List[Dict[str, Any]], ListingFilterMeta]:
    """Aplica filtros combinados y devuelve (productos_filtrados, meta).

    Orden de aplicación (importa):
    1) Texto (roto/para piezas/busco/solo caja/etc.)
    2) Intención (producto principal vs accesorio)  [opcional]
    3) Precio mínimo absoluto
    4) Outliers por mediana (según preset)
    """

    total_in = len(products)
    preset = get_preset(mode)
    min_valid = float(preset["min_valid_price"])
    lower_factor = float(preset["lower_factor"])
    upper_factor = float(preset["upper_factor"])
    mode_norm = (mode or "soft").strip().lower()

    removed_text = 0
    removed_intent = 0
    removed_min_price = 0
    removed_low = 0
    removed_high = 0

    # 1) filtro por texto
    tmp: List[Dict[str, Any]] = []
    if exclude_bad_text:
        for p in products:
            if is_bad_by_text(p):
                removed_text += 1
                continue
            tmp.append(p)
    else:
        tmp = list(products)

    # 2) filtro por intención (producto principal vs accesorio)
    resolved_intent = _resolve_intent_mode(intent_mode, keyword)
    tmp_intent: List[Dict[str, Any]] = []
    if resolved_intent in ("any", ""):
        tmp_intent = tmp
    else:
        for p in tmp:
            if not passes_intent_filter(p, intent_mode=resolved_intent, keyword=keyword):
                removed_intent += 1
                continue
            tmp_intent.append(p)

    # 3) mínimo absoluto
    tmp2: List[Dict[str, Any]] = []
    for p in tmp_intent:
        price = _to_float_or_none(p.get(price_key))
        if price is None:
            tmp2.append(p)
            continue
        if price <= min_valid:
            removed_min_price += 1
            continue
        tmp2.append(p)

    # 4) mediana/outliers (solo si mode != off)
    applied_median_filter = False
    median_raw: Optional[float] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None

    if mode_norm != "off":
        priced = [
            _to_float_or_none(p.get(price_key))
            for p in tmp2
            if _to_float_or_none(p.get(price_key)) is not None
        ]
        priced = [p for p in priced if p is not None]
        n_priced_considered = len(priced)

        if n_priced_considered >= min_n_priced:
            median_raw = float(statistics.median(priced))
            if median_raw > 0:
                lower_bound = median_raw * lower_factor
                upper_bound = median_raw * upper_factor
                applied_median_filter = True
    else:
        n_priced_considered = len([p for p in tmp2 if _to_float_or_none(p.get(price_key)) is not None])

    out: List[Dict[str, Any]] = []
    if not applied_median_filter:
        out = tmp2
    else:
        assert lower_bound is not None and upper_bound is not None
        for p in tmp2:
            price = _to_float_or_none(p.get(price_key))
            if price is None:
                out.append(p)
                continue
            if price < lower_bound:
                removed_low += 1
                continue
            if price > upper_bound:
                removed_high += 1
                continue
            out.append(p)

    meta = ListingFilterMeta(
        mode=mode_norm,
        exclude_bad_text=bool(exclude_bad_text),
        min_valid_price=min_valid,
        total_in=total_in,
        kept=len(out),
        removed_text=removed_text,
        removed_min_price=removed_min_price,
        removed_low=removed_low,
        removed_high=removed_high,
        applied_median_filter=applied_median_filter,
        median_raw=median_raw,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        n_priced_considered=int(n_priced_considered),
        intent_mode=str(resolved_intent),
        removed_intent=int(removed_intent),
    )

    return out, meta
