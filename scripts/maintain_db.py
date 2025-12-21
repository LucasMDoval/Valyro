from pathlib import Path
import sys
import sqlite3

# Aseguramos raíz del proyecto en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.db import DB_PATH, get_connection
from utils.logger import get_logger

log = get_logger("maintain")


def create_extra_indexes(conn: sqlite3.Connection):
    """
    Crea (si no existen) los índices importantes para rendimiento
    y análisis histórico.
    """
    log.info("Creando índices adicionales si no existen...")

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_unique_listing
        ON products(platform, external_id);
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_listing_history
        ON products(external_id, scraped_at);
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_scraped_keyword
        ON products(keyword, scraped_at);
    """)

    conn.commit()
    log.info("Índices creados / verificados correctamente.")


def delete_exact_duplicates(conn: sqlite3.Connection) -> int:
    """
    Elimina duplicados EXACTOS: misma platform + external_id + scraped_at.

    Mantiene el registro con menor rowid (primero insertado) y elimina el resto.
    """
    log.info("Eliminando duplicados exactos (platform, external_id, scraped_at)...")

    sql = """
        DELETE FROM products
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM products
            GROUP BY platform, external_id, scraped_at
        );
    """
    cur = conn.cursor()
    cur.execute(sql)
    deleted = cur.rowcount if cur.rowcount is not None else 0
    conn.commit()

    log.info(f"Duplicados exactos eliminados: {deleted}")
    return int(deleted)


def vacuum_db(conn: sqlite3.Connection):
    """
    Compacta la base de datos para recuperar espacio.
    """
    log.info("Ejecutando VACUUM para compactar la base de datos...")
    conn.execute("VACUUM;")
    log.info("VACUUM completado.")


def main() -> int:
    if not DB_PATH.is_file():
        print("No existe la base de datos. Nada que optimizar.")
        return 0

    print("=== Mantenimiento de la base de datos ===")
    print(f"BD: {DB_PATH}")

    conn = get_connection()

    try:
        create_extra_indexes(conn)
        deleted = delete_exact_duplicates(conn)
        print(f"- Duplicados exactos eliminados: {deleted}")
        vacuum_db(conn)
    finally:
        conn.close()

    print("✔ Mantenimiento completado.")
    print("Revisa logs/app.log para detalles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
