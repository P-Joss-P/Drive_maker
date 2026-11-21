# SPDX-FileCopyrightText: 2026 P-Joss-P
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Adaptateurs par enseigne.

Toute la logique de navigation est dans DriveSite ; chaque enseigne ne fournit
que ses URL et ses sélecteurs CSS. Les valeurs "TODO" sont à remplir à partir
de ton propre drive : lance `python main.py inspect --site carrefour`, ouvre
l'inspecteur Playwright, et repère les sélecteurs (voir README.md).
"""
import random
import time
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin

from config import LECLERC_STORE_URL, PAUSE_RANGE


class SelectorsNotConfigured(RuntimeError):
    pass


@dataclass
class Candidate:
    name: str
    price: str
    url: str


class DriveSite:
    name = ""
    home_url = ""
    search_url = ""  # doit contenir {q}

    # Sélecteurs CSS. "TODO" = pas encore renseigné.
    SEL = {
        "cookie_accept": "TODO",  # bouton d'acceptation des cookies (optionnel)
        "result_card": "TODO",    # un bloc produit dans la page de résultats
        "result_name": "TODO",    # nom du produit, dans le bloc
        "result_price": "TODO",   # prix, dans le bloc
        "result_link": "TODO",    # lien <a> vers la fiche produit, dans le bloc
        "add_button": "TODO",     # bouton « ajouter au panier » (fiche produit)
        "plus_button": "TODO",    # bouton « + » de quantité (fiche produit)
    }

    def __init__(self, page):
        self.page = page

    # --- utilitaires -------------------------------------------------------
    def pause(self):
        time.sleep(random.uniform(*PAUSE_RANGE))

    def _sel(self, key: str, optional: bool = False) -> str | None:
        value = self.SEL[key]
        if value.startswith("TODO"):
            if optional:
                return None
            raise SelectorsNotConfigured(
                f"Sélecteur '{key}' non renseigné pour {self.name} (voir sites.py)"
            )
        return value

    def dismiss_cookies(self):
        sel = self._sel("cookie_accept", optional=True)
        if not sel:
            return
        try:
            self.page.locator(sel).first.click(timeout=3000)
            self.pause()
        except Exception:
            pass  # pas de bannière, tant mieux

    # --- actions -----------------------------------------------------------
    def open_home(self):
        self.page.goto(self.home_url)

    def search(self, query: str, limit: int = 5) -> list[Candidate]:
        if not self.search_url:
            raise SelectorsNotConfigured(f"search_url non renseignée pour {self.name}")
        self.page.goto(self.search_url.format(q=quote_plus(query)))
        self.dismiss_cookies()
        card_sel = self._sel("result_card")
        try:
            self.page.wait_for_selector(card_sel, timeout=10000)
        except Exception:
            return []
        out: list[Candidate] = []
        for card in self.page.locator(card_sel).all()[:limit]:
            try:
                name = card.locator(self._sel("result_name")).first.inner_text().strip()
                price = card.locator(self._sel("result_price")).first.inner_text().strip()
                href = card.locator(self._sel("result_link")).first.get_attribute("href")
            except Exception:
                continue
            if href:
                out.append(Candidate(name, price.replace("\n", " "), urljoin(self.page.url, href)))
        return out

    def add_to_cart(self, product_url: str, qty: int = 1) -> bool:
        """Ajoute `qty` unités du produit. Renvoie False en cas d'échec
        (produit indisponible, bouton introuvable...)."""
        self.page.goto(product_url)
        self.dismiss_cookies()
        self.pause()
        try:
            self.page.locator(self._sel("add_button")).first.click(timeout=8000)
            for _ in range(max(0, qty - 1)):
                self.pause()
                self.page.locator(self._sel("plus_button")).first.click(timeout=5000)
            self.pause()
            return True
        except SelectorsNotConfigured:
            raise
        except Exception:
            return False


class Carrefour(DriveSite):
    name = "carrefour"
    home_url = "https://www.carrefour.fr/"
    # Format d'URL de recherche à confirmer sur ton site (magasin drive sélectionné).
    search_url = "https://www.carrefour.fr/s?q={q}"


class Leclerc(DriveSite):
    name = "leclerc"
    # Chaque magasin Leclerc a son propre sous-domaine/chemin : mets l'URL de TON
    # drive dans LECLERC_STORE_URL (.env).
    home_url = LECLERC_STORE_URL
    # À remplir après avoir fait une recherche à la main et copié l'URL obtenue,
    # en remplaçant le mot cherché par {q}.
    search_url = ""


SITES = {"carrefour": Carrefour, "leclerc": Leclerc}
