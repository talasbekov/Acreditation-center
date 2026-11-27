"""manage.py для сквозного сценария: настройки scripts/stage_e/e2e_settings.py.

POPPLER_BIN (необязательно) — каталог pdftoppm для конвертации PDF-сканов.
"""
import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
if os.environ.get("POPPLER_BIN"):
    os.environ["PATH"] = os.environ["POPPLER_BIN"] + os.pathsep + os.environ.get("PATH", "")
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(HERE))
os.environ["DJANGO_SETTINGS_MODULE"] = "e2e_settings"
sys.dont_write_bytecode = True
sys.argv = ["manage.py", *sys.argv[1:]]
runpy.run_path(str(PROJECT / "manage.py"), run_name="__main__")
