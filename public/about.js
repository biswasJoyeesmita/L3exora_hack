/* =========================================================
   LEXORA — About Us page interactions
   Only two small behaviors live here: the mobile hamburger
   menu, and the "Back" button using browser history.
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  initMobileNav();
  initBackButton();
});

/* ---------------------------------------------------------
   Mobile navigation (hamburger menu)
   --------------------------------------------------------- */
function initMobileNav() {
  const toggle = document.getElementById("navToggle");
  const nav = document.getElementById("primaryNav");

  if (!toggle || !nav) return;

  toggle.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });

  nav.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    });
  });
}

/* ---------------------------------------------------------
   Back button — returns to the previous page in history
   --------------------------------------------------------- */
function initBackButton() {
  const backBtn = document.getElementById("backBtn");
  if (!backBtn) return;

  backBtn.addEventListener("click", () => {
    window.history.back();
  });
}