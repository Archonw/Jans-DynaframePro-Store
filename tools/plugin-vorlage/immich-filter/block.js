
// ------------------------------------------------------------ Immich-Filter (wie Photo Mosaic, immich_filters.py)

const IF_TEXT = ["City", "State", "Country", "TakenAfter", "TakenBefore", "Make", "Model", "Lens", "Description", "OcrText", "FileName", "SkipNames"];
const IF_NUMBER = ["LastDays", "MinMegapixels", "MinFileKB"];
const IF_CHECK = ["OnThisDay", "WithPeople", "CameraOnly", "NoScreenshots", "NotInAlbum"];
const IF_BOOL_SELECT = ["FavoritesOnly", "IncludeArchived"];
const IF_PICKERS = { People: ["./api/people", "people"], SkipAlbums: ["./api/albums", "albums"], SkipTags: ["./api/tags", "tags"] };
const ifLists = {};
const ifErrors = {};
const ifEsc = (text) => String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ifHere = (names) => names.filter((name) => el(name));
let ifSettings = null;

async function ifLoad(name, force = false) {
  if (ifLists[name] && !force) return;
  ifLists[name] = ifLists[name] || [];
  try {
    const result = await api(IF_PICKERS[name][0]);
    if (result.success === false) throw new Error(result.error || "?");
    ifLists[name] = result[IF_PICKERS[name][1]] || [];
    ifErrors[name] = "";
  } catch (error) {
    ifLists[name] = [];
    ifErrors[name] = error.message;
  }
  ifLists[name].loaded = true;
  if (ifSettings) ifRenderPickers(ifSettings);
}

function ifRenderPickers(s) {
  for (const name of Object.keys(IF_PICKERS)) {
    const box = el(name + "List");
    if (!box) continue;
    const items = ifLists[name];
    if (!items || !items.loaded) {
      if (s.ServerUrl && !items) ifLoad(name);
      if (!items) box.innerHTML = s.ServerUrl ? `<p class="hint">${ifEsc(t("ifLoading"))}</p>` : "";
      continue;
    }
    const chosen = new Set((s[name] || "").split(",").filter(Boolean));
    const query = el(name + "Filter").value.trim().toLowerCase();
    // Lange Listen: angehakte und gesuchte zuerst, höchstens 200 zeigen
    const rows = items.filter((a) => chosen.has(String(a.id)) || !query || String(a.name).toLowerCase().includes(query))
      .sort((a, b) => (chosen.has(String(b.id)) - chosen.has(String(a.id))) || String(a.name).localeCompare(String(b.name)))
      .slice(0, Math.max(200, chosen.size));
    const html = rows.map((a) => `<label title="${ifEsc(a.name)}"><input type="checkbox" value="${ifEsc(String(a.id))}" ${chosen.has(String(a.id)) ? "checked" : ""}>
        <span class="name">${ifEsc(a.name)}</span>${a.count != null ? `<span class="count">${fmt(a.count)}</span>` : ""}</label>`).join("");
    if (box.dataset.html !== html) { box.innerHTML = html; box.dataset.html = html; }
    const note = el(name + "Note");
    note.textContent = ifErrors[name] || (!items.length ? t("ifNothingHere") : chosen.size ? t(chosen.size === 1 ? "ifOneChosen" : "ifManyChosen", { n: chosen.size }) : "");
    note.className = "status" + (ifErrors[name] ? " bad" : "");
  }
}

function ifRender(s) {
  if (!el("immichFilters")) return;
  if (ifSettings && ifSettings.ServerUrl !== s.ServerUrl) {
    for (const name of Object.keys(ifLists)) delete ifLists[name];
  }
  ifSettings = s;
  for (const name of ifHere(IF_TEXT.concat(IF_NUMBER))) {
    if (document.activeElement !== el(name)) el(name).value = s[name] ?? "";
  }
  for (const name of ifHere(IF_CHECK)) el(name).checked = Boolean(s[name]);
  for (const name of ifHere(IF_BOOL_SELECT)) el(name).value = String(Boolean(s[name]));
  if (el("MinRating")) el("MinRating").value = String(s.MinRating || 0);
  if (el("Orientation")) el("Orientation").value = s.Orientation || "any";
  ifRenderPickers(s);
}

for (const name of ifHere(IF_TEXT)) el(name).addEventListener("change", (e) => save({ [name]: e.target.value }));
for (const name of ifHere(IF_NUMBER)) el(name).addEventListener("change", (e) => save({ [name]: Number(e.target.value) || 0 }));
for (const name of ifHere(IF_CHECK)) el(name).addEventListener("change", (e) => save({ [name]: e.target.checked }));
for (const name of ifHere(IF_BOOL_SELECT)) el(name).addEventListener("change", (e) => save({ [name]: e.target.value === "true" }));
if (el("MinRating")) el("MinRating").addEventListener("change", (e) => save({ MinRating: Number(e.target.value) }));
if (el("Orientation")) el("Orientation").addEventListener("change", (e) => save({ Orientation: e.target.value }));
for (const name of Object.keys(IF_PICKERS)) {
  if (!el(name + "List")) continue;
  el(name + "Filter").addEventListener("input", () => ifSettings && ifRenderPickers(ifSettings));
  el(name + "List").addEventListener("change", () => {
    const list = el(name + "List");
    const ticked = [...list.querySelectorAll("input:checked")].map((box) => box.value);
    // Angehakte behalten, die der Suchfilter gerade ausblendet
    const hidden = (ifSettings[name] || "").split(",").filter(Boolean)
      .filter((id) => !list.querySelector(`input[value="${CSS.escape(id)}"]`));
    save({ [name]: [...hidden, ...ticked].join(",") });
  });
}
