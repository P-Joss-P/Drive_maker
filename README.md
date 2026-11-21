# Drive auto : liste Tandoor → panier Carrefour

Le projet lit ta liste de courses Tandoor et remplit le panier de ton drive à ta place, **dans ton
vrai Firefox**, avec ta session et ton captcha passés normalement. Il mémorise le produit que tu
choisis pour chaque article : après quelques semaines, presque tout se fait tout seul.
Il s'arrête avant le paiement, que tu fais toi-même.

```
Tandoor ──► server.py (127.0.0.1:8765) ◄──► drive.user.js (dans Firefox, sur carrefour.fr)
              base drive.db (SQLite)          panneau + clics sur les cartes produit
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `server.py` | Serveur local : lit la liste Tandoor, dit pour chaque article s'il est connu, inconnu ou ignoré, et enregistre tes choix |
| `drive.user.js` | Script utilisateur (Violentmonkey / Tampermonkey) : panneau sur carrefour.fr, recherche, choix, ajout au panier |
| `tandoor.py` | Lecture de la liste de courses via l'API Tandoor |
| `db.py` | Base SQLite `drive.db` : correspondance article → produit, par enseigne |
| `normalize.py` | Normalisation des noms (« Œufs », « oeuf », « Oeufs » = même article) |
| `config.py` | Lecture du `.env` |
| `main.py`, `sites.py` | Première version avec Playwright, gardée pour référence (voir la fin) |
| `FIREFOX.md` | Guide détaillé pour trouver les sélecteurs CSS |

## Prérequis

- Python 3.10 ou plus
- Une instance Tandoor et un token d'API (Tandoor → Paramètres → API), avec les droits de lecture
- Firefox avec l'extension **Violentmonkey** (ou Tampermonkey)

## Installation (une seule fois)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Si PowerShell refuse d'activer le `.venv` (« l'exécution de scripts est désactivée ») :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Remplis ensuite `.env` :

```
TANDOOR_URL=http://ton-tandoor:8085
TANDOOR_TOKEN=le_token_tandoor
DRIVE_LOCAL_TOKEN=un_token_au_hasard
```

`DRIVE_LOCAL_TOKEN` protège le serveur local : invente-le avec
`python -c "import secrets; print(secrets.token_urlsafe(24))"`.
Optionnel : `DRIVE_DB_PATH` pour changer l'emplacement de `drive.db`.

Vérifie que Tandoor répond :

```powershell
python -c "import config, tandoor; print(len(tandoor.fetch_items()), 'article(s)')"
```

## Installer le script dans Firefox (une seule fois)

1. Violentmonkey → « Nouveau script », colle tout le contenu de `drive.user.js`, enregistre.
2. En haut du script, remplace `COLLE_ICI_LE_TOKEN` par la valeur de `DRIVE_LOCAL_TOKEN`.
   Ne mets pas ce token dans la copie du dépôt : garde-le seulement dans Violentmonkey.
3. Vérifie `SEARCH_URL` et les sélecteurs de l'objet `SEL`. Ceux de Carrefour sont déjà renseignés ;
   s'ils cessent de fonctionner (le site a changé), refais-les en suivant `FIREFOX.md`.
   Syntaxe : une classe s'écrit `.ma-classe`, balise + classe `article.ma-classe`, un espace
   veut dire « à l'intérieur de ».

## Utilisation hebdomadaire

1. Prépare ta liste dans Tandoor.
2. Lance le serveur et laisse la fenêtre ouverte :
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python server.py
   ```
3. Dans Firefox, va sur carrefour.fr, connecte-toi et choisis ton magasin drive.
4. Clique sur **« Remplir le panier depuis Tandoor »** (panneau en bas à droite). Ne ferme pas
   l'onglet pendant le passage ; **« Arrêter »** interrompt proprement.
5. Pour chaque article :
   - **déjà mémorisé** : le script cherche le produit, retrouve sa carte dans les résultats et
     clique sur « Acheter » puis « + » selon la quantité ;
   - **inconnu** : le panneau propose jusqu'à 5 produits. Choisis, règle la quantité : le choix est
     mémorisé et l'ajout se fait tout de suite. Tu peux aussi relancer une recherche, passer
     (« Passer cette fois ») ou ne plus jamais traiter l'article (« Ignorer toujours »).
6. Lis le récapitulatif, vérifie le panier sur le site, puis choisis ton créneau et paie.

### Sens du récapitulatif

| Message | Signification |
|---|---|
| `ajouté N x …` | ajouté ; N est la quantité réellement affichée par le site |
| `déjà dans le panier (N)` | rien n'est ajouté, pour éviter les doublons |
| `indisponible ? (pas de bouton d'ajout…)` | la carte du produit n'a pas de bouton « Acheter » |
| `échec (produit introuvable…)` | ni le nom exact ni le nom Tandoor ne l'ont fait remonter |
| `échec (ajout non confirmé…)` | le clic n'a pas eu d'effet visible sur la carte |
| `à voir` | tu as passé l'article, à traiter à la main |
| `ignoré` | article marqué « ignorer toujours » |

## Données

`drive.db` contient la table `mapping` : une ligne par article et par enseigne, avec le produit
choisi, son lien, la quantité habituelle et l'indicateur « ignoré ». Le nom d'article est stocké sous
forme normalisée (minuscules, sans accents, sans « s » final). Pour la lire :

```powershell
python -c "import db; [print(dict(r)) for r in db.list_mappings(db.connect(), 'carrefour')]"
```

Pour changer le produit mémorisé d'un article, ou le sortir de la liste « ignoré », supprime sa ligne
avec un éditeur SQLite (par exemple DB Browser for SQLite) : le script te reposera la question.

## Dépannage

| Symptôme | Piste |
|---|---|
| `Tandoor : 403` dans le panneau | Token absent ou mauvais : `python -c "import config; print(len(config.TANDOOR_TOKEN))"` doit afficher plus de 0 (le fichier doit s'appeler `.env`, sans guillemets). Teste aussi le token avec `curl.exe -i -H "Authorization: Bearer TOKEN" "<TANDOOR_URL>/api/shopping-list-entry/?page_size=1"` |
| `Serveur local injoignable` | `python server.py` n'est pas lancé, ou `TOKEN` du script ≠ `DRIVE_LOCAL_TOKEN` |
| Le serveur refuse de démarrer | `DRIVE_LOCAL_TOKEN` manquant dans `.env` |
| `Aucun résultat (0 bloc(s)…)` | Sélecteur `result_card` faux (point oublié ?) ou structure du site changée : compare avec `document.querySelectorAll(...)` dans la console |
| Un article n'est jamais trouvé | Le produit est peut-être retiré du magasin : choisis-en un autre (supprime sa ligne dans `drive.db`) |
| `ModuleNotFoundError` | Le `.venv` n'est pas activé : le préfixe `(.venv)` doit apparaître dans le terminal |
| Captcha qui échoue | N'utilise pas un navigateur piloté : le script tourne dans ton Firefox normal, connecte-toi à la main |

## Versionnement (Git)

À **ne pas** commiter : `.env`, `drive.db`, `profiles/`, `chrome-profile/`, `.venv/`, `__pycache__/`
(le `.gitignore` fourni les exclut). Les dossiers de profil de navigateur contiennent les cookies de
ta session Carrefour. Si l'un d'eux a déjà été commité, retire-le du suivi sans le supprimer :
`git rm -r --cached profiles`. Si un secret a été poussé quelque part, change le mot de passe
concerné et recrée le token.

## Limites connues

- Testé sur Carrefour uniquement, et sur une maquette pour les cas rares (indisponible, déjà dans le
  panier) : à confirmer en réel quand ils se présentent.
- Le script cherche chaque produit par son nom ; un produit qui n'apparaît pas dans les premiers
  résultats est considéré comme introuvable.
- Les quantités Tandoor (200 g, 3 cuillères…) ne sont pas des nombres de paquets : la quantité achetée
  est celle que tu fixes la première fois.
- Le site peut changer de structure : les sélecteurs sont alors à refaire.
- Les conditions d'utilisation des enseignes restreignent en général l'automatisation. Usage
  personnel, une passe par semaine, sur ton propre compte.

## Pour Leclerc

Dupliquer `drive.user.js` : adapter `// @match` à l'adresse de ton drive, `SITE = "leclerc"`,
`SEARCH_URL` et les sélecteurs.

## Version Playwright (historique)

`main.py` et `sites.py` pilotaient un navigateur Playwright. La connexion à Carrefour y échoue
(captcha refusé sur un navigateur piloté, aussi bien Chromium que Firefox), donc cette voie n'est
plus utilisée. Le code reste dans le dépôt pour référence ; son profil `profiles/` peut être supprimé.

## Pistes pour la suite

Produits indisponibles (remplacement mémorisé), Leclerc, notes manuscrites (Gemma via Ollama),
comparaison de prix entre enseignes, recommandations.

## Licence

Ce projet est distribué sous licence **GNU AGPL-3.0 ou ultérieure** (`AGPL-3.0-or-later`), voir le
fichier [LICENSE](LICENSE). Il peut être utilisé, étudié, modifié et redistribué librement. Toute version
modifiée distribuée, ou proposée comme service accessible par le réseau, doit rester sous la même licence
et fournir son code source.
