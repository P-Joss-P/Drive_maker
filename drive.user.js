// ==UserScript==
// @name         Drive auto
// @namespace    drive-auto
// @version      0.2
// @description  Remplit le panier drive depuis la liste Tandoor (via le serveur local), dans ton vrai navigateur
// @match        https://www.carrefour.fr/*
// @noframes
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-idle
// @license      AGPL-3.0-or-later
// ==/UserScript==
// SPDX-FileCopyrightText: 2026 P-Joss-P
// SPDX-License-Identifier: AGPL-3.0-or-later

(function () {
  "use strict";

  // ===================== À RÉGLER =====================
  const SERVER = "http://127.0.0.1:8765";
  const TOKEN = "COLLE_ICI_LE_TOKEN"; // le même que DRIVE_LOCAL_TOKEN dans .env
  const SITE = "carrefour";
  // URL d'une recherche faite à la main, avec le mot remplacé par {q}
  const SEARCH_URL = "https://www.carrefour.fr/s?q={q}";
  // Sélecteurs CSS ("TODO" = pas encore renseigné). Tous sont cherchés DANS une carte
  // produit de la page de résultats : le script n'ouvre jamais la fiche produit.
  const SEL = {
    cookie_accept: "TODO", // bouton d'acceptation des cookies (optionnel)
    result_card: "article.product-list-card-plp-grid-new", // un produit dans les résultats
    result_name: "p.product-card-title__text",
    result_price: '[data-testid="product-price__amount--main"]',
    result_price_per_unit_label: ".product-list-card-plp-grid-new__per-unit-label", // optionnel
    result_link: "a.product-list-card-plp-grid-new__title-container", // sert aussi à reconnaître la carte
    add_button: '.add-to-cart button[aria-label^="Ajouter le produit"]', // « Acheter », dans la carte
    plus_button: "button.c-base-input__append__icon__button", // « + » du compteur, dans la carte
    in_cart: ".quantity-button--has-value", // présent quand le produit est déjà dans le panier
  };
  // ====================================================

  const STATE_KEY = "drive_state_v1";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const pause = () => sleep(800 + Math.random() * 1400);
  const ok = (k) => typeof SEL[k] === "string" && !SEL[k].startsWith("TODO");
  const load = () => GM_getValue(STATE_KEY, null);
  const save = (s) => GM_setValue(STATE_KEY, s);

  function pathOf(u) {
    try {
      return new URL(u, location.href).pathname;
    } catch (e) {
      return "";
    }
  }

  async function waitFor(selector, timeout = 10000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      const e = document.querySelector(selector);
      if (e) return e;
      await sleep(250);
    }
    return null;
  }

  function pick(card, sel) {
    return card.matches(sel) ? card : card.querySelector(sel);
  }

  // La carte d'un produit est reconnue par le chemin de son lien (/p/...), pas par sa position :
  // on ne peut donc jamais cliquer sur le bouton d'un autre produit.
  function findCard(url) {
    const want = pathOf(url);
    if (!want) return null;
    for (const c of document.querySelectorAll(SEL.result_card)) {
      const l = pick(c, SEL.result_link);
      if (l && pathOf(l.getAttribute("href")) === want) return c;
    }
    return null;
  }

  async function waitFind(url, timeout) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      if (findCard(url)) return true;
      await sleep(250);
    }
    return false;
  }

  async function waitInCard(url, sel, timeout) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      const c = findCard(url);
      const e = c && c.querySelector(sel);
      if (e) return e;
      await sleep(250);
    }
    return null;
  }

  function searchUrl(query) {
    return SEARCH_URL.replace("{q}", encodeURIComponent(query));
  }

  function onSearchPage(query) {
    const want = new URL(searchUrl(query), location.href);
    return want.pathname === location.pathname && want.search === location.search;
  }

  // ---------- communication avec le serveur local ----------
  function api(method, path, body) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method,
        url: SERVER + path,
        headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
        data: body ? JSON.stringify(body) : undefined,
        onload: (r) => {
          let data = null;
          try { data = JSON.parse(r.responseText); } catch (e) { /* ignoré */ }
          if (r.status >= 200 && r.status < 300) resolve(data);
          else reject(new Error((data && data.error) || "HTTP " + r.status));
        },
        onerror: () => reject(new Error("Serveur local injoignable : python server.py est-il lancé ?")),
      });
    });
  }

  // ---------- interface ----------
  function el(tag, o = {}, kids = []) {
    const e = document.createElement(tag);
    if (o.text !== undefined) e.textContent = o.text;
    if (o.style) e.style.cssText = o.style;
    for (const k of ["type", "value", "placeholder", "min"]) if (o[k] !== undefined) e[k] = o[k];
    if (o.onclick) e.addEventListener("click", o.onclick);
    kids.forEach((c) => e.appendChild(c));
    return e;
  }
  const title = (t) => el("div", { text: t, style: "font-weight:700;margin-bottom:6px" });
  const note = (t) => el("div", { text: t, style: "margin:4px 0" });
  const btn = (t, f, extra = "") =>
    el("button", { text: t, onclick: f, style: "margin:2px 4px 2px 0;padding:4px 8px;cursor:pointer;" + extra });
  const choiceStyle = "display:block;width:100%;text-align:left;";

  const panel = el("div", {
    style:
      "position:fixed;right:12px;bottom:12px;z-index:2147483647;width:340px;max-height:70vh;" +
      "overflow:auto;background:#fff;color:#111;border:2px solid #0a58ca;border-radius:8px;" +
      "font:13px/1.4 system-ui,sans-serif;padding:10px;box-shadow:0 4px 16px rgba(0,0,0,.3)",
  });
  document.documentElement.appendChild(panel);
  const setPanel = (...nodes) => panel.replaceChildren(...nodes);

  function renderIdle(s) {
    const nodes = [title("Drive auto")];
    if (s && s.finished) {
      nodes.push(note("Dernier passage :"));
      s.results.forEach((r) => nodes.push(note(`• ${r.name} : ${r.result}`)));
      nodes.push(note("Vérifie ton panier avant de payer."));
      nodes.push(btn("Effacer", () => { save(null); renderIdle(null); }));
    }
    nodes.push(btn("Remplir le panier depuis Tandoor", start));
    setPanel(...nodes);
  }

  function fatal(msg) {
    const s = load();
    if (s) { s.running = false; save(s); }
    setPanel(title("Arrêt"), note(msg), btn("Fermer", () => renderIdle(null)));
  }

  function showProgress(s, item) {
    setPanel(title(`Article ${s.i + 1}/${s.items.length} : ${item.name}`), btn("Arrêter", stop));
  }

  // ---------- déroulement ----------
  async function start() {
    setPanel(title("Drive auto"), note("Lecture de la liste Tandoor…"));
    try {
      const data = await api("GET", "/items?site=" + SITE);
      if (!data.items.length) {
        setPanel(title("Drive auto"), note("La liste Tandoor est vide."), btn("OK", () => renderIdle(null)));
        return;
      }
      save({ running: true, items: data.items, i: 0, results: [] });
      step();
    } catch (e) {
      fatal(e.message);
    }
  }

  function stop() {
    const s = load();
    if (s) { s.running = false; s.finished = true; save(s); }
    renderIdle(load());
  }

  function finish(s) {
    s.running = false;
    s.finished = true;
    save(s);
    renderIdle(s);
  }

  function advance(s, result) {
    const cur = load();
    if (!cur || !cur.running) return renderIdle(cur); // arrêté entre-temps
    s.results.push({ name: s.items[s.i].name, result });
    s.i += 1;
    save(s);
    return pause().then(step);
  }

  async function dismissCookies() {
    if (!ok("cookie_accept")) return;
    const b = await waitFor(SEL.cookie_accept, 1500);
    if (b) { b.click(); await pause(); }
  }

  async function step() {
    const s = load();
    if (!s || !s.running) return renderIdle(s);
    if (s.i >= s.items.length) return finish(s);
    const item = s.items[s.i];
    showProgress(s, item);
    await dismissCookies();
    if (item.status === "ignored") return advance(s, "ignoré");
    if (item.status === "known") return doKnown(s, item);
    return doUnknown(s, item);
  }

  // Article déjà mémorisé : on cherche le produit (par son nom exact, puis par le nom Tandoor)
  // et on l'ajoute depuis sa carte dans les résultats.
  async function doKnown(s, item) {
    if (!["result_card", "result_name", "result_link", "add_button"].every(ok)) {
      return fatal("Sélecteurs non renseignés (result_card, result_name, result_link, add_button).");
    }
    const queries = [...new Set([item.product_name, item.name].filter(Boolean))];
    const qi = item.qi || 0;
    if (qi >= queries.length) return advance(s, "échec (produit introuvable dans les résultats de recherche)");
    const query = queries[qi];
    // On ne navigue qu'une fois par recherche, pour éviter une boucle si le site réécrit l'URL.
    if (!onSearchPage(query) && item.navQ !== qi) {
      item.navQ = qi;
      save(s);
      location.href = searchUrl(query);
      return;
    }
    await waitFor(SEL.result_card + " " + SEL.result_name, 10000);
    if (!(await waitFind(item.product_url, 3000))) {
      item.qi = qi + 1; // on essaie la recherche suivante
      save(s);
      return step();
    }
    return addFromCard(s, item);
  }

  async function addFromCard(s, item) {
    const url = item.product_url;
    const inCard = (sel) => {
      const c = findCard(url);
      return c ? c.querySelector(sel) : null;
    };
    const count = () => {
      const i = inCard('input[type="number"]');
      return parseInt(i && i.value, 10) || 0;
    };
    if (!findCard(url)) return advance(s, "échec (carte du produit introuvable)");
    if (ok("in_cart") && inCard(SEL.in_cart)) {
      return advance(s, `déjà dans le panier (${count() || "?"})`);
    }
    if (!inCard(SEL.add_button)) {
      return advance(s, "indisponible ? (pas de bouton d'ajout sur la carte du produit)");
    }
    inCard(SEL.add_button).scrollIntoView({ block: "center" });
    await pause();
    const add = inCard(SEL.add_button); // la carte a pu être redessinée entre-temps
    if (!add) return advance(s, "échec (bouton d'ajout disparu)");
    add.click();

    const confirmSel = ok("in_cart") ? SEL.in_cart : ok("plus_button") ? SEL.plus_button : null;
    if (confirmSel && !(await waitInCard(url, confirmSel, 8000))) {
      return advance(s, "échec (ajout non confirmé par le site)");
    }
    for (let k = 1; k < item.qty; k++) {
      if (!ok("plus_button")) return advance(s, "1 seul ajouté (plus_button non renseigné)");
      await pause();
      const plus = await waitInCard(url, SEL.plus_button, 5000);
      if (!plus) return advance(s, `${k} ajouté(s) sur ${item.qty} (bouton + introuvable)`);
      plus.click();
    }
    await pause();
    const n = count() || item.qty;
    const label = `ajouté ${n} x ${item.product_name || ""}`.trim();
    return advance(s, n === item.qty ? label : `${label} (${item.qty} demandé(s))`);
  }

  // Article inconnu : recherche, choix dans le panneau, puis ajout sur la MÊME page.
  async function doUnknown(s, item) {
    if (!["result_card", "result_name", "result_price", "result_link"].every(ok)) {
      return fatal("Sélecteurs de recherche non renseignés (result_card, result_name, result_price, result_link).");
    }
    if (!item.searched) {
      item.searched = true;
      save(s);
      location.href = searchUrl(item.query || item.name);
      return;
    }
    await waitFor(SEL.result_card + " " + SEL.result_name, 10000);
    const nCards = document.querySelectorAll(SEL.result_card).length;
    const cands = [...document.querySelectorAll(SEL.result_card)]
      .slice(0, 5)
      .map((c) => {
        const name = (pick(c, SEL.result_name) || {}).textContent;
        const price = (pick(c, SEL.result_price) || {}).textContent;
        const unit = ok("result_price_per_unit_label") ? (pick(c, SEL.result_price_per_unit_label) || {}).textContent : "";
        const link = pick(c, SEL.result_link);
        const href = link && link.getAttribute("href");
        if (!name || !href) return null;
        const clean = (t) => (t || "").trim().replace(/\s+/g, " ").replace(/\s+([,.])/g, "$1");
        return { name: clean(name), price: clean(price), unit: clean(unit), url: new URL(href, location.href).href };
      })
      .filter(Boolean);
    showChoices(s, item, cands, nCards);
  }

  function showChoices(s, item, cands, nCards) {
    const qty = el("input", { type: "number", value: "1", min: "1", style: "width:52px" });
    const q = el("input", { type: "text", placeholder: "Autre recherche", style: "width:150px" });
    const nodes = [title(`« ${item.name} » : à choisir`)];
    if (!cands.length) {
      nodes.push(note(`Aucun résultat (${nCards} bloc(s) pour « ${SEL.result_card} » sur ${location.pathname}${location.search}).`));
    }
    cands.forEach((c, n) =>
      nodes.push(
        btn(
          `${n + 1}. ${c.name} [${c.price}${c.unit ? " · " + c.unit : ""}]`,
          () => choose(s, item, c, Math.max(1, parseInt(qty.value, 10) || 1)),
          choiceStyle
        )
      )
    );
    nodes.push(el("div", { style: "margin:6px 0" }, [el("span", { text: "Quantité : " }), qty]));
    nodes.push(
      el("div", { style: "margin:6px 0" }, [
        q,
        btn("Chercher", () => {
          if (!q.value.trim()) return;
          item.query = q.value.trim();
          item.searched = false;
          save(s);
          step();
        }),
      ])
    );
    nodes.push(btn("Passer cette fois", () => advance(s, "à voir")));
    nodes.push(btn("Ignorer toujours", () => ignoreItem(s, item)));
    nodes.push(btn("Arrêter", stop));
    setPanel(...nodes);
  }

  async function choose(s, item, c, qty) {
    try {
      await api("POST", "/mapping", {
        site: SITE, name: item.name, product_name: c.name, product_url: c.url, qty, ignored: false,
      });
    } catch (e) {
      return fatal(e.message);
    }
    Object.assign(item, { status: "known", product_name: c.name, product_url: c.url, qty, qi: 0, navQ: 0 });
    save(s);
    showProgress(s, item);
    return addFromCard(s, item); // on est déjà sur la page de résultats : pas de navigation
  }

  async function ignoreItem(s, item) {
    try {
      await api("POST", "/mapping", { site: SITE, name: item.name, ignored: true });
    } catch (e) {
      return fatal(e.message);
    }
    return advance(s, "ignoré (mémorisé)");
  }

  // ---------- démarrage ----------
  const s0 = load();
  if (s0 && s0.running) step();
  else renderIdle(s0);
})();
