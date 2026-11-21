# SPDX-FileCopyrightText: 2026 P-Joss-P
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Remplissage semi-automatique du panier drive à partir de la liste Tandoor.

Commandes :
  python main.py login   --site carrefour   # connexion manuelle (une fois)
  python main.py inspect --site carrefour   # ouvre l'inspecteur pour trouver les sélecteurs
  python main.py list                       # affiche la liste Tandoor
  python main.py run     --site carrefour [--dry-run]
  python main.py mappings --site carrefour  # affiche les correspondances mémorisées

Le script s'arrête avant le paiement : tu vérifies et tu valides toi-même.
"""
import argparse
import sys

from playwright.sync_api import sync_playwright

import db
import tandoor
from config import PROFILES_DIR
from normalize import normalize_name
from sites import SITES, SelectorsNotConfigured

import os

BROWSER = os.environ.get("DRIVE_BROWSER", "firefox")  # "firefox" ou "chromium"

def open_context(p, site_name: str):
    profile = PROFILES_DIR / site_name
    profile.mkdir(parents=True, exist_ok=True)
    ctx = getattr(p, BROWSER).launch_persistent_context(
        str(profile),
        headless=False,
        viewport={"width": 1280, "height": 900},
        locale="fr-FR",
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, page

def ask_choice(item, candidates):
    """Renvoie ('choice', candidate) | ('skip', None) | ('ignore', None) | ('retry', texte)."""
    print(f"\n« {item.name} » : pas encore mémorisé")
    for i, c in enumerate(candidates, 1):
        print(f"  {i}. {c.name}  [{c.price}]")
    print("  s = passer cette fois   i = ignorer définitivement   ou tape un autre mot pour chercher")
    while True:
        answer = input("> ").strip()
        if answer.lower() == "s":
            return "skip", None
        if answer.lower() == "i":
            return "ignore", None
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return "choice", candidates[int(answer) - 1]
        if answer:
            return "retry", answer


def ask_qty() -> int:
    raw = input("Nombre d'unités à acheter chaque semaine [1] > ").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else 1


def cmd_run(site_name: str, dry_run: bool):
    items = tandoor.fetch_items()
    print(f"{len(items)} article(s) dans la liste Tandoor.")
    conn = db.connect()
    added, to_check, failed, ignored = [], [], [], []

    with sync_playwright() as p:
        ctx, page = open_context(p, site_name)
        site = SITES[site_name](page)
        site.open_home()
        input("Vérifie que tu es connecté et que le bon magasin/créneau est sélectionné, "
              "puis appuie sur Entrée... ")

        for item in items:
            key = normalize_name(item.name)
            m = db.get_mapping(conn, key, site_name)

            if m and m.ignored:
                ignored.append(item.name)
                continue

            if m is None:
                query = item.name
                while True:
                    candidates = site.search(query)
                    if not candidates:
                        print(f"\nAucun résultat pour « {query} ».")
                        answer = input("Autre mot à chercher (ou Entrée pour passer) > ").strip()
                        if not answer:
                            to_check.append(item.name)
                            break
                        query = answer
                        continue
                    kind, value = ask_choice(item, candidates)
                    if kind == "retry":
                        query = value
                        continue
                    if kind == "skip":
                        to_check.append(item.name)
                    elif kind == "ignore":
                        db.save_mapping(conn, key, site_name, None, None, ignored=True)
                        ignored.append(item.name)
                    else:
                        qty = ask_qty()
                        db.save_mapping(conn, key, site_name, value.name, value.url, qty)
                        m = db.get_mapping(conn, key, site_name)
                    break
                if m is None:
                    continue

            if dry_run:
                print(f"[dry-run] ajouterait {m.qty_default} x {m.product_name}")
                added.append(item.name)
                continue

            if site.add_to_cart(m.product_url, m.qty_default):
                print(f"OK  {m.qty_default} x {m.product_name}")
                added.append(item.name)
            else:
                print(f"ÉCHEC  {m.product_name} (indisponible ?)")
                failed.append(item.name)

        print("\n=== Récapitulatif ===")
        print(f"Ajoutés    ({len(added)}) : {', '.join(added) or '-'}")
        print(f"À voir     ({len(to_check)}) : {', '.join(to_check) or '-'}")
        print(f"Échecs     ({len(failed)}) : {', '.join(failed) or '-'}")
        print(f"Ignorés    ({len(ignored)}) : {', '.join(ignored) or '-'}")
        input("\nVérifie ton panier dans le navigateur, puis appuie sur Entrée pour fermer... ")
        ctx.close()


def cmd_login(site_name: str):
    with sync_playwright() as p:
        ctx, page = open_context(p, site_name)
        SITES[site_name](page).open_home()
        input("Connecte-toi, choisis ton magasin drive, puis appuie sur Entrée pour fermer... ")
        ctx.close()


def cmd_inspect(site_name: str):
    with sync_playwright() as p:
        ctx, page = open_context(p, site_name)
        SITES[site_name](page).open_home()
        print("Inspecteur Playwright : utilise « Pick locator » pour repérer les sélecteurs.")
        page.pause()
        ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=["run", "login", "inspect", "list", "mappings"])
    ap.add_argument("--site", choices=list(SITES), default="carrefour")
    ap.add_argument("--dry-run", action="store_true", help="n'ajoute rien au panier")
    args = ap.parse_args()

    try:
        if args.command == "list":
            for it in tandoor.fetch_items():
                print(f"- {it.name}  ({it.amount:g} {it.unit or ''})".rstrip())
        elif args.command == "mappings":
            for row in db.list_mappings(db.connect(), args.site):
                tag = "IGNORÉ" if row["ignored"] else f"{row['qty_default']} x {row['product_name']}"
                print(f"{row['article_key']:30} {tag}")
        elif args.command == "login":
            cmd_login(args.site)
        elif args.command == "inspect":
            cmd_inspect(args.site)
        else:
            cmd_run(args.site, args.dry_run)
    except SelectorsNotConfigured as e:
        sys.exit(f"\n{e}\nRemplis les sélecteurs dans sites.py (voir README.md).")


if __name__ == "__main__":
    main()
