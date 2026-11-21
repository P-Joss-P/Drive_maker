# SPDX-FileCopyrightText: 2026 P-Joss-P
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Configuration : lue depuis les variables d'environnement ou un fichier .env."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv est optionnel
    pass

BASE_DIR = Path(__file__).resolve().parent

TANDOOR_URL = os.environ.get("TANDOOR_URL", "http://localhost:8080").rstrip("/")
TANDOOR_TOKEN = os.environ.get("TANDOOR_TOKEN", "")

DB_PATH = Path(os.environ.get("DRIVE_DB_PATH", BASE_DIR / "drive.db"))

# Un profil de navigateur par enseigne : ta session (connexion, magasin choisi)
# y est conservée entre deux exécutions.
PROFILES_DIR = Path(os.environ.get("DRIVE_PROFILES_DIR", BASE_DIR / "profiles"))

# Délais "humains" entre deux actions, en secondes (min, max).
PAUSE_RANGE = (0.8, 2.2)

# URL de ton drive Leclerc (propre à ton magasin), à renseigner dans .env
LECLERC_STORE_URL = os.environ.get("LECLERC_STORE_URL", "")
