import os
from pathlib import Path
import textwrap


def get_default_project_dir() -> Path:
    """
    Devuelve la carpeta raíz del proyecto asumiendo:
    scripts/setup_autostart.py -> raíz = .. (padre de scripts)
    """
    return Path(__file__).resolve().parents[1]


def get_startup_folder() -> Path:
    """
    Carpeta de inicio de Windows para el usuario actual.
    """
    appdata = os.getenv("APPDATA")
    if not appdata:
        raise RuntimeError("No se ha podido obtener APPDATA. Solo soportado en Windows.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def create_bat(project_dir: Path) -> Path:
    """
    Crea el .bat en la carpeta del proyecto para lanzar daily_scrape.
    Soporta venv y .venv automáticamente.
    """
    bat_path = project_dir / "ejecutar_scrape_al_iniciar.bat"

    contenido = textwrap.dedent(f"""\
        @echo off
        REM Ir a la carpeta del proyecto
        cd /d "{project_dir}"

        REM 1) Si existe un entorno virtual llamado 'venv', usarlo
        if exist "venv\\Scripts\\python.exe" (
            echo Usando venv\\Scripts\\python.exe
            "venv\\Scripts\\python.exe" -m scripts.daily_scrape
            exit /b
        )

        REM 2) Si existe un entorno virtual llamado '.venv', usarlo
        if exist ".venv\\Scripts\\python.exe" (
            echo Usando .venv\\Scripts\\python.exe
            ".venv\\Scripts\\python.exe" -m scripts.daily_scrape
            exit /b
        )

        REM 3) Si no hay venv, usar 'python' del sistema
        echo No se ha encontrado venv, usando 'python' del sistema
        python -m scripts.daily_scrape

        exit
    """)

    bat_path.write_text(contenido, encoding="utf-8")
    return bat_path


def create_vbs(bat_path: Path, startup_folder: Path) -> Path:
    """
    Crea el .vbs en la carpeta de Inicio de Windows para ejecutar el .bat oculto.
    """
    vbs_path = startup_folder / "market_analyzer_autoscrape.vbs"

    # Ojo con las comillas triples para la ruta
    contenido = textwrap.dedent(f"""\
        Set WshShell = CreateObject("WScript.Shell")
        WshShell.Run """ + '"""' + f"{bat_path}" + '"""' + ", 0, False\n"
    )

    vbs_path.write_text(contenido, encoding="utf-8")
    return vbs_path

def setup_keywords_file(project_dir: Path):
    """
    Pregunta al usuario las keywords para el daily scrape y las guarda
    en data/daily_keywords.txt (una por línea).
    """
    data_dir = project_dir / "data"
    data_dir.mkdir(exist_ok=True)

    keywords_file = data_dir / "daily_keywords.txt"

    print("\n--- Configuración de keywords para el daily scrape ---")
    print("Puedes definir las keywords que quieres que se scrapeen automáticamente.")
    print("Escribe una por línea. Deja la línea vacía y pulsa Enter para terminar.\n")

    kws = []
    while True:
        linea = input("Keyword (o Enter para terminar): ").strip()
        if not linea:
            break
        kws.append(linea)

    if not kws:
        print("No se han introducido keywords. Se usará la lista por defecto en scripts/daily_scrape.py.")
        return

    contenido = "\n".join(kws) + "\n"
    keywords_file.write_text(contenido, encoding="utf-8")
    print(f"\n✅ Keywords guardadas en:\n  {keywords_file}")


def main():
    print("=== Configuración de auto-scrape al iniciar Windows ===\n")

    default_dir = get_default_project_dir()
    print(f"Ruta detectada del proyecto por defecto:\n  {default_dir}\n")
    resp = input("¿Quieres usar ESTA ruta como carpeta del proyecto? [S/n]: ").strip().lower()

    if resp in ("n", "no"):
        ruta = input("Introduce la ruta completa de la carpeta del proyecto (donde está 'scripts'): ").strip()
        project_dir = Path(ruta).expanduser().resolve()
    else:
        project_dir = default_dir

    if not project_dir.is_dir():
        print(f"\n❌ La ruta no existe o no es una carpeta: {project_dir}")
        return

    scripts_dir = project_dir / "scripts"
    if not scripts_dir.is_dir():
        print(f"\n❌ No se ha encontrado la carpeta 'scripts' dentro de: {project_dir}")
        print("   Asegúrate de indicar la carpeta raíz del proyecto (donde están 'scripts', 'analytics', etc.).")
        return

    print(f"\nUsando carpeta de proyecto: {project_dir}")

    # Crear .bat
    bat_path = create_bat(project_dir)
    print(f"\n✅ Archivo .bat creado/actualizado en:\n  {bat_path}")

    # Carpeta de inicio
    try:
        startup_folder = get_startup_folder()
    except RuntimeError as e:
        print(f"\n❌ Error obteniendo carpeta de inicio de Windows: {e}")
        return

    if not startup_folder.is_dir():
        print(f"\n❌ La carpeta de inicio no existe: {startup_folder}")
        return

        # Crear .vbs en Inicio
    vbs_path = create_vbs(bat_path, startup_folder)
    print(f"\n✅ Archivo .vbs creado/actualizado en la carpeta de inicio de Windows:\n  {vbs_path}")

    # Ofrecer configurar keywords
    resp_kw = input("\n¿Quieres configurar ahora las keywords para el daily scrape? [S/n]: ").strip().lower()
    if resp_kw in ("", "s", "si", "sí"):
        setup_keywords_file(project_dir)
    else:
        print("\n(No se ha configurado fichero de keywords; se usarán las keywords por defecto.)")

    print("\nA partir del próximo reinicio/inicio de sesión en Windows:")
    print("  → Se ejecutará automáticamente 'python -m scripts.daily_scrape'")
    print("  → Usando venv/.venv si existe, o 'python' global si no.")
    print("  → Todo en segundo plano, SIN mostrar consola.\n")



if __name__ == "__main__":
    main()
