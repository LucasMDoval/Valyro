from pathlib import Path
import sys
from typing import Optional

# Aseguramos raíz del proyecto en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler.wallapop_client import fetch_products
from utils.logger import get_logger


log = get_logger("selftest")


def run_self_test(keyword: str = "iphone 12", limit: int = 30) -> bool:
    """
    Ejecuta un test básico del scraper:
      - Intenta obtener `limit` productos para `keyword`.
      - Verifica que haya al menos 1 producto con precio y URL.
    Devuelve True si el test pasa, False si falla.
    """
    log.info(f"[SELFTEST] Iniciando self-test con keyword='{keyword}', limit={limit}")

    try:
        productos = fetch_products(keyword=keyword, order_by="most_relevance", limit=limit)
    except Exception as e:
        log.error(f"[SELFTEST] Error ejecutando fetch_products: {e}", exc_info=True)
        print("❌ SELF-TEST: error ejecutando el scraper (ver logs/app.log para detalles).")
        return False

    total = len(productos)
    print(f"SELF-TEST: productos recibidos = {total}")

    if total == 0:
        print("❌ SELF-TEST: no se ha recibido ningún producto.")
        print("   - Posible captcha, bloqueo temporal o cambio en la web de Wallapop.")
        print("   - Revisa logs/app.log para más detalles.")
        return False

    # Buscamos al menos un producto 'sano'
    validos = [
        p for p in productos
        if p.get("precio") is not None and p.get("url")
    ]
    n_validos = len(validos)

    print(f"SELF-TEST: productos con precio y URL válidos = {n_validos}")

    if n_validos == 0:
        print("❌ SELF-TEST: ninguno de los productos tiene precio y URL válidos.")
        print("   - Puede indicar un cambio en la estructura de la API o un fallo de parseo.")
        print("   - Revisa logs/app.log para ver la respuesta cruda.")
        return False

    # Si hay al menos 1 válido, consideramos que el scraper está funcional
    ej = validos[0]
    print("✅ SELF-TEST: scraper funcional.")
    print("   Ejemplo de producto válido:")
    print(f"   - ID: {ej.get('id')}")
    print(f"   - Título: {ej.get('titulo')}")
    print(f"   - Precio: {ej.get('precio')} €")
    print(f"   - URL: {ej.get('url')}")

    log.info("[SELFTEST] Test superado correctamente.")
    return True


def main(argv: Optional[list] = None) -> int:
    """
    Uso:
      python scripts/self_test_scraper.py
      python scripts/self_test_scraper.py "ps5"
    """
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) >= 1:
        keyword = " ".join(argv)
    else:
        keyword = "iphone 12"

    ok = run_self_test(keyword=keyword, limit=30)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
