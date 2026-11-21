# Version Firefox : script utilisateur + serveur local

Ici, rien n'est piloté depuis l'extérieur : le code tourne **dans ton Firefox habituel**, avec ta
session, tes cookies et ton captcha passé normalement. Le script ne fait que cliquer sur
« ajouter au panier » à ta place. Il s'arrête avant le paiement.

```
Tandoor ──► server.py (127.0.0.1) ◄──► drive.user.js (dans Firefox, sur carrefour.fr)
              base drive.db                panneau + clics sur le site
```

## Installation

1. Installe **Violentmonkey** (ou Tampermonkey) dans Firefox.
2. Dans `.env`, ajoute un token (le serveur refuse de démarrer sans) :
   ```
   DRIVE_LOCAL_TOKEN=<résultat de la commande ci-dessous>
   ```
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(24))"
   ```
3. Lance le serveur et laisse-le ouvert pendant que tu utilises le script :
   ```powershell
   python server.py
   ```
4. Dans Violentmonkey : « Nouveau script », colle le contenu de `drive.user.js`, puis remplace
   `COLLE_ICI_LE_TOKEN` par le même token. Enregistre.

Le serveur n'écoute que sur ta machine (127.0.0.1) et exige le token à chaque requête.

## Renseigner les sélecteurs (une fois)

Les valeurs `TODO` en haut de `drive.user.js` sont à remplir. Sur carrefour.fr, connecté et
magasin choisi :

1. Fais une recherche à la main. Copie l'URL de la page de résultats et colle-la dans
   `SEARCH_URL`, en remplaçant le mot cherché par `{q}`.
2. Clic droit sur un produit → « Examiner l'élément » (F12). Repère, **dans la carte produit de la
   page de résultats** (le script n'ouvre jamais la fiche produit) :
   - `result_card` : le bloc qui contient un produit entier (le même pour tous les produits) ;
   - `result_name`, `result_price`, `result_link` : le nom, le prix et le lien, à l'intérieur du bloc
     (si le bloc est lui-même le lien, mets le même sélecteur que `result_card`). Le lien sert aussi à
     reconnaître la carte d'un produit déjà mémorisé ;
   - `add_button` : le bouton « Acheter » de la carte, pour un produit qui n'est pas dans le panier ;
   - `plus_button` : le « + » du compteur de quantité, qui apparaît dans la carte après l'ajout ;
   - `in_cart` : un élément présent dans la carte seulement quand le produit est déjà dans le panier
     (sert à confirmer l'ajout et à ne pas ajouter deux fois) ;
   - `cookie_accept` : le bouton des cookies, si une bannière s'affiche.
3. Pour tester un sélecteur : dans la console (F12), sur la page de résultats,
   `document.querySelectorAll("TON_SÉLECTEUR")` doit renvoyer le bon nombre d'éléments.
   Rappel de syntaxe : une classe s'écrit avec un point (`.ma-classe`), une balise + classe se colle
   (`article.ma-classe`), un espace veut dire « à l'intérieur de ».

Utilise des classes ou attributs stables (`data-testid`, `aria-label`…) plutôt que des noms
générés du type `css-1x2y3z`, qui changent à chaque mise à jour du site.

## Utilisation

1. `python server.py` dans un terminal.
2. Sur carrefour.fr (connecté, bon magasin), clique sur **« Remplir le panier depuis Tandoor »**
   dans le panneau en bas à droite.
3. Article déjà mémorisé : le script cherche le produit sur le site (d'abord par son nom exact, puis
   par le nom Tandoor), retrouve **sa carte** dans les résultats grâce à son lien, et clique sur
   « Acheter » puis sur « + » dans cette carte. Aucune fiche produit n'est ouverte.
   Article inconnu : le panneau affiche jusqu'à 5 produits, tu choisis, tu fixes la quantité, le choix
   est mémorisé et l'ajout se fait aussitôt, sur la même page. Tu peux aussi relancer une recherche,
   passer, ou ignorer pour toujours.
4. En fin de passage, le panneau affiche le récapitulatif. Vérifie le panier, puis paie toi-même.

## Pour Leclerc

Ajoute une ligne `// @match` avec l'adresse de ton drive Leclerc en haut du script, change `SITE`
en `"leclerc"`, et remplis `SEARCH_URL` et les sélecteurs de la même façon. Le plus simple est
de dupliquer le script (un par enseigne).

## Limites

- Testé sur une maquette construite d'après ta carte HTML (14 vérifications), mais pas sur le vrai site :
  les cas non vus (produit indisponible, carte sans bouton) restent à confirmer en réel.
- Un produit déjà dans le panier n'est pas ajouté une seconde fois : le récapitulatif indique
  « déjà dans le panier (n) ».
- Un produit sans bouton « Acheter » dans sa carte est signalé « indisponible ? » et rien n'est cliqué.
- Le script avance de page en page : ne ferme pas l'onglet et ne navigue pas ailleurs pendant un
  passage. Le bouton « Arrêter » interrompt proprement.
- Les protections du site peuvent encore réagir à des clics trop réguliers ; le script laisse des
  pauses aléatoires entre les actions. Si un captcha réapparaît, résous-le à la main puis relance.
- Les quantités Tandoor (200 g, etc.) ne sont pas des nombres de paquets : la quantité achetée est
  celle que tu fixes à la première association.
