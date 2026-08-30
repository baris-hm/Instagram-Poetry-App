"use strict";

const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
const MAX_CAROUSEL_SLIDES = 10;
const ALLOWED_PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const DRAFT_STORAGE_KEY = "poetry-carousel-draft-v1";
const INSTAGRAM_HANDLE = "@aeminatasoy";

const state = {
  currentSlide: 0,
  description: "",
  linesPerSlide: 4,
  maxLinesPerSlide: 4,
  photoUrl: "",
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
  error: document.querySelector("#form-error"),
  form: document.querySelector("#poem-form"),
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

function totalSlidesFor(linesPerSlide) {
  return countPoemSlides(elements.poem.value, linesPerSlide) + (state.photoUrl ? 1 : 0);
}

function selectLayout(linesPerSlide) {
  if (linesPerSlide === 2 && elements.coupletLayout.disabled) {
    return;
  }
  state.linesPerSlide = linesPerSlide;
  elements.quatrainLayout.classList.toggle("is-selected", linesPerSlide === 4);
  elements.coupletLayout.classList.toggle("is-selected", linesPerSlide === 2);
  elements.quatrainLayout.setAttribute("aria-pressed", String(linesPerSlide === 4));
  elements.coupletLayout.setAttribute("aria-pressed", String(linesPerSlide === 2));
}

function updateLayoutControls() {
  const hasPoem = Boolean(elements.poem.value.trim());
  const quatrainTotal = totalSlidesFor(4);
  const coupletTotal = totalSlidesFor(2);
  elements.quatrainCount.textContent = hasPoem
    ? `${quatrainTotal} kare${state.photoUrl ? " · fotoğraf dahil" : ""}`
    : "Her karede 4 satır";
  elements.coupletCount.textContent = hasPoem
    ? `${coupletTotal} kare${state.photoUrl ? " · fotoğraf dahil" : ""}`
    : "Her karede 2 satır";

  const coupletExceedsLimit = hasPoem && coupletTotal > MAX_CAROUSEL_SLIDES;
  elements.coupletLayout.disabled = coupletExceedsLimit;

  elements.layoutStatus.classList.toggle("is-warning", coupletExceedsLimit);
  elements.layoutStatus.textContent = coupletExceedsLimit
    ? `Beyit görünümü ${coupletTotal} kare oluşturur; 10 kare sınırını aştığı için kullanılamaz.`
    : "Görünümü değiştirmek satır yerleşimini yeniden oluşturur. Fotoğraf dahil en fazla 10 kare hazırlanabilir.";
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
    description: state.description,
    linesPerSlide: state.linesPerSlide,
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
    state.linesPerSlide = saved.linesPerSlide === 2 ? 2 : 4;
    state.maxLinesPerSlide = 4;
    state.slides = saved.slides.map((slide) => makeSlide(slide.lines ?? []));
    elements.title.value = state.title;
    elements.description.value = state.description;
    elements.poem.value = typeof saved.poem === "string" ? saved.poem : "";
    updatePoemCount();
    updateLayoutControls();
    selectLayout(state.linesPerSlide);
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
    const data = await requestPreview(4);
    applyPreviewData(data);
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

async function requestPreview(linesPerSlide) {
  const response = await fetch("/api/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      poem: elements.poem.value.trim(),
      title: elements.title.value,
      description: elements.description.value,
      has_photo: Boolean(state.photoUrl),
      lines_per_slide: linesPerSlide,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Önizleme oluşturulamadı.");
  }
  return data;
}

function applyPreviewData(data) {
  state.title = data.title;
  state.description = data.description;
  state.linesPerSlide = data.lines_per_slide;
  state.maxLinesPerSlide = data.max_lines_per_slide;
  state.slides = data.slides.map(makeSlide);
  selectLayout(state.linesPerSlide);
}

async function applyLayout(linesPerSlide) {
  if (linesPerSlide === state.linesPerSlide) {
    return;
  }
  if (linesPerSlide === 2 && elements.coupletLayout.disabled) {
    return;
  }

  elements.quatrainLayout.disabled = true;
  elements.coupletLayout.disabled = true;
  elements.layoutStatus.classList.remove("is-warning");
  elements.layoutStatus.textContent = "Görünüm hazırlanıyor…";
  let failureMessage = "";

  try {
    const data = await requestPreview(linesPerSlide);
    applyPreviewData(data);
    state.currentSlide = 0;
    saveDraft();
    renderPreview();
  } catch (error) {
    failureMessage = error.message || "Görünüm değiştirilemedi.";
  } finally {
    elements.quatrainLayout.disabled = false;
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
  selectLayout(state.linesPerSlide);
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
    card.className = `slide-card${state.photoUrl ? " has-photo" : ""}`;
    card.dataset.slideId = slide.id;
    card.setAttribute("aria-label", `Kare ${visibleIndex + 1}, toplam ${total}`);
    if (state.photoUrl) {
      card.style.backgroundImage = `url("${state.photoUrl}")`;
    }

    const content = document.createElement("div");
    content.className = "slide-content";
    if (poemIndex === 0 && state.title) {
      const title = document.createElement("h2");
      title.className = "slide-title";
      title.textContent = state.title;
      content.append(title);
    }

    const poem = document.createElement("div");
    poem.className = "slide-poem";
    slide.lines.forEach((line) => {
      const text = document.createElement("div");
      text.textContent = line;
      poem.append(text);
    });
    content.append(poem);

    const handle = document.createElement("span");
    handle.className = "slide-handle";
    handle.textContent = INSTAGRAM_HANDLE;

    const number = document.createElement("span");
    number.className = "slide-number";
    number.textContent = `${String(visibleIndex + 1).padStart(2, "0")} / ${String(total).padStart(2, "0")}`;
    card.append(content, handle, number);
    elements.carouselTrack.append(card);
    appendCarouselDot(visibleIndex, total);
  });

  if (state.photoUrl) {
    const visibleIndex = state.slides.length;
    const photoCard = document.createElement("article");
    photoCard.className = "slide-card photo-slide";
    photoCard.setAttribute(
      "aria-label",
      `Düzenlenmemiş fotoğraf, son kare ${visibleIndex + 1}, toplam ${total}`,
    );

    const photo = document.createElement("img");
    photo.className = "photo-slide-image";
    photo.src = state.photoUrl;
    photo.alt = "Seçilen fotoğrafın düzenlenmemiş önizlemesi";
    photoCard.append(photo);
    elements.carouselTrack.append(photoCard);
    appendCarouselDot(visibleIndex, total);
  }

  requestAnimationFrame(() => {
    elements.carouselTrack.scrollLeft = state.currentSlide * elements.carouselTrack.clientWidth;
  });
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
        previous.disabled = !previousSlide || previousSlide.lines.length >= state.maxLinesPerSlide;
        if (previous.disabled) {
          previous.title = previousSlide
            ? `Önceki kare en fazla ${state.maxLinesPerSlide} satır alabilir.`
            : "Önceki şiir karesi yok.";
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
        next.disabled = movingWouldHaveNoEffect
          || Boolean(nextSlide && nextSlide.lines.length >= state.maxLinesPerSlide);
        if (next.disabled) {
          next.title = movingWouldHaveNoEffect
            ? "Taşınacak başka bir şiir karesi yok."
            : `Sonraki kare en fazla ${state.maxLinesPerSlide} satır alabilir.`;
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

function moveLine(sourceIndex, lineIndex, direction) {
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
  ) {
    return;
  }

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
  saveDraft();
  renderPreview();
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

elements.form.addEventListener("submit", createPreview);
elements.poem.addEventListener("input", () => {
  updatePoemCount();
  updateLayoutControls();
});
elements.quatrainLayout.addEventListener("click", () => applyLayout(4));
elements.coupletLayout.addEventListener("click", () => applyLayout(2));
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
if (window.location.pathname === "/preview" && restoreDraft()) {
  showPreview();
}
