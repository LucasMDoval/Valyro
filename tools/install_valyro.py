import subprocess
import sys
import os
from pathlib import Path

def main():
    base = Path(__file__).resolve().parent

    print("\n=== Configurando Valyro por primera vez ===\n")

    # 1) Crear rutas necesarias
    for folder in ["data", "plots", "reports"]:
        p = base / folder
        p.mkdir(exist_ok=True)
        print(f"[OK] Carpeta lista: {p}")

    # 2) Instalar browsers de Playwright dentro del build
    print("\nInstalando navegador de Playwright (Chromium)...\n")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True
        )
        print("[OK] Chromium instalado correctamente.")
    except Exception as e:
        print("[ERROR] Fallo instalando Playwright:", e)

    # 3) Marcar instalación completada
    (base / "valyro_installed.flag").write_text("1")

    print("\nValyro está listo para usarse.\n")

if __name__ == "__main__":
    main()
