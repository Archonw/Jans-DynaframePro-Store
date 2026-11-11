// ------------------------------------------------------------ DynaFrame-Filter (wie Foto Mosaik, dynaframe_filters.py)

const DF_TEXT = ["DfAfter", "DfBefore", "DfPlace", "DfMake", "DfModel", "DfLens", "DfText", "DfFileName", "DfSkipNames"];
const DF_NUMBER = ["DfLastDays", "DfMinMegapixels"];
const DF_CHECK = ["DfOnThisDay", "DfCameraOnly", "DfNoScreenshots"];
const dfHere = (names) => names.filter((name) => el(name));

// render(): dfRender(state.settings, state) aufrufen
function dfRender(s, state) {
  if (!el("dynaframeFilters")) return;
  for (const name of dfHere(DF_TEXT.concat(DF_NUMBER))) {
    if (document.activeElement !== el(name)) el(name).value = s[name] || (DF_NUMBER.includes(name) ? 0 : "");
  }
  for (const name of dfHere(DF_CHECK)) el(name).checked = Boolean(s[name]);
  if (el("DfMinRating")) el("DfMinRating").value = String(s.DfMinRating || 0);
  if (el("DfOrientation")) el("DfOrientation").value = s.DfOrientation || "any";
  const note = el("dfNote");
  const count = state && state.dfCount;
  if (note) {
    note.textContent = count && count.total ? t("dfCount", { n: fmt(count.kept), m: fmt(count.total) }) : "";
    note.className = "status" + (count && count.total && !count.kept ? " bad" : "");
  }
}

for (const name of dfHere(DF_TEXT)) el(name).addEventListener("change", (e) => save({ [name]: e.target.value }));
for (const name of dfHere(DF_NUMBER)) el(name).addEventListener("change", (e) => save({ [name]: Number(e.target.value) || 0 }));
for (const name of dfHere(DF_CHECK)) el(name).addEventListener("change", (e) => save({ [name]: e.target.checked }));
if (el("DfMinRating")) el("DfMinRating").addEventListener("change", (e) => save({ DfMinRating: Number(e.target.value) }));
if (el("DfOrientation")) el("DfOrientation").addEventListener("change", (e) => save({ DfOrientation: e.target.value }));
