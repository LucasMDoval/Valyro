from pathlib import Path
import sys

# Aseguramos que la raíz del proyecto está en sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.app import main


if __name__ == "__main__":
    # Lanza la app Flask (web/app.py)
    main()
