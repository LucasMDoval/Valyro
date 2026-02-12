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
    price_key: str = "precio",
    min_n_priced: int = 10,
) -> Tuple[List[Dict[str, Any]], ListingFilterMeta]:
    """Aplica filtros combinados y devuelve (productos_filtrados, meta)."""

    total_in = len(products)
    preset = get_preset(mode)
    min_valid = float(preset["min_valid_price"])
    lower_factor = float(preset["lower_factor"])
    upper_factor = float(preset["upper_factor"])
    mode_norm = (mode or "soft").strip().lower()

    removed_text = 0
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

    # 2) mínimo absoluto
    tmp2: List[Dict[str, Any]] = []
    for p in tmp:
        price = _to_float_or_none(p.get(price_key))
        if price is None:
            tmp2.append(p)
            continue
        if price <= min_valid:
            removed_min_price += 1
            continue
        tmp2.append(p)

    # 3) mediana/outliers (solo si mode != off)
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
    )

    return out, meta
