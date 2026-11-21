# SPDX-FileCopyrightText: 2026 P-Joss-P
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Serveur local pour le script utilisateur Firefox.

Il expose, sur 127.0.0.1 uniquement :
  GET  /items?site=carrefour   liste Tandoor + statut de chaque article
                               (known | unknown | ignored) d'après la base
  POST /mapping                mémorise un choix de produit (ou « ignorer »)

Chaque requête doit porter l'en-tête X-Token (variable DRIVE_LOCAL_TOKEN du .env),
pour qu'une page web quelconque ne puisse pas lire ta liste ni écrire dans ta base.

Lancement : py server.py
"""
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import config  # noqa: F401  (charge le .env)
import db
import tandoor
from normalize import normalize_name

HOST, PORT = "127.0.0.1", 8765
SITES = {"carrefour", "leclerc"}
TOKEN = os.environ.get("DRIVE_LOCAL_TOKEN", "")
MAX_BODY = 10_000


class Handler(BaseHTTPRequestHandler):
    server_version = "DriveLocal/0.1"

    def log_message(self, fmt, *args):  # pas de bruit dans le terminal
        pass

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        # Le contrôle de Host limite les attaques par "DNS rebinding".
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return False
        sent = (self.headers.get("X-Token") or "").encode()
        return bool(TOKEN) and hmac.compare_digest(sent, TOKEN.encode())

    def do_GET(self):
        if not self._authorized():
            return self._send(403, {"error": "non autorisé"})
        url = urlparse(self.path)
        if url.path == "/health":
            return self._send(200, {"ok": True})
        if url.path != "/items":
            return self._send(404, {"error": "inconnu"})

        site = (parse_qs(url.query).get("site") or [""])[0]
        if site not in SITES:
            return self._send(400, {"error": "site invalide"})
        try:
            raw_items = tandoor.fetch_items()
        except Exception as e:  # réseau, token, format...
            return self._send(502, {"error": f"Tandoor : {e}"})

        conn = db.connect()
        seen, items = set(), []
        for it in raw_items:
            key = normalize_name(it.name)
            if not key or key in seen:  # un même article = une seule ligne
                continue
            seen.add(key)
            m = db.get_mapping(conn, key, site)
            if m and m.ignored:
                status = "ignored"
            elif m and m.product_url:
                status = "known"
            else:
                status = "unknown"
            items.append({
                "name": it.name,
                "status": status,
                "product_name": m.product_name if m else None,
                "product_url": m.product_url if m else None,
                "qty": m.qty_default if m else 1,
            })
        conn.close()
        return self._send(200, {"items": items})

    def do_POST(self):
        if not self._authorized():
            return self._send(403, {"error": "non autorisé"})
        if urlparse(self.path).path != "/mapping":
            return self._send(404, {"error": "inconnu"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                raise ValueError("taille")
            data = json.loads(self.rfile.read(length))
            site = data["site"]
            name = data["name"]
            ignored = bool(data.get("ignored", False))
            qty = int(data.get("qty", 1))
            product_name = data.get("product_name")
            product_url = data.get("product_url")
            if site not in SITES or not isinstance(name, str) or not name.strip():
                raise ValueError("site ou nom")
            if not 1 <= qty <= 99:
                raise ValueError("quantité")
            if not ignored and not (isinstance(product_url, str) and product_url.startswith("https://")):
                raise ValueError("product_url")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return self._send(400, {"error": "requête invalide"})

        conn = db.connect()
        db.save_mapping(conn, normalize_name(name), site, product_name, product_url, qty, ignored)
        conn.close()
        return self._send(200, {"ok": True})


def make_server(port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((HOST, port), Handler)


def main():
    if not TOKEN:
        sys.exit(
            "DRIVE_LOCAL_TOKEN manquant dans .env. Génère-en un avec :\n"
            '  python -c "import secrets; print(secrets.token_urlsafe(24))"'
        )
    srv = make_server()
    print(f"Serveur local sur http://{HOST}:{PORT} (Ctrl+C pour arrêter)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
