// ==== photo-privacy:start (tools/plugin-vorlage/photo-privacy, nicht von Hand ändern) ====
const PP_TEXT = /*PP_TEXT*/{};

function ppRender(state) {
  const box = document.getElementById("KeepPhotoPlaces");
  if (!box) return;
  const tx = PP_TEXT[String(lang || document.documentElement.lang || "en").slice(0, 2)] || PP_TEXT.en;
  const card = document.getElementById("photoPrivacy");
  const uses = String(card?.dataset.ppUses || "places").split(",").filter((k) => tx[k] && k !== "guide").map((k) => tx[k]);
  for (const node of document.querySelectorAll("[data-pp]")) {
    const key = node.dataset.pp;
    node.textContent = key === "hint" ? tx.hint.replace("{uses}", uses.join(", ")) : (tx[key] || "");
  }
  const on = Boolean(state?.settings?.KeepPhotoPlaces);
  if (state?.settings && document.activeElement !== box) box.checked = on;
  const note = document.getElementById("photoPrivacyNote");
  if (note) { note.textContent = on ? tx.on : tx.off; note.className = on ? "status ok" : "status"; }
}

{
  const ppOriginalRender = render;
  // eslint-disable-next-line no-func-assign
  render = function (...args) {
    const out = ppOriginalRender.apply(this, args);
    try { ppRender(args[0]); } catch (_) { /* Seite läuft weiter */ }
    return out;
  };
  document.getElementById("KeepPhotoPlaces")?.addEventListener("change", (event) => save({ KeepPhotoPlaces: event.target.checked }));
  try { ppRender(current); } catch (_) { /* noch nicht geladen */ }
}
// ==== photo-privacy:end ====
