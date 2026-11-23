"use strict";

const state = {
  families: [],
  currentSlug: "pomacentridae",
  dataset: null,
  speciesBySci: new Map(),
  viewMode: "genera", // "genera" | "genus_species" | "all_species"
  selectedGenus: null,
  dismissedGenera: new Set(),
  dismissedSpecies: new Set(),
  undoStack: [], // { type: "genus", genus } | { type: "species", sci }
  traitInputs: {
    dorsalSpines: null,
    dorsalSoft: null,
    analSoft: null,
  },
  hideMismatch: true,
  activeModalSci: null,
  targetPhotoObjectUrl: null,
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheElements();
  bindEvents();
  registerServiceWorker();
  initApp();
});

function cacheElements() {
  const ids = [
    "family-select", "offline-status",
    "photo-preview-box", "target-photo-img", "photo-empty-hint",
    "camera-input", "file-input", "ai-candidate-btn", "clear-photo-btn", "ai-notice",
    "input-dorsal-spines", "input-dorsal-soft", "input-anal-soft", "clear-traits-btn",
    "trait-counts-pills", "hide-mismatch-toggle",
    "remaining-count", "dismissed-count",
    "tab-genera", "tab-all-species", "undo-btn", "reset-all-btn",
    "genus-breadcrumb", "back-to-genera-btn", "selected-genus-title", "selected-genus-sub",
    "tile-grid", "empty-state", "empty-reset-btn",
    "detail-modal", "modal-backdrop", "modal-close-btn", "detail-close-footer-btn",
    "detail-genus-badge", "detail-ja-name", "detail-sci-name",
    "detail-main-photo", "detail-no-photo", "detail-photo-credit", "detail-gallery",
    "detail-color-pattern", "detail-color-source",
    "detail-field-marks", "detail-marks-source",
    "detail-similar-list", "detail-similar-source",
    "detail-traits-grid", "detail-dismiss-btn",
    "detail-evidence-section", "detail-evidence-list",
  ];
  for (const id of ids) {
    els[id] = document.getElementById(id);
  }
}

function bindEvents() {
  els["family-select"].addEventListener("change", (e) => {
    loadFamilyDataset(e.target.value);
  });

  els["camera-input"].addEventListener("change", handlePhotoFileChange);
  els["file-input"].addEventListener("change", handlePhotoFileChange);

  els["photo-preview-box"].addEventListener("click", () => {
    if (els["photo-preview-box"].classList.contains("has-photo")) {
      els["photo-preview-box"].classList.toggle("expanded");
    } else {
      els["file-input"].click();
    }
  });

  els["clear-photo-btn"].addEventListener("click", clearTargetPhoto);

  els["ai-candidate-btn"].addEventListener("click", () => {
    const notice = els["ai-notice"];
    if (!notice.classList.contains("hidden")) {
      notice.classList.add("hidden");
      return;
    }
    notice.textContent =
      "写真からの自動候補表示は準備中です（今後、端末内ONNX推論モデルを搭載予定）。現在は上の写真を見ながら下のタイル✕消去と形質フィルタで絞り込めます。";
    notice.classList.remove("hidden");
  });

  const onTraitChange = () => {
    state.traitInputs.dorsalSpines = parseIntOrNull(els["input-dorsal-spines"].value);
    state.traitInputs.dorsalSoft = parseIntOrNull(els["input-dorsal-soft"].value);
    state.traitInputs.analSoft = parseIntOrNull(els["input-anal-soft"].value);
    render();
  };

  for (const id of ["input-dorsal-spines", "input-dorsal-soft", "input-anal-soft"]) {
    els[id].addEventListener("input", onTraitChange);
  }

  document.querySelectorAll(".step-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      const delta = Number(btn.dataset.delta);
      const cur = parseIntOrNull(target.value);
      const next = cur === null ? (delta > 0 ? Number(target.min || 1) : 10) : Math.max(1, cur + delta);
      target.value = String(next);
      onTraitChange();
    });
  });

  els["hide-mismatch-toggle"].addEventListener("change", (e) => {
    state.hideMismatch = e.target.checked;
    render();
  });

  els["clear-traits-btn"].addEventListener("click", clearTraits);

  els["tab-genera"].addEventListener("click", () => {
    state.viewMode = "genera";
    state.selectedGenus = null;
    render();
  });

  els["tab-all-species"].addEventListener("click", () => {
    state.viewMode = "all_species";
    state.selectedGenus = null;
    render();
  });

  els["back-to-genera-btn"].addEventListener("click", () => {
    state.viewMode = "genera";
    state.selectedGenus = null;
    render();
  });

  els["undo-btn"].addEventListener("click", undoLastDismiss);
  els["reset-all-btn"].addEventListener("click", resetAll);
  els["empty-reset-btn"].addEventListener("click", resetAll);

  els["modal-backdrop"].addEventListener("click", closeDetailModal);
  els["modal-close-btn"].addEventListener("click", closeDetailModal);
  els["detail-close-footer-btn"].addEventListener("click", closeDetailModal);

  els["detail-dismiss-btn"].addEventListener("click", () => {
    if (state.activeModalSci) {
      const sci = state.activeModalSci;
      closeDetailModal();
      dismissSpecies(sci);
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !els["detail-modal"].classList.contains("hidden")) {
      closeDetailModal();
    }
  });
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    els["offline-status"].textContent = "オンラインモード";
    return;
  }

  navigator.serviceWorker
    .register("./sw.js")
    .then(() => {
      els["offline-status"].textContent = "オフライン同期中";
    })
    .catch(() => {
      els["offline-status"].textContent = "キャッシュ未対応";
    });

  navigator.serviceWorker.addEventListener("message", (event) => {
    const msg = event.data || {};
    if (msg.type === "PRECACHE_DONE") {
      els["offline-status"].textContent = "オフライン対応済";
      els["offline-status"].classList.add("ready");
    }
  });
}

async function initApp() {
  try {
    const res = await fetch("./data/families.json");
    const manifest = await res.json();
    state.families = manifest.families || [];
    els["family-select"].innerHTML = state.families
      .map((f) => `<option value="${escapeHtml(f.slug)}">${escapeHtml(f.family_ja || f.family)} (${f.species_count}種)</option>`)
      .join("");
    if (state.families.length > 0) {
      await loadFamilyDataset(state.families[0].slug);
    }
  } catch (err) {
    els["tile-grid"].innerHTML = `<div class="empty-state">データの読み込みに失敗しました: ${escapeHtml(String(err))}</div>`;
  }
}

async function loadFamilyDataset(slug) {
  state.currentSlug = slug;
  state.viewMode = "genera";
  state.selectedGenus = null;
  state.dismissedGenera.clear();
  state.dismissedSpecies.clear();
  state.undoStack = [];
  closeDetailModal();

  const res = await fetch(`./data/${slug}.json`);
  const data = await res.json();
  state.dataset = data;
  state.speciesBySci = new Map(data.species.map((s) => [s.scientific_name, s]));

  // Request Service Worker to precache representative photos for offline use
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.ready.then((reg) => {
      if (reg.active) {
        const urls = [];
        for (const g of data.genera) {
          if (g.photo && g.photo.url) urls.push(g.photo.url);
        }
        for (const sp of data.species) {
          if (sp.photo && sp.photo.url) urls.push(sp.photo.url);
        }
        reg.active.postMessage({ type: "PRECACHE_PHOTOS", urls });
      }
    });
  }

  render();
}

function handlePhotoFileChange(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  if (state.targetPhotoObjectUrl) {
    URL.revokeObjectURL(state.targetPhotoObjectUrl);
  }
  const url = URL.createObjectURL(file);
  state.targetPhotoObjectUrl = url;
  els["target-photo-img"].src = url;
  els["target-photo-img"].classList.remove("hidden");
  els["photo-empty-hint"].classList.add("hidden");
  els["photo-preview-box"].classList.remove("empty");
  els["photo-preview-box"].classList.add("has-photo");
  els["clear-photo-btn"].classList.remove("hidden");
}

function clearTargetPhoto() {
  if (state.targetPhotoObjectUrl) {
    URL.revokeObjectURL(state.targetPhotoObjectUrl);
    state.targetPhotoObjectUrl = null;
  }
  els["camera-input"].value = "";
  els["file-input"].value = "";
  els["target-photo-img"].src = "";
  els["target-photo-img"].classList.add("hidden");
  els["photo-empty-hint"].classList.remove("hidden");
  els["photo-preview-box"].classList.add("empty");
  els["photo-preview-box"].classList.remove("has-photo", "expanded");
  els["clear-photo-btn"].classList.add("hidden");
}

function parseIntOrNull(val) {
  const s = String(val ?? "").trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isInteger(n) && n > 0 ? n : null;
}

function compareTrait(rangeObj, inputVal) {
  if (inputVal === null) return "none";
  if (!rangeObj || rangeObj.min === null || rangeObj.max === null) return "unknown";
  return inputVal >= rangeObj.min && inputVal <= rangeObj.max ? "match" : "mismatch";
}

function evaluateSpecies(sp) {
  const { dorsalSpines, dorsalSoft, analSoft } = state.traitInputs;
  const active = dorsalSpines !== null || dorsalSoft !== null || analSoft !== null;
  if (!active) {
    return { status: "all", details: { dorsalSpines: "none", dorsalSoft: "none", analSoft: "none" } };
  }
  const details = {
    dorsalSpines: compareTrait(sp.traits.dorsal_spines, dorsalSpines),
    dorsalSoft: compareTrait(sp.traits.dorsal_soft_rays, dorsalSoft),
    analSoft: compareTrait(sp.traits.anal_soft_rays, analSoft),
  };
  const activeResults = Object.values(details).filter((r) => r !== "none");
  if (activeResults.includes("mismatch")) {
    return { status: "mismatch", details };
  }
  if (activeResults.includes("unknown")) {
    return { status: "unknown", details };
  }
  return { status: "match", details };
}

function isTraitsActive() {
  const { dorsalSpines, dorsalSoft, analSoft } = state.traitInputs;
  return dorsalSpines !== null || dorsalSoft !== null || analSoft !== null;
}

function isSpeciesManuallyDismissed(sp) {
  return state.dismissedGenera.has(sp.genus) || state.dismissedSpecies.has(sp.scientific_name);
}

function isSpeciesRemaining(sp) {
  if (isSpeciesManuallyDismissed(sp)) return false;
  const evalRes = evaluateSpecies(sp);
  if (isTraitsActive() && state.hideMismatch && evalRes.status === "mismatch") {
    return false;
  }
  return true;
}

function dismissGenus(genus) {
  if (state.dismissedGenera.has(genus)) return;
  state.dismissedGenera.add(genus);
  state.undoStack.push({ type: "genus", genus });
  if (state.selectedGenus === genus) {
    state.viewMode = "genera";
    state.selectedGenus = null;
  }
  render();
}

function dismissSpecies(sci) {
  if (state.dismissedSpecies.has(sci)) return;
  state.dismissedSpecies.add(sci);
  state.undoStack.push({ type: "species", sci });
  render();
}

function undoLastDismiss() {
  const last = state.undoStack.pop();
  if (!last) return;
  if (last.type === "genus") {
    state.dismissedGenera.delete(last.genus);
  } else if (last.type === "species") {
    state.dismissedSpecies.delete(last.sci);
  }
  render();
}

function clearTraits() {
  els["input-dorsal-spines"].value = "";
  els["input-dorsal-soft"].value = "";
  els["input-anal-soft"].value = "";
  state.traitInputs = { dorsalSpines: null, dorsalSoft: null, analSoft: null };
  render();
}

function resetAll() {
  state.dismissedGenera.clear();
  state.dismissedSpecies.clear();
  state.undoStack = [];
  state.viewMode = "genera";
  state.selectedGenus = null;
  clearTraits();
}

function render() {
  if (!state.dataset) return;

  const allSpecies = state.dataset.species;
  const activeTraits = isTraitsActive();

  // Compute stats across non-manually-dismissed species
  let manualAliveCount = 0;
  let matchCount = 0;
  let unknownCount = 0;
  let mismatchCount = 0;
  const remainingSpecies = [];

  for (const sp of allSpecies) {
    const evalRes = evaluateSpecies(sp);
    if (!isSpeciesManuallyDismissed(sp)) {
      manualAliveCount += 1;
      if (evalRes.status === "match") matchCount += 1;
      else if (evalRes.status === "unknown") unknownCount += 1;
      else if (evalRes.status === "mismatch") mismatchCount += 1;
    }
    if (isSpeciesRemaining(sp)) {
      remainingSpecies.push({ sp, evalRes });
    }
  }

  const remainingGenera = new Set(remainingSpecies.map((x) => x.sp.genus));

  // Header & control bar counters
  els["remaining-count"].textContent = `残り ${remainingSpecies.length} / ${allSpecies.length} 種（${remainingGenera.size} / ${state.dataset.genera_count} 属）`;
  const manualDismissedTotal = allSpecies.length - manualAliveCount;
  els["dismissed-count"].textContent =
    manualDismissedTotal > 0 ? `手動✕除外: ${manualDismissedTotal}種` : "";

  els["undo-btn"].disabled = state.undoStack.length === 0;
  els["undo-btn"].textContent =
    state.undoStack.length > 0 ? `↺ 戻す (${state.undoStack.length})` : "↺ 戻す";

  // Trait summary pills
  if (activeTraits) {
    els["trait-counts-pills"].innerHTML = `
      <span class="pill pill-match">一致: ${matchCount}種</span>
      <span class="pill pill-unknown">不明（残す）: ${unknownCount}種</span>
      <span class="pill pill-mismatch">不一致: ${mismatchCount}種</span>
    `;
  } else {
    els["trait-counts-pills"].innerHTML =
      `<span class="pill pill-neutral">背鰭棘数・背鰭軟条数・臀鰭軟条数を入力すると範囲比較で絞り込めます</span>`;
  }

  // Tabs state
  els["tab-genera"].classList.toggle("active", state.viewMode !== "all_species");
  els["tab-all-species"].classList.toggle("active", state.viewMode === "all_species");
  els["tab-genera"].setAttribute("aria-selected", String(state.viewMode !== "all_species"));
  els["tab-all-species"].setAttribute("aria-selected", String(state.viewMode === "all_species"));

  // Breadcrumb visibility
  if (state.viewMode === "genus_species" && state.selectedGenus) {
    const genusMeta = state.dataset.genera.find((g) => g.genus === state.selectedGenus);
    const inGenusRem = remainingSpecies.filter((x) => x.sp.genus === state.selectedGenus).length;
    const inGenusTotal = genusMeta ? genusMeta.species_count : inGenusRem;
    els["genus-breadcrumb"].classList.remove("hidden");
    els["selected-genus-title"].textContent = `${genusMeta ? genusMeta.ja_name : ""} (${state.selectedGenus})`;
    els["selected-genus-sub"].textContent = `残り ${inGenusRem} / ${inGenusTotal} 種`;
  } else {
    els["genus-breadcrumb"].classList.add("hidden");
  }

  // Render Grid
  els["tile-grid"].innerHTML = "";
  let renderedCount = 0;

  if (state.viewMode === "genera") {
    renderedCount = renderGenusTiles(remainingSpecies, activeTraits);
  } else if (state.viewMode === "genus_species" && state.selectedGenus) {
    const list = remainingSpecies.filter((x) => x.sp.genus === state.selectedGenus);
    renderedCount = renderSpeciesTiles(list, activeTraits);
  } else {
    renderedCount = renderSpeciesTiles(remainingSpecies, activeTraits);
  }

  els["empty-state"].classList.toggle("hidden", renderedCount > 0);
}

function renderGenusTiles(remainingSpecies, activeTraits) {
  const byGenus = new Map();
  for (const item of remainingSpecies) {
    const g = item.sp.genus;
    if (!byGenus.has(g)) byGenus.set(g, []);
    byGenus.get(g).push(item);
  }

  let count = 0;
  const frag = document.createDocumentFragment();

  for (const gMeta of state.dataset.genera) {
    if (state.dismissedGenera.has(gMeta.genus)) continue;
    const remList = byGenus.get(gMeta.genus) || [];
    if (remList.length === 0) continue;

    count += 1;
    // Use the remaining species whose photo shows the fish best (largest/clearest).
    let repPhoto = null;
    for (const x of remList) {
      const ph = x.sp.photo;
      if (ph && (!repPhoto || (ph.score || 0) > (repPhoto.score || 0))) repPhoto = ph;
    }
    repPhoto = repPhoto || gMeta.photo;
    const examples = (gMeta.examples_ja || []).join("・");

    const matchCnt = remList.filter((x) => x.evalRes.status === "match").length;
    const unkCnt = remList.filter((x) => x.evalRes.status === "unknown").length;

    const card = document.createElement("article");
    card.className = "tile-card";
    card.tabIndex = 0;
    card.dataset.genus = gMeta.genus;

    card.innerHTML = `
      <div class="tile-thumb-wrap">
        ${buildThumbHtml(repPhoto, gMeta.ja_name)}
        <button type="button" class="tile-dismiss-btn" aria-label="${escapeHtml(gMeta.ja_name)} を候補から消す">✕</button>
        ${repPhoto ? `<span class="tile-lic-badge">${escapeHtml(repPhoto.license)}</span>` : ""}
      </div>
      <div class="tile-body">
        <h3 class="tile-ja">${escapeHtml(gMeta.ja_name)}</h3>
        <p class="tile-sci">${escapeHtml(gMeta.genus)}</p>
        ${examples ? `<p class="tile-examples">${escapeHtml(examples)}${gMeta.species_count > (gMeta.examples_ja || []).length ? " など" : ""}</p>` : ""}
        <div class="tile-meta-row">
          <span class="count-chip">残り ${remList.length} / ${gMeta.species_count} 種</span>
          ${
            activeTraits
              ? `<span class="meristic-line">一致${matchCnt}・不明${unkCnt}</span>`
              : `<span class="meristic-line">タップで種一覧 →</span>`
          }
        </div>
      </div>
    `;

    attachImgFallback(card);
    card.querySelector(".tile-dismiss-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      dismissGenus(gMeta.genus);
    });
    card.addEventListener("click", () => {
      state.viewMode = "genus_species";
      state.selectedGenus = gMeta.genus;
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        card.click();
      }
    });

    frag.appendChild(card);
  }

  els["tile-grid"].appendChild(frag);
  return count;
}

function renderSpeciesTiles(items, activeTraits) {
  const frag = document.createDocumentFragment();

  for (const { sp, evalRes } of items) {
    const card = document.createElement("article");
    card.className = "tile-card" + (evalRes.status === "mismatch" ? " is-mismatch" : "");
    card.tabIndex = 0;
    card.dataset.sci = sp.scientific_name;

    const dSpines = sp.traits.dorsal_spines.raw || "不明";
    const dSoft = sp.traits.dorsal_soft_rays.raw || "不明";
    const aSoft = sp.traits.anal_soft_rays.raw || "不明";
    const badgeHtml = activeTraits ? buildStatusBadge(evalRes.status) : "";

    card.innerHTML = `
      <div class="tile-thumb-wrap">
        ${buildThumbHtml(sp.photo, sp.ja_name || sp.scientific_name)}
        <button type="button" class="tile-dismiss-btn" aria-label="${escapeHtml(sp.ja_name || sp.scientific_name)} を候補から消す">✕</button>
        ${
          sp.photo
            ? `<span class="tile-lic-badge">${escapeHtml(sp.photo.context)}・${escapeHtml(sp.photo.license)}</span>`
            : ""
        }
      </div>
      <div class="tile-body">
        <div class="tile-title-row">
          <h3 class="tile-ja">${escapeHtml(sp.ja_name || "和名未設定")}</h3>
          ${badgeHtml}${regionBadge(sp)}
        </div>
        <p class="tile-sci">${escapeHtml(sp.scientific_name)}</p>
        <div class="tile-meta-row">
          <span class="meristic-line">D:${escapeHtml(dSpines)},${escapeHtml(dSoft)} / A軟:${escapeHtml(aSoft)}</span>
        </div>
      </div>
    `;

    attachImgFallback(card);
    card.querySelector(".tile-dismiss-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      dismissSpecies(sp.scientific_name);
    });
    card.addEventListener("click", () => {
      openDetailModal(sp.scientific_name);
    });
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openDetailModal(sp.scientific_name);
      }
    });

    frag.appendChild(card);
  }

  els["tile-grid"].appendChild(frag);
  return items.length;
}

function buildStatusBadge(status) {
  if (status === "match") return `<span class="status-badge match">一致</span>`;
  if (status === "unknown") return `<span class="status-badge unknown">不明</span>`;
  if (status === "mismatch") return `<span class="status-badge mismatch">不一致</span>`;
  return "";
}

function buildThumbHtml(photo, alt) {
  if (!photo || !photo.url) {
    return buildFallbackSvgHtml("CC写真なし");
  }
  const crop = Array.isArray(photo.crop) ? ` data-crop="${photo.crop.join(",")}"` : "";
  return `<img class="tile-thumb" src="${escapeHtml(photo.url)}" alt="${escapeHtml(alt)}" loading="lazy" referrerpolicy="no-referrer"${crop} />`;
}

// Zoom a tile image so the detected fish box fills the tile (no blank edges).
function applyCrop(img) {
  const c = (img.dataset.crop || "").split(",").map(Number);
  const wrap = img.parentElement;
  if (c.length !== 4 || !img.naturalWidth || !wrap) return;
  const W = wrap.clientWidth, H = wrap.clientHeight;
  const w = img.naturalWidth, h = img.naturalHeight;
  if (!W || !H) return;
  const pad = 0.06;
  const bx0 = Math.max(0, c[0] - pad) * w, bx1 = Math.min(1, c[2] + pad) * w;
  const by0 = Math.max(0, c[1] - pad) * h, by1 = Math.min(1, c[3] + pad) * h;
  const cover = Math.max(W / w, H / h);
  const k = Math.max(cover, Math.min(W / (bx1 - bx0), H / (by1 - by0), cover * 3));
  const left = Math.min(0, Math.max(W - w * k, W / 2 - ((bx0 + bx1) / 2) * k));
  const top = Math.min(0, Math.max(H - h * k, H / 2 - ((by0 + by1) / 2) * k));
  img.classList.add("is-cropped");
  Object.assign(img.style, { width: `${w * k}px`, height: `${h * k}px`, left: `${left}px`, top: `${top}px` });
}

window.addEventListener("resize", () => {
  document.querySelectorAll("img.tile-thumb[data-crop]").forEach(applyCrop);
});

function buildFallbackSvgHtml(caption) {
  return `
    <div class="tile-svg-fallback">
      <svg width="56" height="36" viewBox="0 0 64 40" aria-hidden="true">
        <path d="M12 20c8-11 22-15 35-9 5 2 8 5 11 9-3 4-6 7-11 9-13 6-27 2-35-9z" fill="#64748b"/>
        <path d="M14 20L4 11v18z" fill="#64748b"/>
        <circle cx="45" cy="17" r="2.2" fill="#f8fafc"/>
      </svg>
      <span>${escapeHtml(caption)}</span>
    </div>
  `;
}

function attachImgFallback(container) {
  const img = container.querySelector("img.tile-thumb");
  if (!img) return;
  if (img.dataset.crop) {
    if (img.complete && img.naturalWidth) requestAnimationFrame(() => applyCrop(img));
    else img.addEventListener("load", () => applyCrop(img));
  }
  img.addEventListener("error", () => {
    const wrap = img.parentElement;
    img.remove();
    wrap.insertAdjacentHTML("afterbegin", buildFallbackSvgHtml("画像読込不可"));
  });
}

function openDetailModal(sci) {
  const sp = state.speciesBySci.get(sci);
  if (!sp) return;
  state.activeModalSci = sci;

  els["detail-genus-badge"].textContent = `${sp.genus_ja} (${sp.genus})`;
  els["detail-ja-name"].textContent = sp.ja_name || "和名未設定";
  els["detail-sci-name"].textContent = (sp.en_name
    ? `${sp.scientific_name} — ${sp.en_name}`
    : sp.scientific_name) + (sp.region === "近海のみ" ? "（日本未記録・近海で記録あり）" : isDoubtful(sp) ? "（要確認: 日本産魚類全種目録に和名なし。FishBase の国別記録のみ）" : "");

  // Main photo & gallery
  const photos = sp.photos && sp.photos.length > 0 ? sp.photos : sp.photo ? [sp.photo] : [];
  renderModalPhoto(photos[0] || null, sp);

  els["detail-gallery"].innerHTML = "";
  if (photos.length > 1) {
    photos.forEach((ph, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "gallery-thumb-btn" + (idx === 0 ? " active" : "");
      btn.ariaLabel = `写真 ${idx + 1} (${ph.license})`;
      btn.innerHTML = `<img src="${escapeHtml(ph.url)}" alt="" loading="lazy" referrerpolicy="no-referrer" />`;
      btn.addEventListener("click", () => {
        els["detail-gallery"].querySelectorAll(".gallery-thumb-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        renderModalPhoto(ph, sp);
      });
      els["detail-gallery"].appendChild(btn);
    });
  }

  // Descriptions
  els["detail-color-pattern"].textContent = sp.color_pattern || "記載なし";
  els["detail-color-source"].textContent = sp.color_pattern_source ? `出典: ${sp.color_pattern_source}` : "";

  els["detail-field-marks"].innerHTML =
    sp.field_marks && sp.field_marks.length > 0
      ? sp.field_marks.map((m) => `<li>${escapeHtml(m)}</li>`).join("")
      : "<li>記載なし</li>";
  els["detail-marks-source"].textContent = sp.field_marks_source ? `出典: ${sp.field_marks_source}` : "";

  // Similar species clickable chips
  els["detail-similar-list"].innerHTML = "";
  if (sp.similar_species && sp.similar_species.length > 0) {
    for (const simSci of sp.similar_species) {
      const target = state.speciesBySci.get(simSci);
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "similar-chip";
      chip.textContent = target && target.ja_name ? `${target.ja_name} (${simSci})` : simSci;
      if (target) {
        chip.addEventListener("click", () => openDetailModal(simSci));
      } else {
        chip.disabled = true;
      }
      els["detail-similar-list"].appendChild(chip);
    }
  } else {
    els["detail-similar-list"].innerHTML = `<span class="meristic-line">なし</span>`;
  }
  els["detail-similar-source"].textContent = sp.similar_species_source ? `出典: ${sp.similar_species_source}` : "";

  // Evidence from open-access papers
  const ev = sp.evidence || [];
  els["detail-evidence-section"].hidden = ev.length === 0;
  els["detail-evidence-list"].innerHTML = ev
    .map((e) => {
      const href = e.doi ? `https://doi.org/${e.doi}` : e.url;
      const vs = e.vs && e.vs.length ? `<span class="evidence-vs">vs ${e.vs.map(escapeHtml).join(", ")}</span>` : "";
      const note = e.note ? `<div>${escapeHtml(e.note)}</div>` : "";
      return `<li><strong>${escapeHtml(e.trait_ja)}</strong>: ${escapeHtml(e.value)} ${vs}${note}
        <div class="source-note">出典: <a href="${escapeHtml(href)}" target="_blank" rel="noopener">${escapeHtml(e.cite || e.doi || "論文")}</a>${e.where ? `（${escapeHtml(e.where)}）` : ""}</div></li>`;
    })
    .join("");

  // Trait grid with ternary match highlights
  const evalRes = evaluateSpecies(sp);
  const t = sp.traits;
  const cells = [
    { label: "背鰭棘数", val: t.dorsal_spines.raw || "不明", status: evalRes.details.dorsalSpines },
    { label: "背鰭軟条数", val: t.dorsal_soft_rays.raw || "不明", status: evalRes.details.dorsalSoft },
    { label: "臀鰭棘数", val: t.anal_spines.raw || "不明", status: "none" },
    { label: "臀鰭軟条数", val: t.anal_soft_rays.raw || "不明", status: evalRes.details.analSoft },
    { label: "胸鰭条数", val: t.pectoral_rays.raw || "不明", status: "none" },
    { label: "側線鱗数", val: t.lateral_line_scales.raw || "不明", status: "none" },
    { label: "最大体長", val: t.max_length ? `${t.max_length} cm` : "不明", status: "none" },
    { label: "尾鰭の形", val: traitJa(t.caudal_fin) || "不明", status: "none" },
    { label: "体形", val: traitJa(t.body_shape) || "不明", status: "none" },
  ];

  els["detail-traits-grid"].innerHTML = cells
    .map(
      (c) => `
      <div class="trait-cell">
        <div class="trait-cell-label">${escapeHtml(c.label)}</div>
        <div class="trait-cell-val">
          <span>${escapeHtml(c.val)}</span>
          ${buildStatusBadge(c.status)}
        </div>
      </div>
    `
    )
    .join("");

  els["detail-modal"].classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function renderModalPhoto(photo, sp) {
  const img = els["detail-main-photo"];
  const fallback = els["detail-no-photo"];
  const credit = els["detail-photo-credit"];

  if (!photo || !photo.url) {
    img.src = "";
    img.classList.add("hidden");
    fallback.classList.remove("hidden");
    credit.textContent = "※ CC0 / CC-BY / CC-BY-NC ライセンスで掲載可能な写真がありません。";
    return;
  }

  fallback.classList.add("hidden");
  img.classList.remove("hidden");
  img.alt = sp.ja_name || sp.scientific_name;
  img.src = photo.url;
  img.onerror = () => {
    img.classList.add("hidden");
    fallback.classList.remove("hidden");
  };

  const parts = [
    `<span><strong>撮影者:</strong> ${escapeHtml(photo.author || "記載なし")}</span>`,
    `<span><strong>ライセンス:</strong> ${escapeHtml(photo.license)}</span>`,
    `<span><strong>出典:</strong> ${escapeHtml(photo.source)}</span>`,
  ];
  if (photo.context) parts.push(`<span><strong>状況:</strong> ${escapeHtml(photo.context)}</span>`);
  if (photo.life_stage && photo.life_stage !== "不明") {
    parts.push(`<span><strong>成長段階:</strong> ${escapeHtml(photo.life_stage)}</span>`);
  }
  if (photo.place) parts.push(`<span><strong>場所:</strong> ${escapeHtml(photo.place)}</span>`);
  if (photo.observed_on) parts.push(`<span><strong>撮影日:</strong> ${escapeHtml(photo.observed_on)}</span>`);
  credit.innerHTML = parts.join("");
}

function closeDetailModal() {
  state.activeModalSci = null;
  els["detail-modal"].classList.add("hidden");
  document.body.style.overflow = "";
}

// FishBase の英語の値を日本語にする（表にない値はそのまま出す）
const TRAIT_JA = {
  "elongated": "細長い",
  "eel-like": "ウナギ形",
  "fusiform / normal": "紡錘形（ふつう）",
  "short and / or deep": "体高が高い・寸詰まり",
  "more or less truncate": "ほぼ截形（まっすぐ）",
  "forked": "二叉",
  "pointed": "尖る",
  "rounded": "円い",
  "heterocercal": "異尾（上葉が長い）",
  "trilobed": "三叉",
};

function traitJa(val) {
  if (!val) return "";
  const key = String(val).toLowerCase();
  if (TRAIT_JA[key]) return TRAIT_JA[key];
  return key.startsWith("other") ? "その他" : val;
}

// 「日本産」でも目録に和名が無い種は、FishBase の国別記録だけが根拠なので要確認とする
function isDoubtful(sp) {
  return sp.region !== "近海のみ" && (!sp.ja_name || sp.ja_name === "和名なし");
}

function regionBadge(sp) {
  if (sp.region === "近海のみ") return `<span class="region-badge">日本未記録</span>`;
  return isDoubtful(sp) ? `<span class="region-badge">要確認</span>` : "";
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
