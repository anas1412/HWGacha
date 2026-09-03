"""Start the bot inside a local virtual environment (.venv). Nothing is installed globally.

    python3 start.py
"""
import os
import subprocess
import sys
import venv

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HERE, ".venv")
PY = os.path.join(VENV, "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
REQS = os.path.join(HERE, "requirements.txt")
STAMP = os.path.join(VENV, ".requirements.stamp")


def ensure_venv():
    if not os.path.exists(PY):
        print("creating .venv ...")
        venv.create(VENV, with_pip=True)
    # reinstall only when requirements.txt changed since last time
    if not os.path.exists(STAMP) or os.path.getmtime(STAMP) < os.path.getmtime(REQS):
        print("installing requirements ...")
        subprocess.check_call([PY, "-m", "pip", "install", "-q", "-r", REQS])
        open(STAMP, "w").close()


if __name__ == "__main__":
    ensure_venv()
    os.chdir(HERE)
    sys.exit(subprocess.call([PY, os.path.join(HERE, "main.py")]))
