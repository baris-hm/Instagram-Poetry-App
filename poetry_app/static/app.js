"use strict";

const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
const MAX_CAROUSEL_SLIDES = 10;
const MAX_BENT_SLIDES = 9;
const MAX_VERSES = 63;
const ALLOWED_PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const DRAFT_STORAGE_KEY = "poetry-carousel-draft-v1";

const state = {
  currentSlide: 0,
  description: "",
  hasPublished: false,
  instagramHandle: "@handle-",
  layout: "quatrain",
  bentMode: "automatic",
  maxLinesPerSlide: 4,
  photoUrl: "",
  previewImageUrls: [],
  previewRenderInProgress: false,
  previewRenderReady: false,
  publishInProgress: false,
  publishingEnabled: false,
  slides: [],
  title: "",
};

const elements = {
  backButton: document.querySelector("#back-to-editor"),
  captionPanel: document.querySelector("#caption-panel"),
  carousel: document.querySelector("#carousel"),
  carouselDots: document.querySelector("#carousel-dots"),
  carouselTrack: document.querySelector("#carousel-track"),
  composerView: document.querySelector("#composer-view"),
  createButton: document.querySelector("#create-preview"),
  description: document.querySelector("#description"),
  editorHelp: document.querySelector("#editor-help"),
  error: document.querySelector("#form-error"),
  form: document.querySelector("#poem-form"),
  bentCount: document.querySelector("#bent-count"),
  bentLayout: document.querySelector("#bent-layout"),
  bentModes: document.querySelector("#bent-modes"),
  bentModeButtons: [...document.querySelectorAll("[data-bent-mode]")],
  coupletCount: document.querySelector("#couplet-count"),
  coupletLayout: document.querySelector("#couplet-layout"),
  layoutStatus: document.querySelector("#layout-status"),
  lineEditorTitle: document.querySelector("#line-editor-title"),
  lineList: document.querySelector("#line-list"),
  nextButton: document.querySelector("#next-slide"),
  photo: document.querySelector("#photo"),
  photoIcon: document.querySelector("#photo-icon"),
  photoName: document.querySelector("#photo-name"),
  photoPreviewThumb: document.querySelector("#photo-preview-thumb"),
  photoSelection: document.querySelector("#photo-selection"),
  poem: document.querySelector("#poem"),
  poemCount: document.querySelector("#poem-count"),
  previewDescription: document.querySelector("#preview-description"),
  previewView: document.querySelector("#preview-view"),
  previousButton: document.querySelector("#previous-slide"),
  publishButton: document.querySelector("#publish-button"),
  publishNote: document.querySelector("#publish-note"),
  publishResult: document.querySelector("#publish-result"),
  quatrainCount: document.querySelector("#quatrain-count"),
  quatrainLayout: document.querySelector("#quatrain-layout"),
  removePhoto: document.querySelector("#remove-photo"),
  slideCounter: document.querySelector("#slide-counter"),
  slideLabel: document.querySelector("#current-slide-label"),
  title: document.querySelector("#title"),
};

let scrollTimer = 0;

function uniqueId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function makeSlide(lines) {
  return { id: uniqueId(), lines: [...lines] };
}

function showError(message) {
  elements.error.textContent = message;
  elements.error.hidden = !message;
  if (message) {
    elements.error.focus?.();
  }
}

function updatePoemCount() {
  elements.poemCount.textContent = `${elements.poem.value.length} karakter`;
}

function countPoemSlides(poem, linesPerSlide) {
  const normalized = poem.replace(/\r\n?/g, "\n").trim();
  if (!normalized) {
    return 0;
  }
  return normalized.split(/\n\s*\n+/).reduce((total, stanza) => {
    const lineCount = stanza.split("\n").filter((line) => line.trim()).length;
    return total + Math.ceil(lineCount / linesPerSlide);
  }, 0);
}

function countPoemLines(poem) {
  return poem.replace(/\r\n?/g, "\n").split("\n").filter((line) => line.trim()).length;
}

function totalSlidesFor(linesPerSlide) {
  return countPoemSlides(elements.poem.value, linesPerSlide) + (state.photoUrl ? 1 : 0);
}

function automaticBentSlideCount(verseCount) {
  return Math.min(verseCount, MAX_BENT_SLIDES);
}

function selectLayout(layout, bentMode = state.bentMode) {
  state.layout = layout;
  state.bentMode = String(bentMode || "automatic");
  elements.quatrainLayout.classList.toggle("is-selected", layout === "quatrain");
  elements.coupletLayout.classList.toggle("is-selected", layout === "couplet");
  elements.bentLayout.classList.toggle("is-selected", layout === "bent");
  elements.quatrainLayout.setAttribute("aria-pressed", String(layout === "quatrain"));
  elements.coupletLayout.setAttribute("aria-pressed", String(layout === "couplet"));
  elements.bentLayout.setAttribute("aria-pressed", String(layout === "bent"));
  elements.bentModes.hidden = layout !== "bent";
  elements.bentModeButtons.forEach((button) => {
    const selected = button.dataset.bentMode === state.bentMode;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function updateLayoutControls() {
  const hasPoem = Boolean(elements.poem.value.trim());
  const verseCount = countPoemLines(elements.poem.value);
  const quatrainTotal = totalSlidesFor(4);
  const coupletTotal = totalSlidesFor(2);
  const automaticBentTotal = automaticBentSlideCount(verseCount) + (state.photoUrl ? 1 : 0);
  const fixedBentSize = Number(state.bentMode);
  const selectedBentTotal = state.bentMode === "automatic"
    ? automaticBentTotal
    : Math.ceil(verseCount / fixedBentSize) + (state.photoUrl ? 1 : 0);
  elements.quatrainCount.textContent = hasPoem
    ? `${quatrainTotal} kare${state.photoUrl ? " · fotoğraf dahil" : ""}`
    : "Her karede 4 satır";
  elements.coupletCount.textContent = hasPoem
    ? `${coupletTotal} kare${state.photoUrl ? " · fotoğraf dahil" : ""}`
    : "Her karede 2 satır";
  elements.bentCount.textContent = hasPoem
    ? `${state.bentMode === "automatic" ? "Otomatik" : `${state.bentMode}'lik`}: ${selectedBentTotal} kare${state.photoUrl ? " · fotoğraf dahil" : ""}`
    : "9 kareye kadar dengeli dağılım";

  const coupletExceedsLimit = hasPoem && coupletTotal > MAX_CAROUSEL_SLIDES;
  const quatrainExceedsLimit = hasPoem
    && (verseCount >= 37 || quatrainTotal > MAX_CAROUSEL_SLIDES);
  const poemExceedsLimit = verseCount > MAX_VERSES;
  elements.quatrainLayout.disabled = quatrainExceedsLimit || poemExceedsLimit;
  elements.coupletLayout.disabled = coupletExceedsLimit || poemExceedsLimit;
  elements.bentLayout.disabled = poemExceedsLimit;
  elements.bentModeButtons.forEach((button) => {
    const mode = button.dataset.bentMode;
    const fixedSize = Number(mode);
    const exceedsModeLimit = mode !== "automatic" && verseCount > fixedSize * MAX_BENT_SLIDES;
    button.disabled = poemExceedsLimit || exceedsModeLimit;
    button.title = exceedsModeLimit
      ? `${mode}'lik düzen en fazla ${fixedSize * MAX_BENT_SLIDES} dize destekler.`
      : "";
  });

  const hasWarning = poemExceedsLimit
    || (state.layout === "couplet" && coupletExceedsLimit)
    || (state.layout === "quatrain" && quatrainExceedsLimit);
  elements.layoutStatus.classList.toggle("is-warning", hasWarning);
  if (poemExceedsLimit) {
    elements.layoutStatus.textContent = `Bu şiir ${verseCount} dize; önizleme en fazla 63 dize destekler.`;
  } else if (verseCount >= 37) {
    const bentDescription = state.bentMode === "automatic"
      ? "Otomatik düzen dizeleri 9 şiir karesine dengeli dağıtır; fazla dizeler son karelere eklenir."
      : `${state.bentMode}'lik düzen kareleri ${state.bentMode} dizeyle doldurur; son kare kalan dizeleri alır.`;
    elements.layoutStatus.textContent = state.layout === "bent"
      ? `${bentDescription} Dörtlük görünümü 37 dizeden itibaren kullanılamaz.`
      : "37 veya daha fazla dizede Bent görünümü kullanılır; Dörtlük görünümü kullanılamaz.";
  } else if (state.layout === "couplet" && coupletExceedsLimit) {
    elements.layoutStatus.textContent = `Beyit görünümü ${coupletTotal} kare oluşturur; 10 kare sınırını aştığı için kullanılamaz.`;
  } else if (state.layout === "quatrain" && quatrainExceedsLimit) {
    elements.layoutStatus.textContent = `Dörtlük görünümü ${quatrainTotal} kare oluşturur; 10 kare sınırını aştığı için kullanılamaz.`;
  } else if (state.layout === "bent") {
    elements.layoutStatus.textContent = state.bentMode === "automatic"
      ? "Otomatik düzen dizeleri en fazla 9 şiir karesine dengeli dağıtır; fazla dizeler son karelere eklenir."
      : `${state.bentMode}'lik düzen kareleri ${state.bentMode} dizeyle doldurur; son kare kalan dizeleri alır.`;
  } else {
    elements.layoutStatus.textContent = "Görünümü değiştirmek satır yerleşimini yeniden oluşturur. Fotoğraf dahil en fazla 10 kare hazırlanabilir.";
  }
}

function clearPhoto() {
  if (state.photoUrl) {
    URL.revokeObjectURL(state.photoUrl);
  }
  state.photoUrl = "";
  elements.photo.value = "";
  elements.photoPreviewThumb.removeAttribute("src");
  elements.photoPreviewThumb.hidden = true;
  elements.photoIcon.hidden = false;
  elements.photoName.textContent = "";
  elements.photoSelection.hidden = true;
  updateLayoutControls();
}

function handlePhotoSelection() {
  showError("");
  const file = elements.photo.files[0];
  if (!file) {
    clearPhoto();
    return;
  }
  if (!ALLOWED_PHOTO_TYPES.has(file.type)) {
    clearPhoto();
    showError("Lütfen JPG, PNG veya WebP biçiminde bir fotoğraf seçin.");
    return;
  }
  if (file.size > MAX_PHOTO_BYTES) {
    clearPhoto();
    showError("Fotoğraf 10 MB'den küçük olmalıdır.");
    return;
  }
  if (state.photoUrl) {
    URL.revokeObjectURL(state.photoUrl);
  }
  state.photoUrl = URL.createObjectURL(file);
  elements.photoPreviewThumb.src = state.photoUrl;
  elements.photoPreviewThumb.hidden = false;
  elements.photoIcon.hidden = true;
  elements.photoName.textContent = file.name;
  elements.photoSelection.hidden = false;
  updateLayoutControls();
}

function saveDraft() {
  const draft = {
    bentMode: state.bentMode,
    description: state.description,
    layout: state.layout,
    maxLinesPerSlide: state.maxLinesPerSlide,
    poem: elements.poem.value,
    slides: state.slides,
    title: state.title,
  };
  try {
    sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // Preview remains usable when browser storage is unavailable.
  }
}

function restoreDraft() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(DRAFT_STORAGE_KEY));
    if (!saved || !Array.isArray(saved.slides) || saved.slides.length === 0) {
      return false;
    }
    state.title = typeof saved.title === "string" ? saved.title : "";
    state.description = typeof saved.description === "string" ? saved.description : "";
    state.layout = ["couplet", "quatrain", "bent"].includes(saved.layout)
      ? saved.layout
      : (saved.linesPerSlide === 2 ? "couplet" : "quatrain");
    state.bentMode = ["automatic", "5", "6", "7"].includes(String(saved.bentMode))
      ? String(saved.bentMode)
      : "automatic";
    state.maxLinesPerSlide = state.layout === "bent" ? 7 : 4;
    state.slides = saved.slides.map((slide) => makeSlide(slide.lines ?? []));
    state.previewImageUrls = [];
    state.previewRenderReady = false;
    elements.title.value = state.title;
    elements.description.value = state.description;
    elements.poem.value = typeof saved.poem === "string" ? saved.poem : "";
    updatePoemCount();
    updateLayoutControls();
    selectLayout(state.layout, state.bentMode);
    return true;
  } catch {
    return false;
  }
}

async function createPreview(event) {
  event.preventDefault();
  showError("");

  const poem = elements.poem.value.trim();
  if (!poem) {
    showError("Önizleme için şiirinizi yapıştırın.");
    elements.poem.focus();
    return;
  }

  elements.createButton.disabled = true;
  elements.createButton.querySelector("span:first-child").textContent = "Hazırlanıyor…";

  try {
    const defaultLayout = countPoemLines(poem) >= 37 ? "bent" : "quatrain";
    const data = await requestPreview(defaultLayout, "automatic");
    applyPreviewData(data);
    await refreshRenderedPreview();
    state.currentSlide = 0;
    saveDraft();
    showPreview({ updateHistory: true });
  } catch (error) {
    showError(error.message || "Önizleme oluşturulamadı. Lütfen tekrar deneyin.");
  } finally {
    elements.createButton.disabled = false;
    elements.createButton.querySelector("span:first-child").textContent = "Önizleme oluştur";
  }
}

async function requestPreview(layout, bentMode = "automatic") {
  const response = await fetch("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      poem: elements.poem.value.trim(),
      title: elements.title.value,
      description: elements.description.value,
      has_photo: Boolean(state.photoUrl),
      layout,
      bent_mode: bentMode,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Önizleme oluşturulamadı.");
  }
  return data;
}

async function requestRenderedPreview() {
  const photoDataUrl = await selectedPhotoAsDataUrl();
  const response = await fetch("/api/render-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      description: state.description,
      photo_data_url: photoDataUrl,
      slides: state.slides.map((slide) => slide.lines),
      title: state.title,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Kare önizlemeleri oluşturulamadı.");
  }
  if (!Array.isArray(data.preview_urls) || data.preview_urls.length !== visibleSlideCount()) {
    throw new Error("Kare önizlemeleri eksik oluşturuldu.");
  }
  return data.preview_urls;
}

async function refreshRenderedPreview() {
  state.previewRenderInProgress = true;
  state.previewRenderReady = false;
  state.previewImageUrls = [];
  updatePublishAvailability();
  if (!elements.previewView.hidden) {
    renderPreview();
  }

  try {
    state.previewImageUrls = await requestRenderedPreview();
    state.previewRenderReady = true;
  } finally {
    state.previewRenderInProgress = false;
    updatePublishAvailability();
  }
}

function applyPreviewData(data) {
  state.title = data.title;
  state.description = data.description;
  state.layout = data.layout;
  state.bentMode = data.bent_mode || state.bentMode || "automatic";
  state.maxLinesPerSlide = data.max_lines_per_slide;
  state.slides = data.slides.map(makeSlide);
  state.previewImageUrls = [];
  state.previewRenderReady = false;
  state.hasPublished = false;
  selectLayout(state.layout, state.bentMode);
  updatePublishAvailability();
}

async function applyLayout(layout, bentMode = state.bentMode) {
  if (state.previewRenderInProgress) {
    return;
  }
  const normalizedBentMode = String(bentMode || "automatic");
  if (layout === state.layout && (layout !== "bent" || normalizedBentMode === state.bentMode)) {
    return;
  }
  const selectedControl = layout === "quatrain"
    ? elements.quatrainLayout
    : (layout === "couplet" ? elements.coupletLayout : elements.bentLayout);
  const selectedBentControl = elements.bentModeButtons.find(
    (button) => button.dataset.bentMode === normalizedBentMode,
  );
  if (selectedControl.disabled || (layout === "bent" && selectedBentControl?.disabled)) {
    return;
  }

  const previousState = {
    bentMode: state.bentMode,
    currentSlide: state.currentSlide,
    hasPublished: state.hasPublished,
    layout: state.layout,
    maxLinesPerSlide: state.maxLinesPerSlide,
    previewImageUrls: [...state.previewImageUrls],
    previewRenderReady: state.previewRenderReady,
    slides: state.slides,
  };

  elements.quatrainLayout.disabled = true;
  elements.coupletLayout.disabled = true;
  elements.bentLayout.disabled = true;
  elements.bentModeButtons.forEach((button) => { button.disabled = true; });
  elements.layoutStatus.classList.remove("is-warning");
  elements.layoutStatus.textContent = "Görünüm hazırlanıyor…";
  let failureMessage = "";

  try {
    const data = await requestPreview(layout, normalizedBentMode);
    applyPreviewData(data);
    await refreshRenderedPreview();
    state.currentSlide = 0;
    saveDraft();
    renderPreview();
  } catch (error) {
    state.bentMode = previousState.bentMode;
    state.currentSlide = previousState.currentSlide;
    state.hasPublished = previousState.hasPublished;
    state.layout = previousState.layout;
    state.maxLinesPerSlide = previousState.maxLinesPerSlide;
    state.previewImageUrls = previousState.previewImageUrls;
    state.previewRenderReady = previousState.previewRenderReady;
    state.slides = previousState.slides;
    selectLayout(state.layout, state.bentMode);
    renderPreview();
    failureMessage = error.message || "Görünüm değiştirilemedi.";
  } finally {
    updateLayoutControls();
    if (failureMessage) {
      elements.layoutStatus.classList.add("is-warning");
      elements.layoutStatus.textContent = failureMessage;
    }
  }
}

function showPreview({ updateHistory = false } = {}) {
  if (state.slides.length === 0) {
    return;
  }
  elements.composerView.hidden = true;
  elements.previewView.hidden = false;
  if (updateHistory && window.location.pathname !== "/preview") {
    history.pushState({ view: "preview" }, "", "/preview");
  }
  updateLayoutControls();
  selectLayout(state.layout, state.bentMode);
  renderPreview();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showComposer({ updateHistory = false } = {}) {
  elements.previewView.hidden = true;
  elements.composerView.hidden = false;
  if (updateHistory && window.location.pathname !== "/") {
    history.pushState({ view: "composer" }, "", "/");
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderPreview() {
  state.currentSlide = Math.min(state.currentSlide, visibleSlideCount() - 1);
  renderCarousel();
  renderLineEditor();
  renderCaption();
  updateNavigation();
}

function visibleSlideCount() {
  return state.slides.length + (state.photoUrl ? 1 : 0);
}

function renderCarousel() {
  elements.carouselTrack.replaceChildren();
  elements.carouselDots.replaceChildren();

  const total = visibleSlideCount();

  state.slides.forEach((slide, poemIndex) => {
    const visibleIndex = poemIndex;
    const card = document.createElement("article");
    card.className = "slide-card rendered-slide";
    card.dataset.slideId = slide.id;
    card.setAttribute("aria-label", `Kare ${visibleIndex + 1}, toplam ${total}`);
    appendRenderedSlide(
      card,
      visibleIndex,
      `Instagram'da yayınlanacak ${visibleIndex + 1}. şiir karesi`,
    );
    elements.carouselTrack.append(card);
    appendCarouselDot(visibleIndex, total);
  });

  if (state.photoUrl) {
    const visibleIndex = state.slides.length;
    const photoCard = document.createElement("article");
    photoCard.className = "slide-card photo-slide rendered-slide";
    photoCard.setAttribute(
      "aria-label",
      `Düzenlenmemiş fotoğraf, son kare ${visibleIndex + 1}, toplam ${total}`,
    );

    appendRenderedSlide(
      photoCard,
      visibleIndex,
      "Instagram'da yayınlanacak düzenlenmemiş fotoğraf karesi",
    );
    elements.carouselTrack.append(photoCard);
    appendCarouselDot(visibleIndex, total);
  }

  requestAnimationFrame(() => {
    elements.carouselTrack.scrollLeft = state.currentSlide * elements.carouselTrack.clientWidth;
  });
}

function appendRenderedSlide(card, index, alt) {
  const imageUrl = state.previewImageUrls[index];
  if (imageUrl) {
    const image = document.createElement("img");
    image.className = "rendered-slide-image";
    image.src = imageUrl;
    image.alt = alt;
    card.append(image);
    return;
  }

  const placeholder = document.createElement("div");
  placeholder.className = "rendered-slide-placeholder";
  placeholder.textContent = state.previewRenderInProgress
    ? "Kare hazırlanıyor…"
    : "Kare önizlemesi hazırlanamadı.";
  card.append(placeholder);
}

function appendCarouselDot(index, total) {
  const dot = document.createElement("button");
  dot.className = `carousel-dot${index === state.currentSlide ? " is-active" : ""}`;
  dot.type = "button";
  dot.setAttribute("aria-label", `${index + 1}. kareye git, toplam ${total}`);
  dot.setAttribute("aria-current", index === state.currentSlide ? "true" : "false");
  dot.addEventListener("click", () => goToSlide(index));
  elements.carouselDots.append(dot);
}

function renderLineEditor() {
  elements.lineList.replaceChildren();
  elements.slideLabel.textContent = `Kare ${state.currentSlide + 1}`;
  const capacityLabel = state.maxLinesPerSlide === 7 ? "yedi" : "dört";
  elements.editorHelp.textContent = `Sırayı korumak için yalnızca ilk ve son satır taşınabilir. Bu görünümde her kare en fazla ${capacityLabel} satır alır.`;

  const poemSlideIndex = state.currentSlide;
  if (poemSlideIndex >= state.slides.length) {
    elements.lineEditorTitle.textContent = "Fotoğraf karesi";
    const note = document.createElement("div");
    note.className = "photo-editor-note";
    note.textContent = "Bu fotoğraf son karede, kırpılmadan ve üzerine yazı eklenmeden kullanılacak.";
    elements.lineList.append(note);
    return;
  }

  elements.lineEditorTitle.textContent = "Bu karedeki satırlar";
  const slide = state.slides[poemSlideIndex];

  slide.lines.forEach((line, lineIndex) => {
    const row = document.createElement("div");
    row.className = "line-row";

    const text = document.createElement("div");
    text.className = "line-text";
    text.textContent = line;

    row.append(text);

    const isFirstLine = lineIndex === 0;
    const isLastLine = lineIndex === slide.lines.length - 1;
    if (isFirstLine || isLastLine) {
      const actions = document.createElement("div");
      actions.className = "line-actions";
      actions.classList.toggle("has-two-actions", isFirstLine && isLastLine);

      if (isFirstLine) {
        const previous = makeMoveButton(
          "← Önceki kare",
          poemSlideIndex,
          lineIndex,
          -1,
        );
        const previousSlide = state.slides[poemSlideIndex - 1];
        previous.disabled = state.previewRenderInProgress
          || !previousSlide
          || previousSlide.lines.length >= state.maxLinesPerSlide;
        if (previous.disabled) {
          if (state.previewRenderInProgress) {
            previous.title = "Kare önizlemesi hazırlanıyor.";
          } else {
            previous.title = previousSlide
              ? `Önceki kare en fazla ${state.maxLinesPerSlide} satır alabilir.`
              : "Önceki şiir karesi yok.";
          }
        }
        actions.append(previous);
      }

      if (isLastLine) {
        const next = makeMoveButton(
          "Sonraki kare →",
          poemSlideIndex,
          lineIndex,
          1,
        );
        const nextSlide = state.slides[poemSlideIndex + 1];
        const movingWouldHaveNoEffect = !nextSlide && slide.lines.length === 1;
        const movingWouldExceedSlideLimit = !nextSlide
          && visibleSlideCount() >= MAX_CAROUSEL_SLIDES;
        next.disabled = state.previewRenderInProgress
          || movingWouldHaveNoEffect
          || movingWouldExceedSlideLimit
          || Boolean(nextSlide && nextSlide.lines.length >= state.maxLinesPerSlide);
        if (next.disabled) {
          if (state.previewRenderInProgress) {
            next.title = "Kare önizlemesi hazırlanıyor.";
          } else if (movingWouldHaveNoEffect) {
            next.title = "Taşınacak başka bir şiir karesi yok.";
          } else if (movingWouldExceedSlideLimit) {
            next.title = "Fotoğraf dahil en fazla 10 kare hazırlanabilir.";
          } else {
            next.title = `Sonraki kare en fazla ${state.maxLinesPerSlide} satır alabilir.`;
          }
        }
        actions.append(next);
      }

      row.append(actions);
    }
    elements.lineList.append(row);
  });
}

function makeMoveButton(label, poemSlideIndex, lineIndex, direction) {
  const button = document.createElement("button");
  button.className = "move-button";
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", () => moveLine(poemSlideIndex, lineIndex, direction));
  return button;
}

async function moveLine(sourceIndex, lineIndex, direction) {
  if (state.previewRenderInProgress) {
    return;
  }
  const source = state.slides[sourceIndex];
  const isAllowedBoundary = direction < 0
    ? lineIndex === 0
    : lineIndex === source.lines.length - 1;
  const existingTarget = state.slides[sourceIndex + direction];
  if (
    !isAllowedBoundary
    || (direction < 0 && !existingTarget)
    || (existingTarget && existingTarget.lines.length >= state.maxLinesPerSlide)
    || (direction > 0 && !existingTarget && source.lines.length === 1)
    || (direction > 0 && !existingTarget && visibleSlideCount() >= MAX_CAROUSEL_SLIDES)
  ) {
    return;
  }

  const previousSlides = state.slides.map((slide) => ({
    id: slide.id,
    lines: [...slide.lines],
  }));
  const previousImageUrls = [...state.previewImageUrls];
  const previousRenderReady = state.previewRenderReady;
  const previousCurrentSlide = state.currentSlide;
  const previousHasPublished = state.hasPublished;

  const [line] = source.lines.splice(lineIndex, 1);
  let targetIndex = sourceIndex + direction;

  if (direction > 0 && targetIndex === state.slides.length) {
    state.slides.push(makeSlide([]));
  }

  const target = state.slides[targetIndex];
  if (direction < 0) {
    target.lines.push(line);
  } else {
    target.lines.unshift(line);
  }

  if (source.lines.length === 0) {
    state.slides.splice(sourceIndex, 1);
    if (sourceIndex < targetIndex) {
      targetIndex -= 1;
    }
  }

  state.currentSlide = targetIndex;
  state.hasPublished = false;
  renderPreview();
  elements.layoutStatus.classList.remove("is-warning");
  elements.layoutStatus.textContent = "Kare önizlemesi hazırlanıyor…";

  try {
    await refreshRenderedPreview();
    saveDraft();
    renderPreview();
    updateLayoutControls();
  } catch (error) {
    state.slides = previousSlides;
    state.previewImageUrls = previousImageUrls;
    state.previewRenderReady = previousRenderReady;
    state.currentSlide = previousCurrentSlide;
    state.hasPublished = previousHasPublished;
    renderPreview();
    elements.layoutStatus.classList.add("is-warning");
    elements.layoutStatus.textContent = error.message || "Kare önizlemesi güncellenemedi.";
    updatePublishAvailability();
  }
}

function renderCaption() {
  elements.captionPanel.hidden = !state.description;
  elements.previewDescription.textContent = state.description;
}

function updateNavigation() {
  const current = state.currentSlide;
  const total = visibleSlideCount();
  elements.previousButton.disabled = current === 0;
  elements.nextButton.disabled = current === total - 1;
  elements.slideCounter.textContent = `${current + 1} / ${total}`;
  [...elements.carouselDots.children].forEach((dot, index) => {
    const active = index === current;
    dot.classList.toggle("is-active", active);
    dot.setAttribute("aria-current", active ? "true" : "false");
  });
}

function goToSlide(index) {
  if (index < 0 || index >= visibleSlideCount()) {
    return;
  }
  state.currentSlide = index;
  elements.carouselTrack.scrollTo({
    left: index * elements.carouselTrack.clientWidth,
    behavior: "smooth",
  });
  renderLineEditor();
  updateNavigation();
}

function handleCarouselScroll() {
  clearTimeout(scrollTimer);
  scrollTimer = window.setTimeout(() => {
    const width = elements.carouselTrack.clientWidth;
    if (!width) {
      return;
    }
    const index = Math.round(elements.carouselTrack.scrollLeft / width);
    if (index !== state.currentSlide && index >= 0 && index < visibleSlideCount()) {
      state.currentSlide = index;
      renderLineEditor();
      updateNavigation();
    }
  }, 80);
}

function handleCarouselKeydown(event) {
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    goToSlide(state.currentSlide - 1);
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    goToSlide(state.currentSlide + 1);
  }
}

async function loadPublishingConfig() {
  try {
    const response = await fetch("/api/config");
    const config = await response.json();
    state.publishingEnabled = Boolean(config.publishing_enabled);
    state.instagramHandle = config.instagram_handle || "@handle-";
    elements.publishNote.textContent = config.message || "Instagram yayın ayarları eksik.";
    if (!elements.previewView.hidden && state.slides.length > 0) {
      renderCarousel();
      updateNavigation();
    }
  } catch {
    state.publishingEnabled = false;
    elements.publishNote.textContent = "Instagram yayın ayarları okunamadı.";
  }
  updatePublishAvailability();
}

function updatePublishAvailability() {
  elements.publishButton.disabled = !state.publishingEnabled
    || state.slides.length === 0
    || !state.previewRenderReady
    || state.previewRenderInProgress
    || state.publishInProgress
    || state.hasPublished;
}

function selectedPhotoAsDataUrl() {
  const file = elements.photo.files[0];
  if (!file) {
    return Promise.resolve("");
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")), { once: true });
    reader.addEventListener("error", () => reject(new Error("Fotoğraf okunamadı.")), { once: true });
    reader.readAsDataURL(file);
  });
}

function showPublishResult(message, { error = false, permalink = "" } = {}) {
  elements.publishResult.replaceChildren();
  elements.publishResult.hidden = false;
  elements.publishResult.classList.toggle("is-error", error);
  elements.publishResult.append(document.createTextNode(message));
  if (permalink.startsWith("https://")) {
    elements.publishResult.append(document.createTextNode(" "));
    const link = document.createElement("a");
    link.href = permalink;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Gönderiyi aç";
    elements.publishResult.append(link);
  }
}

async function publishPost() {
  if (
    !state.publishingEnabled
    || !state.previewRenderReady
    || state.previewRenderInProgress
    || state.publishInProgress
    || state.hasPublished
  ) {
    return;
  }
  const total = visibleSlideCount();
  const confirmed = window.confirm(
    `${total} kare şimdi Instagram'da yayınlanacak. Devam edilsin mi?`,
  );
  if (!confirmed) {
    return;
  }

  state.publishInProgress = true;
  elements.publishButton.textContent = "Instagram'a gönderiliyor…";
  elements.publishResult.hidden = true;
  updatePublishAvailability();

  try {
    const photoDataUrl = await selectedPhotoAsDataUrl();
    const response = await fetch("/api/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        description: state.description,
        photo_data_url: photoDataUrl,
        slides: state.slides.map((slide) => slide.lines),
        title: state.title,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Gönderi yayınlanamadı.");
    }
    state.hasPublished = true;
    elements.publishButton.textContent = "Instagram'da yayınlandı";
    showPublishResult(result.message || "Gönderi Instagram'da yayınlandı.", {
      permalink: result.permalink || "",
    });
  } catch (error) {
    elements.publishButton.textContent = "Instagram'da yayınla";
    showPublishResult(error.message || "Gönderi yayınlanamadı.", { error: true });
  } finally {
    state.publishInProgress = false;
    updatePublishAvailability();
  }
}

elements.form.addEventListener("submit", createPreview);
elements.poem.addEventListener("input", () => {
  updatePoemCount();
  updateLayoutControls();
});
elements.quatrainLayout.addEventListener("click", () => applyLayout("quatrain"));
elements.coupletLayout.addEventListener("click", () => applyLayout("couplet"));
elements.bentLayout.addEventListener("click", () => applyLayout("bent", state.bentMode));
elements.bentModeButtons.forEach((button) => {
  button.addEventListener("click", () => applyLayout("bent", button.dataset.bentMode));
});
elements.publishButton.addEventListener("click", publishPost);
elements.photo.addEventListener("change", handlePhotoSelection);
elements.removePhoto.addEventListener("click", clearPhoto);
elements.backButton.addEventListener("click", () => showComposer({ updateHistory: true }));
elements.previousButton.addEventListener("click", () => goToSlide(state.currentSlide - 1));
elements.nextButton.addEventListener("click", () => goToSlide(state.currentSlide + 1));
elements.carouselTrack.addEventListener("scroll", handleCarouselScroll, { passive: true });
elements.carousel.addEventListener("keydown", handleCarouselKeydown);

window.addEventListener("popstate", () => {
  if (window.location.pathname === "/preview" && state.slides.length > 0) {
    showPreview();
  } else {
    showComposer();
  }
});

updatePoemCount();
updateLayoutControls();
loadPublishingConfig();
if (window.location.pathname === "/preview" && restoreDraft()) {
  showPreview();
  refreshRenderedPreview()
    .then(() => {
      renderPreview();
      updateLayoutControls();
    })
    .catch((error) => {
      renderPreview();
      elements.layoutStatus.classList.add("is-warning");
      elements.layoutStatus.textContent = error.message || "Kare önizlemeleri oluşturulamadı.";
    });
}
