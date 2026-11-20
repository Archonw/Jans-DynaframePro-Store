// ==== folder-picker:start (tools/plugin-vorlage/folder-picker, nicht von Hand ändern) ====
// Liste „Ausgewählte Ordner in DynaFrame“: kurze Namen ab dem Medienordner, nach
// Medienordner gruppiert, lange Namen brechen um statt abgeschnitten zu werden.
// Gespeichert wird weiter der volle Pfad (value = id).
Object.assign(I18N, {
  fpTop: ["Nur die Fotos direkt in diesem Ordner", "Only the photos directly in this folder", "Solo las fotos directamente en esta carpeta"],
  fpMore: ["Ordner fehlt, z. B. auf einem NAS?", "Folder missing, e.g. on a NAS?", "¿Falta una carpeta, p. ej. en un NAS?"],
  fpMoreLink: ["Unter „Weitere Ordner“ eintragen", "Add it under “More folders”", "Añádela en «Más carpetas»"],
  fpNoMatch: ["Kein Ordner passt zur Suche.", "No folder matches the search.", "Ninguna carpeta coincide con la búsqueda."],
});

function fpRender(box, prefix, s, items) {
  const chosen = new Set(chosenItems(prefix, s));
  const query = el(prefix + "AlbumFilter").value.trim().toLowerCase();
  const rows = items.filter((a) => !query || [a.name, a.root, a.id].join(" ").toLowerCase().includes(query));
  const groups = new Map();
  for (const a of rows) {
    const key = a.rootPath ?? "";
    if (!groups.has(key)) groups.set(key, { label: a.root || "", path: key, rows: [] });
    groups.get(key).rows.push(a);
  }
  const many = new Set(items.map((a) => a.rootPath ?? "")).size > 1;
  const byName = (a, b) => String(a.name).localeCompare(String(b.name), undefined, { numeric: true, sensitivity: "base" });
  let html = "";
  for (const g of groups.values()) {
    // Angehaktes zuerst, damit es in einer langen Liste sichtbar bleibt
    g.rows.sort((a, b) => (chosen.has(String(b.id)) - chosen.has(String(a.id))) || (!!b.top - !!a.top) || byName(a, b));
    if (many) html += `<div class="fp-group"><b>${esc(g.label)}</b><small>${esc(g.path)}</small></div>`;
    html += g.rows.map((a) => {
      const leaf = a.leaf ?? a.name;
      const under = a.leaf == null ? "" : a.parent || (a.top ? t("fpTop") : "");
      return `<label class="fp-row" title="${esc(String(a.id))}"><input type="checkbox" value="${esc(String(a.id))}" ${chosen.has(String(a.id)) ? "checked" : ""}>
        <span class="fp-name"><b>${esc(leaf)}</b>${under ? `<small>${esc(under)}</small>` : ""}</span>${a.count != null ? `<span class="count">${fmt(a.count)}</span>` : ""}</label>`;
    }).join("");
  }
  if (items.length && !rows.length) html += `<p class="hint fp-wide">${esc(t("fpNoMatch"))}</p>`;
  if (el("Folders")) html += `<p class="hint fp-wide fp-more">${esc(t("fpMore"))} <a href="#" data-fp-more>${esc(t("fpMoreLink"))}</a></p>`;
  if (box.dataset.html !== html) { box.innerHTML = html; box.dataset.html = html; }
  if (listErrors.folders) setStatus(listErrors.folders, "bad", prefix + "Note");
  else if (!items.length) setStatus(t("noFolders"), "warn", prefix + "Note");
}

// „Weitere Ordner“: Karte aufklappen (Akkordeon) und hinscrollen
document.addEventListener("click", (e) => {
  const link = e.target.closest("[data-fp-more]");
  if (!link) return;
  e.preventDefault();
  const card = el("Folders").closest("section");
  const bar = card && card.querySelector(":scope > .fold-bar");
  if (card && card.classList.contains("fold-closed") && bar) bar.click();
  (card || el("Folders")).scrollIntoView({ behavior: "smooth", block: "start" });
  setTimeout(() => el("Folders").focus({ preventScroll: true }), 400);
});
// ==== folder-picker:end ====
