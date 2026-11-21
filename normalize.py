# SPDX-FileCopyrightText: 2026 P-Joss-P
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Normalisation des noms d'articles pour que « Tomates », « tomate » et « Tomate » 
retombent sur la même clé."""
import re
import unicodedata


def normalize_name(name: str) -> str:
    # les ligatures n'ont pas d'équivalent ASCII par décomposition : on les traite avant
    name = name.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("Æ", "Ae")
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = []
    for w in s.split():
        # pluriel simple : on retire le « s » final des mots de plus de 3 lettres
        if len(w) > 3 and w.endswith("s"):
            w = w[:-1]
        words.append(w)
    return " ".join(words)
