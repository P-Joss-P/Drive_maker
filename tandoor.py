# SPDX-FileCopyrightText: 2026 P-Joss-P
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lecture de la liste de courses Tandoor via son API REST.

Les noms de champs ci-dessous correspondent à ce que j'ai vu de l'API
(/api/shopping-list-entry/ avec food, unit, amount, checked). Vérifie-les sur
ton instance : la doc interactive est sur <ton-tandoor>/docs/api/.
"""
from dataclasses import dataclass, field

import requests

from config import TANDOOR_TOKEN, TANDOOR_URL


@dataclass
class Item:
    name: str
    amount: float = 0.0
    unit: str | None = None
    entry_ids: list[int] = field(default_factory=list)


def _get_all(url: str, headers: dict, params: dict | None = None) -> list[dict]:
    results: list[dict] = []
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):  # réponse non paginée
            return results + data
        results += data.get("results", [])
        url = data.get("next")
        params = None  # l'URL « next » contient déjà les paramètres
    return results


def fetch_items() -> list[Item]:
    if not TANDOOR_TOKEN:
        raise RuntimeError("TANDOOR_TOKEN manquant (voir .env.example)")
    headers = {"Authorization": f"Bearer {TANDOOR_TOKEN}"}
    entries = _get_all(
        f"{TANDOOR_URL}/api/shopping-list-entry/", headers, {"page_size": 200}
    )

    merged: dict[tuple[str, str | None], Item] = {}
    for e in entries:
        if e.get("checked"):
            continue
        food = e.get("food") or {}
        name = food.get("name") if isinstance(food, dict) else str(food)
        if not name:
            continue
        unit = e.get("unit")
        unit_name = unit.get("name") if isinstance(unit, dict) else None
        key = (name.lower(), unit_name)
        item = merged.setdefault(key, Item(name=name, unit=unit_name))
        item.amount += float(e.get("amount") or 0)
        item.entry_ids.append(e["id"])
    return list(merged.values())
