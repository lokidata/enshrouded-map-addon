"use strict";
const API = "/addon/api";
const $ = (id) => document.getElementById(id);
let state = "";
let busy = false;
let canAct = false;
const LEVELS = [["", "Aucun"], ["read", "Lecture"], ["action", "Action"]];

async function call(path, init) {
  const resp = await fetch(API + path, { credentials: "same-origin", ...init });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw { status: resp.status, detail: body.detail, wait: body.retry_after };
  }
  return resp.json();
}

const post = (path, body) =>
  call(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Addon": "1" },
    body: JSON.stringify(body),
  });

function say(text) {
  $("msg").textContent = text;
  $("msg").className = text ? "err" : "";
}

const REASONS = {
  confirmation_required: "Confirmez d'abord que les joueurs sont prévenus.",
  full_backup_confirmation_required: "Confirmez d'abord la sauvegarde complète du serveur.",
  invalid_request: "Requête invalide.",
  wrong_state: "Action impossible dans l'état actuel du serveur.",
  pelican_rejected: "Le panneau a refusé l'action.",
  pelican_denied: "Le panneau refuse l'accès à ce serveur.",
  pelican_not_found: "Serveur introuvable sur le panneau.",
  pelican_unavailable: "Le panneau du serveur est injoignable.",
  pelican_timeout: "Le panneau n'a pas répondu à temps : l'action a peut-être été faite, vérifiez l'état.",
  busy: "Une autre action est en cours, réessayez dans quelques secondes.",
  forbidden: "Action non autorisée.",
};

function failure(err) {
  const code = err.status;
  if (code === 429) return "Trop rapproché : réessayez dans " + (err.wait ?? "quelques") + " s.";
  if (REASONS[err.detail]) return REASONS[err.detail];
  if (code === 401) return "Connectez-vous d'abord sur le site.";
  if (code === 503) return "Le site est injoignable.";
  if (code === 502) return "Le panneau du serveur est injoignable.";
  return "Erreur inattendue (" + code + ").";
}

const fmtBytes = (n) => (n / 2 ** 30).toFixed(2) + " Go";
function fmtUptime(ms) {
  const m = Math.floor(ms / 60000);
  return Math.floor(m / 1440) + " j " + Math.floor((m % 1440) / 60) + " h " + (m % 60) + " min";
}

async function refreshStatus() {
  try {
    const s = await call("/status");
    $("s-state").textContent = s.state;
    $("s-cpu").textContent = s.cpu.toFixed(1) + " %";
    $("s-ram").textContent = fmtBytes(s.memory_bytes);
    $("s-disk").textContent = fmtBytes(s.disk_bytes);
    $("s-up").textContent = fmtUptime(s.uptime_ms);
    state = s.state;
    syncButtons();
    $("s-err").textContent = "";
  } catch (code) {
    $("s-err").textContent = failure(code);
    state = ""; // unknown: no power button until a status read succeeds
    syncButtons();
  }
}

function row(tbody, cells) {
  const tr = document.createElement("tr");
  for (const c of cells) {
    const td = document.createElement("td");
    if (c instanceof Node) td.append(c);
    else td.textContent = c;
    tr.append(td);
  }
  tbody.append(tr);
}

async function loadJournal() {
  const body = $("j-body");
  body.replaceChildren();
  for (const r of await call("/journal")) {
    row(body, [new Date(r.at).toLocaleString("fr-FR"), r.username, r.action, r.target, r.result]);
  }
}

async function loadAccess() {
  const body = $("a-body");
  body.replaceChildren();
  for (const u of await call("/access")) {
    const sel = document.createElement("select");
    sel.id = "lvl-" + u.user_key.replace(/\W/g, "_");
    for (const [v, label] of LEVELS) sel.add(new Option(label, v));
    sel.value = u.level || "";
    sel.addEventListener("change", async () => {
      try {
        await call("/access/" + encodeURIComponent(u.user_key), {
          method: "PUT",
          headers: { "Content-Type": "application/json", "X-Addon": "1" },
          body: JSON.stringify({ level: sel.value || null }),
        });
        say("");
      } catch (code) {
        say(failure(code));
        sel.value = u.level || "";
      }
      u.level = sel.value || null;
    });
    const label = document.createElement("label");
    label.htmlFor = sel.id;
    label.textContent = u.username;
    row(body, [label, sel]);
  }
}

const NEEDS = { start: "offline", stop: "running", restart: "running" };
const DONE = { start: "Démarrage demandé.", stop: "Arrêt demandé.", restart: "Redémarrage demandé." };

function syncButtons() {
  for (const b of document.querySelectorAll("[data-signal]")) {
    b.disabled = busy || state !== NEEDS[b.dataset.signal];
  }
  $("b-create").disabled = busy;
}

// Runs one write with every button locked; the server's reason is shown in French.
async function act(target, run, okText) {
  busy = true;
  $(target).textContent = "";
  syncButtons();
  try {
    await run();
    $(target).textContent = okText;
  } catch (err) {
    $(target).textContent = failure(err);
  }
  busy = false;
  const journal = $("journal").hidden ? null : loadJournal().catch((err) => say(failure(err)));
  await Promise.all([refreshStatus(), loadBackups(), journal]);
  syncButtons();
}

const power = (signal) =>
  act("act-msg", () => post("/power", signal === "start" ? { signal } : { signal, confirm: true }), DONE[signal]);

function ask(signal) {
  const dlg = $("confirm");
  $("c-title").textContent = signal === "stop" ? "Arrêter le serveur ?" : "Redémarrer le serveur ?";
  $("c-label").textContent = "J'ai prévenu les joueurs";
  $("c-warned").checked = false;
  $("c-ok").disabled = true;
  dlg.dataset.signal = signal;
  dlg.showModal();
  $("c-warned").focus();
}

function askFull() {
  // no BACKUP_IGNORED: the backup contains every file of the server and can be very large
  $("c-title").textContent = "Sauvegarder tout le serveur ?";
  $("c-label").textContent = "Je sais que cela sauvegarde tous les fichiers du serveur (très volumineux)";
  $("c-warned").checked = false;
  $("c-ok").disabled = true;
  $("confirm").dataset.signal = "backup";
  $("confirm").showModal();
  $("c-warned").focus();
}

function fmtSize(n) {
  return n >= 2 ** 30 ? (n / 2 ** 30).toFixed(2) + " Go" : (n / 2 ** 20).toFixed(1) + " Mo";
}

async function loadBackups() {
  const body = $("b-body");
  try {
    const rows = await call("/backups");
    body.replaceChildren();
    $("b-err").textContent = "";
    for (const b of rows) {
      const st = b.completed_at === null ? "en cours" : b.is_successful === false ? "échec" : "";
      row(body, [b.name, fmtSize(b.bytes), new Date(b.created_at).toLocaleString("fr-FR"), st]);
    }
  } catch (err) {
    $("b-err").textContent = failure(err);
  }
}

function tick() {
  if (!document.hidden) refreshStatus();
}

async function start() {
  let me;
  try {
    me = await call("/me");
  } catch (code) {
    say(failure(code));
    return;
  }
  if (!me.level) {
    say("Accès non accordé");
    return;
  }
  $("status").hidden = false;
  $("journal").hidden = false;
  $("backups").hidden = false;
  canAct = me.level === "action";
  $("actions").hidden = !canAct;
  $("b-actions").hidden = !canAct;
  for (const b of document.querySelectorAll("[data-signal]")) {
    b.addEventListener("click", () => (b.dataset.signal === "start" ? power("start") : ask(b.dataset.signal)));
  }
  $("b-create").addEventListener("click", () => {
    if (me.backup_filtered) act("b-msg", () => post("/backups", {}), "Sauvegarde lancée.");
    else askFull();
  });
  $("c-warned").addEventListener("change", () => ($("c-ok").disabled = !$("c-warned").checked));
  $("c-cancel").addEventListener("click", () => $("confirm").close());
  $("c-ok").addEventListener("click", () => {
    const signal = $("confirm").dataset.signal;
    $("confirm").close();
    if (signal === "backup") act("b-msg", () => post("/backups", { confirm_full: true }), "Sauvegarde lancée.");
    else power(signal);
  });
  try {
    await Promise.all([refreshStatus(), loadJournal(), loadBackups(), me.is_admin ? loadAccess() : null]);
  } catch (code) {
    say(failure(code));
  }
  $("access").hidden = !me.is_admin;
  setInterval(tick, 15000);
  document.addEventListener("visibilitychange", tick);
}

start();
