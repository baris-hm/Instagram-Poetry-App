"use strict";

let deferredInstallPrompt = null;

const installButtons = [...document.querySelectorAll("[data-install-app]")];
const installedBadges = [...document.querySelectorAll("[data-installed-badge]")];
const standaloneQuery = window.matchMedia("(display-mode: standalone)");

function isStandalone() {
  return standaloneQuery.matches || window.navigator.standalone === true;
}

function updateInstallUi() {
  const installed = isStandalone();
  installButtons.forEach((button) => {
    button.hidden = installed || deferredInstallPrompt === null;
  });
  installedBadges.forEach((badge) => {
    badge.hidden = !installed;
  });
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  updateInstallUi();
});

installButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    if (deferredInstallPrompt === null) {
      return;
    }
    button.disabled = true;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    button.disabled = false;
    updateInstallUi();
  });
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  updateInstallUi();
});

standaloneQuery.addEventListener?.("change", updateInstallUi);
updateInstallUi();

if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(() => {
      // The online application remains fully usable if registration is unavailable.
    });
  });
}
