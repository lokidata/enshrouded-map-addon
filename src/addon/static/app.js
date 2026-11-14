"use strict";
const API = "/addon/api";
const $ = (id) => document.getElementById(id);
const LEVELS = [["", "Aucun"], ["read", "Lecture"], ["action", "Action"]];

async function call(path, init) {
  const resp = await fetch(API + path, { credentials: "same-origin", ...init });
  if (!resp.ok) throw resp.status;
  return resp.json();
}

function say(text) {
  $("msg").textContent = text;
  $("msg").className = text ? "err" : "";
}

function failure(code) {
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
    $("s-err").textContent = "";
  } catch (code) {
    $("s-err").textContent = failure(code);
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
  try {
    await Promise.all([refreshStatus(), loadJournal(), me.is_admin ? loadAccess() : null]);
  } catch (code) {
    say(failure(code));
  }
  $("access").hidden = !me.is_admin;
  setInterval(tick, 15000);
  document.addEventListener("visibilitychange", tick);
}

start();
