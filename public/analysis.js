/* =========================================================
   LEXORA — Analysis page interactions
   Handles the mobile hamburger menu, the "Back" button, and
   a subtle entrance animation as sections scroll into view.
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  initMobileNav();
  initBackButton();
  initRevealOnScroll();
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

/* ---------------------------------------------------------
   Subtle entrance animation as sections scroll into view
   --------------------------------------------------------- */
function initRevealOnScroll() {
  const targets = document.querySelectorAll(
    ".overview, .problem, .objectives, .workflow, .categories, .tech, .features, .use-cases, .future, .highlights, .cta"
  );
  targets.forEach((el) => el.classList.add("reveal"));

  if (!("IntersectionObserver" in window)) {
    targets.forEach((el) => el.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  targets.forEach((el) => observer.observe(el));
}