"use strict";
// Chestsort editor. The edited state lives in memory only; nothing is stored in the browser.
const CS_REASONS = {
  changed_elsewhere: "Le fichier a changé : rechargez.",
  too_large: "Le fichier est trop gros (1 Mo au maximum).",
  file_invalid: "Le fichier du serveur n'est pas valide : corrigez-le dans le panneau.",
  invalid_content: "Le contenu est refusé.",
  backup_failed: "La copie de secours a échoué : rien n'a été modifié.",
  verify_failed: "L'écriture n'a pas pu être vérifiée : l'ancien contenu a été remis, vérifiez le fichier.",
  rollback_failed: "L'écriture a échoué et l'ancien contenu n'a pas pu être remis : le fichier est peut-être abîmé. Restaurez la copie de secours (bouton Restaurer ou panneau).",
  file_not_utf8: "Le fichier n'est pas en UTF-8 : rien n'a été modifié, corrigez-le dans le panneau.",
  invalid_backup_name: "Nom de copie invalide.",
  unknown_backup: "Cette copie n'existe plus.",
  confirmation_required: "Confirmez d'abord que vous avez relu.",
};

// version: bumped by every edit, so a preview answer for older content is dropped
let cs = { cats: {}, hash: "", selected: null, previewed: false, edit: false, version: 0 };

function csFail(err) {
  let base = CS_REASONS[err.detail] || failure(err);
  if (err.backup) base += " Copie à restaurer : " + err.backup + ".";
  return err.errors && err.errors.length ? base + "\n- " + err.errors.join("\n- ") : base;
}

// only empty lines are dropped: a line is kept exactly as typed (the diff shows it)
const csLines = (text) => text.split("\n").filter((l) => l !== "");

function csShowErr(text) {
  $("cs-err").textContent = text;
  $("cs-reload").hidden = !text.startsWith("Le fichier a changé");
}

function csDirty() {
  cs.version++;
  cs.previewed = false;
  $("cs-save").disabled = true;
  $("cs-diff").textContent = "";
}

function csFillList(keep) {
  const sel = $("cs-list");
  sel.replaceChildren();
  for (const name of Object.keys(cs.cats)) sel.add(new Option(name, name));
  cs.selected = keep in cs.cats ? keep : (Object.keys(cs.cats)[0] ?? null);
  if (cs.selected !== null) sel.value = cs.selected;
  csFillEditors();
}

function csFillEditors() {
  const c = cs.selected === null ? { words: [], items: [] } : cs.cats[cs.selected];
  $("cs-name").value = cs.selected ?? "";
  $("cs-words").disabled = $("cs-items").disabled = cs.selected === null;
  $("cs-words").value = c.words.join("\n");
  $("cs-words-n").textContent = c.words.length + " mots";
  $("cs-filter").value = "";
  csShowItems();
}

// Only the selected category's items are in the DOM; a filter makes the box read-only.
function csShowItems() {
  const items = cs.selected === null ? [] : cs.cats[cs.selected].items;
  const q = $("cs-filter").value.trim().toLowerCase();
  const shown = q ? items.filter((i) => i.toLowerCase().includes(q)) : items;
  $("cs-items").value = shown.join("\n");
  $("cs-items").readOnly = !cs.edit || q !== "";
  $("cs-items-n").textContent = q ? shown.length + " sur " + items.length + " objets" : items.length + " objets";
}

function csSelectedChanged() {
  cs.selected = $("cs-list").value;
  csFillEditors();
}

async function csLoad() {
  csShowErr("");
  try {
    const data = await call("/chestsort");
    cs.cats = data.categories;
    cs.hash = data.hash;
    csDirty();
    csFillList(cs.selected);
  } catch (err) {
    csShowErr(csFail(err));
  }
  if (cs.edit) csLoadBackups();
}

async function csLoadBackups() {
  const sel = $("cs-bak");
  sel.replaceChildren();
  try {
    for (const name of await call("/chestsort/backups")) sel.add(new Option(name, name));
    $("cs-restore").disabled = sel.options.length === 0;
  } catch (err) {
    csShowErr(csFail(err));
  }
}

async function csPreview() {
  csShowErr("");
  $("cs-msg").textContent = "";
  const version = cs.version;
  try {
    const r = await post("/chestsort/preview", { categories: cs.cats });
    if (version !== cs.version) return; // edited meanwhile: this diff is not the current content
    const out = [];
    if (r.errors.length) out.push("Erreurs :", ...r.errors.map((e) => "- " + e), "");
    if (r.warnings.length) out.push("Avertissements :", ...r.warnings.map((w) => "- " + w), "");
    out.push(r.changed ? "Changements :" : "Aucun changement.", ...r.diff);
    $("cs-diff").textContent = out.join("\n");
    cs.previewed = r.errors.length === 0 && r.changed;
    $("cs-save").disabled = !cs.previewed;
  } catch (err) {
    csShowErr(csFail(err));
  }
}

function csAsk(signal, title, label) {
  $("c-title").textContent = title;
  $("c-label").textContent = label;
  $("c-warned").checked = false;
  $("c-ok").disabled = true;
  $("confirm").dataset.signal = signal;
  $("confirm").showModal();
  $("c-warned").focus();
}

async function csWrite(run) {
  csShowErr("");
  $("cs-msg").textContent = "";
  $("cs-save").disabled = true;
  try {
    const r = await run();
    $("cs-msg").textContent = "Enregistré. Copie de secours : " + r.backup + ". Le mod recharge le fichier en quelques secondes.";
    cs.hash = r.hash;
    await csLoad();
  } catch (err) {
    csShowErr(csFail(err));
    $("cs-save").disabled = !cs.previewed;
  }
}

function csAdd() {
  const name = $("cs-name").value.trim();
  if (!name) return csShowErr("Donnez un nom à la catégorie.");
  if (Object.keys(cs.cats).some((n) => n.toLowerCase() === name.toLowerCase())) {
    return csShowErr("Une catégorie porte déjà ce nom.");
  }
  csShowErr("");
  cs.cats[name] = { words: [], items: [] };
  csDirty();
  csFillList(name);
  $("cs-words").focus();
}

function csRename() {
  const name = $("cs-name").value.trim();
  if (cs.selected === null || !name || name === cs.selected) return;
  if (Object.keys(cs.cats).some((n) => n !== cs.selected && n.toLowerCase() === name.toLowerCase())) {
    return csShowErr("Une catégorie porte déjà ce nom.");
  }
  csShowErr("");
  const next = {};
  for (const [n, c] of Object.entries(cs.cats)) next[n === cs.selected ? name : n] = c; // keeps the order
  cs.cats = next;
  csDirty();
  csFillList(name);
}

function initChestsort(me) {
  cs.edit = me.level === "action";
  $("chestsort").hidden = false;
  for (const id of ["cs-edit", "cs-act", "cs-bak-box"]) $(id).hidden = !cs.edit;
  $("cs-words").readOnly = !cs.edit;
  $("cs-list").addEventListener("change", csSelectedChanged);
  $("cs-filter").addEventListener("input", csShowItems);
  $("cs-reload").addEventListener("click", csLoad);
  if (cs.edit) {
    $("cs-words").addEventListener("input", () => {
      if (cs.selected === null) return;
      cs.cats[cs.selected].words = csLines($("cs-words").value);
      $("cs-words-n").textContent = cs.cats[cs.selected].words.length + " mots";
      csDirty();
    });
    $("cs-items").addEventListener("input", () => {
      if (cs.selected === null) return;
      cs.cats[cs.selected].items = csLines($("cs-items").value);
      $("cs-items-n").textContent = cs.cats[cs.selected].items.length + " objets";
      csDirty();
    });
    $("cs-add").addEventListener("click", csAdd);
    $("cs-rename").addEventListener("click", csRename);
    $("cs-del").addEventListener("click", () => {
      if (cs.selected !== null) csAsk("cs-del", "Supprimer la catégorie « " + cs.selected + " » ?", "Je confirme la suppression");
    });
    $("cs-preview").addEventListener("click", csPreview);
    $("cs-save").addEventListener("click", () => csAsk("cs-save", "Enregistrer les changements ?", "J'ai relu les changements"));
    $("cs-restore").addEventListener("click", () => {
      if ($("cs-bak").value) csAsk("cs-restore", "Restaurer " + $("cs-bak").value + " ?", "Je sais que les modifications non enregistrées seront perdues");
    });
    ON_CONFIRM["cs-del"] = () => {
      delete cs.cats[cs.selected];
      csDirty();
      csFillList(null);
    };
    ON_CONFIRM["cs-save"] = () => csWrite(() => call("/chestsort", {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-Addon": "1" },
      body: JSON.stringify({ categories: cs.cats, base_hash: cs.hash, confirm: true }),
    }));
    ON_CONFIRM["cs-restore"] = () => csWrite(() => post("/chestsort/restore", { name: $("cs-bak").value, base_hash: cs.hash, confirm: true }));
  }
  csLoad();
}
