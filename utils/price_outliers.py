from __future__ import annotations

"""Utilidades para filtrar outliers de precio basados en la mediana.

Regla por defecto:
  - fuera si precio < 0.8 * mediana  (20% por debajo)
  - fuera si precio > 4.0 * mediana  (300% por encima => +300% = x4)

Se aplica únicamente si hay suficientes precios válidos, para evitar que
una muestra pequeña distorsione el filtro.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import statistics


DEFAULT_LOWER_FACTOR = 0.8
DEFAULT_UPPER_FACTOR = 4.0


@dataclass(frozen=True)
class OutlierFilterMeta:
    applied: bool
    median_raw: Optional[float]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    n_priced: int
    removed_low: int
    removed_high: int
    kept_priced: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "applied": self.applied,
            "median_raw": self.median_raw,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "n_priced": self.n_priced,
            "removed_low": self.removed_low,
            "removed_high": self.removed_high,
            "kept_priced": self.kept_priced,
        }


def _bounds_from_median(
    median: float,
    *,
    lower_factor: float,
    upper_factor: float,
) -> Tuple[float, float]:
    return (median * float(lower_factor), median * float(upper_factor))


def filter_prices_by_median(
    prices: Iterable[float],
    *,
    lower_factor: float = DEFAULT_LOWER_FACTOR,
    upper_factor: float = DEFAULT_UPPER_FACTOR,
    min_n_priced: int = 10,
) -> Tuple[List[float], OutlierFilterMeta]:
    """Filtra una lista de precios usando umbrales relativos a la mediana."""

    precios = [float(p) for p in prices if p is not None]
    n_priced = len(precios)
    if n_priced < min_n_priced:
        meta = OutlierFilterMeta(
            applied=False,
            median_raw=None,
            lower_bound=None,
            upper_bound=None,
            n_priced=n_priced,
            removed_low=0,
            removed_high=0,
            kept_priced=n_priced,
        )
        return precios, meta

    median_raw = float(statistics.median(precios))
    # Si la mediana es 0 (o negativa), la regla multiplicativa no tiene sentido.
    if median_raw <= 0:
        meta = OutlierFilterMeta(
            applied=False,
            median_raw=median_raw,
            lower_bound=None,
            upper_bound=None,
            n_priced=n_priced,
            removed_low=0,
            removed_high=0,
            kept_priced=n_priced,
        )
        return precios, meta

    lower, upper = _bounds_from_median(median_raw, lower_factor=lower_factor, upper_factor=upper_factor)

    filtered: List[float] = []
    removed_low = 0
    removed_high = 0
    for p in precios:
        if p < lower:
            removed_low += 1
            continue
        if p > upper:
            removed_high += 1
            continue
        filtered.append(p)

    meta = OutlierFilterMeta(
        applied=True,
        median_raw=median_raw,
        lower_bound=lower,
        upper_bound=upper,
        n_priced=n_priced,
        removed_low=removed_low,
        removed_high=removed_high,
        kept_priced=len(filtered),
    )
    return filtered, meta


def filter_products_by_median(
    products: List[Dict[str, Any]],
    *,
    price_key: str = "precio",
    lower_factor: float = DEFAULT_LOWER_FACTOR,
    upper_factor: float = DEFAULT_UPPER_FACTOR,
    min_n_priced: int = 10,
) -> Tuple[List[Dict[str, Any]], OutlierFilterMeta]:
    """Filtra anuncios con precio fuera de rango respecto a la mediana.

    - Mantiene anuncios sin precio (price_key None) tal cual.
    - Solo filtra los que tienen precio numérico.
    """

    precios = [p.get(price_key) for p in products if p.get(price_key) is not None]
    precios_f, meta = filter_prices_by_median(
        precios,
        lower_factor=lower_factor,
        upper_factor=upper_factor,
        min_n_priced=min_n_priced,
    )

    if not meta.applied:
        return products, meta

    # Usamos los bounds calculados
    lower = meta.lower_bound
    upper = meta.upper_bound
    if lower is None or upper is None:
        return products, meta

    out: List[Dict[str, Any]] = []
    for p in products:
        price = p.get(price_key)
        if price is None:
            out.append(p)
            continue
        try:
            pf = float(price)
        except Exception:
            # Si el precio no parsea, lo mantenemos y que lo descarte la capa de stats.
            out.append(p)
            continue
        if pf < lower or pf > upper:
            continue
        out.append(p)

    return out, meta
