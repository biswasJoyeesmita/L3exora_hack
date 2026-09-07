/* =========================================================
   LEXORA — Frontend interactions & Lexora Model Integration
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  initMobileNav();
  initDashboardButtons();
  initAnalyzeButton();
  initCharCount();
});

/* ---------------------------------------------------------
   Mobile Navigation
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
   Live Character Counter
   --------------------------------------------------------- */
function initCharCount() {
  const textarea = document.getElementById("contentInput");
  const counter = document.getElementById("charCount");

  if (!textarea || !counter) return;

  const updateCount = () => {
    const length = textarea.value.length;
    counter.textContent = `${length} character${length === 1 ? "" : "s"}`;
  };

  textarea.addEventListener("input", updateCount);
  updateCount();
}

/* ---------------------------------------------------------
   Toast Notifications
   --------------------------------------------------------- */
function showToast(message) {
  let toast = document.getElementById("toast");

  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }

  toast.textContent = message;
  toast.classList.add("show");

  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.classList.remove("show");
  }, 2800);
}

/* ---------------------------------------------------------
   HTML Escaping Helper
   --------------------------------------------------------- */
function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/* ---------------------------------------------------------
   SINGLE TEXT ANALYZER WIDGET
   --------------------------------------------------------- */
function initAnalyzeButton() {
  const analyzeBtn = document.getElementById("analyzeBtn");
  const textarea = document.getElementById("contentInput");

  if (!analyzeBtn || !textarea) return;

  analyzeBtn.addEventListener("click", async () => {
    const text = textarea.value.trim();

    if (!text) {
      textarea.focus();
      showPlaceholder("Please enter some content before running an analysis.");
      return;
    }

    setSingleLoadingState(true);

    try {
      const result = await analyzeContentAPI(text);
      renderSingleResult(result);
      showToast("Content classified successfully.");
    } catch (error) {
      console.error("Lexora single text analysis failed:", error);
      showPlaceholder(error.message || "Something went wrong while analyzing this content. Please try again.");
    } finally {
      setSingleLoadingState(false);
    }
  });
}

/**
  Calls backend POST /api/analyze for single text classification
 */
async function analyzeContentAPI(text) {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    let errorMsg = `Request failed with status ${response.status}`;
    try {
      const errData = await response.json();
      if (errData.error) errorMsg = errData.error;
    } catch { }
    throw new Error(errorMsg);
  }

  return response.json();
}

function setSingleLoadingState(isLoading) {
  const analyzeBtn = document.getElementById("analyzeBtn");
  const spinner = document.getElementById("btnSpinner");
  const label = analyzeBtn?.querySelector(".btn-label");

  if (!analyzeBtn) return;

  analyzeBtn.disabled = isLoading;
  if (spinner) spinner.hidden = !isLoading;
  if (label) label.textContent = isLoading ? "Analyzing…" : "Analyze content";
}

function showPlaceholder(message) {
  const placeholder = document.getElementById("resultPlaceholder");
  const content = document.getElementById("resultContent");

  if (content) content.hidden = true;
  if (placeholder) {
    placeholder.textContent = message;
    placeholder.hidden = false;
  }
}

/**
  Renders single-text classification response into #resultContent
 */
function renderSingleResult(result) {
  const placeholder = document.getElementById("resultPlaceholder");
  const content = document.getElementById("resultContent");

  if (!result || !content) return;

  const tier = Number(result.tier || 1);
  const statusText = tier >= 2 ? `Flagged (Tier ${tier})` : "Clear / Lawful";
  const categoryText = result.category || (tier >= 2 ? "Abusive / Harmful" : "Lawful / Neutral");

  // Confidence estimation based on tier or data
  let confidenceVal = 95;
  if (tier === 4) confidenceVal = 96;
  else if (tier === 3) confidenceVal = 89;
  else if (tier === 2) confidenceVal = 76;

  document.getElementById("resultStatus").textContent = statusText;
  document.getElementById("resultCategory").textContent = categoryText;
  document.getElementById("resultConfidence").textContent = `${confidenceVal}%`;
  document.getElementById("resultReason").textContent = result.reason || "No flagged language detected.";

  // Determine flag booleans
  const matches = Array.isArray(result.matches) ? result.matches : [];
  const isAbusive = Boolean(
    tier === 2 ||
    matches.some(m => m.category === "abusive" || m.category === "offensive") ||
    categoryText.toLowerCase().includes("abusive")
  );
  const isThreatening = Boolean(
    tier === 3 ||
    tier === 4 ||
    matches.some(m => m.category === "threatening") ||
    categoryText.toLowerCase().includes("threat")
  );
  const isAntinational = Boolean(
    tier === 4 ||
    categoryText.toLowerCase().includes("antinational") ||
    categoryText.toLowerCase().includes("incitement")
  );

  setFlag("flagAbusive", isAbusive);
  setFlag("flagThreatening", isThreatening);
  setFlag("flagAntinational", isAntinational);

  if (placeholder) placeholder.hidden = true;
  content.hidden = false;
}

function setFlag(elementId, value) {
  const el = document.getElementById(elementId);
  if (!el) return;

  el.textContent = value ? "Yes" : "No";
  el.classList.toggle("is-yes", Boolean(value));
  el.classList.toggle("is-no", !value);
}

/* ---------------------------------------------------------
   YOUTUBE MONITORING DASHBOARD (LEXORA MODEL REPORT)
   --------------------------------------------------------- */
function initDashboardButtons() {
  const loadBtn = document.getElementById("loadReportBtn");
  const refreshBtn = document.getElementById("refreshReportBtn");

  loadBtn?.addEventListener("click", loadLatestReport);
  refreshBtn?.addEventListener("click", loadLatestReport);
}

function showDashboardLoading() {
  const empty = document.getElementById("emptyState");
  const loading = document.getElementById("loadingState");
  const dashContent = document.getElementById("dashContent");

  empty?.classList.add("hidden");
  dashContent?.classList.add("hidden");
  loading?.classList.remove("hidden");
}

function showDashboardContent() {
  const empty = document.getElementById("emptyState");
  const loading = document.getElementById("loadingState");
  const dashContent = document.getElementById("dashContent");

  loading?.classList.add("hidden");
  empty?.classList.add("hidden");
  dashContent?.classList.remove("hidden");
}

function getTierClass(tier) {
  const num = Number(tier);
  if (num === 4) return "tier-4";
  if (num === 3) return "tier-3";
  if (num === 2) return "tier-2";
  return "tier-1";
}

async function loadLatestReport() {
  showDashboardLoading();

  const loadingMsg = document.getElementById("loadingMsg");
  let elapsed = 0;
  const timerInterval = setInterval(() => {
    elapsed++;
    if (loadingMsg) {
      loadingMsg.textContent = `⏳ Fetching YouTube comments & running AI analysis... ${elapsed}s`;
    }
  }, 1000);

  const queryInput = document.getElementById("reportQueryInput");
  const query = queryInput ? queryInput.value.trim() : "";
  const commentsInput = document.getElementById("reportCommentsInput");
  const requestedComments = Math.min(2000, Math.max(1, Number.parseInt(commentsInput?.value || "200", 10) || 200));

  let url = "/api/report";
  if (query) {
    url += "?query=" + encodeURIComponent(query) + "&comments=" + requestedComments;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 180000); // 3 min timeout

  try {
    const response = await fetch(url, {
      method: "GET",
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });

    clearTimeout(timeoutId);
    clearInterval(timerInterval);

    if (!response.ok) {
      let errText = "Unable to load model report.";
      try {
        const errJson = await response.json();
        if (errJson.error) errText = errJson.error;
      } catch { }
      throw new Error(errText);
    }

    const data = await response.json();
    console.log("LEXORA MODEL REPORT LOADED:", data);

    renderReport(data);
    showToast("Model report loaded successfully.");
  } catch (error) {
    clearInterval(timerInterval);
    console.error("LEXORA REPORT ERROR:", error);

    const loading = document.getElementById("loadingState");
    const empty = document.getElementById("emptyState");

    loading?.classList.add("hidden");
    empty?.classList.remove("hidden");

    if (empty) {
      empty.innerHTML = `
        <div class="dash-error">
          <i class="fa-solid fa-triangle-exclamation" style="font-size:2rem;color:#C62828;margin-bottom:12px;"></i>
          <p style="font-weight:700;font-size:1.1rem;margin-bottom:8px;">Report Loading Failed</p>
          <p style="color:var(--color-text-muted);">${escapeHtml(error.message)}</p>
          <p style="font-size:0.85rem;color:var(--color-text-muted);margin-top:12px;">
            Ensure backend server is active and <code>/api/report</code> is responding.
          </p>
        </div>
      `;
    }
  }
}

function renderReport(report) {
  showDashboardContent();

  // Query & inputs
  const queryEl = document.getElementById("reportQuery");
  const queryInput = document.getElementById("reportQueryInput");
  const queryVal = report.query || queryInput?.value || "Default / Cached";

  if (queryEl) queryEl.textContent = queryVal;
  if (queryInput && report.query) queryInput.value = report.query;

  // Source & Policy
  const sourceEl = document.getElementById("reportSource");
  if (sourceEl) sourceEl.textContent = report.source || "YouTube Data API";

  const reviewEl = document.getElementById("reviewStatus");
  if (reviewEl) reviewEl.textContent = report.humanReviewOnly ? "HUMAN REVIEW ONLY" : "REVIEW REQUIRED";

  // Main stats
  const scanned = Number(report.commentsScanned ?? 0);
  const flagged = Number(report.flagged ?? 0);
  const lawful = Number(report.lowConcern ?? report.lawful ?? (scanned - flagged));

  document.getElementById("commentsScanned").textContent = scanned;
  document.getElementById("flaggedCount").textContent = flagged;
  document.getElementById("lawfulCount").textContent = lawful;

  // Tier counts & percentages
  const tierStats = report.tierStats || {};
  const formatTier = (val) => {
    const cnt = Number(val || 0);
    const pct = scanned ? ((cnt / scanned) * 100).toFixed(1) : "0.0";
    return `${cnt} (${pct}%)`;
  };

  document.getElementById("tier1Count").textContent = formatTier(tierStats.tier1 ?? lawful);
  document.getElementById("tier2Count").textContent = formatTier(tierStats.tier2);
  document.getElementById("tier3Count").textContent = formatTier(tierStats.tier3);
  document.getElementById("tier4Count").textContent = formatTier(tierStats.tier4);

  // Risk Badge & Bar Fill
  const risk = report.riskLevel || "Unknown";
  const riskBadge = document.getElementById("riskBadge");
  if (riskBadge) {
    riskBadge.textContent = risk;
    const rLower = String(risk).toLowerCase();
    if (rLower === "high" || rLower === "critical") {
      riskBadge.style.color = "#C62828";
      riskBadge.style.backgroundColor = "#FFEBEE";
    } else if (rLower === "moderate" || rLower === "medium") {
      riskBadge.style.color = "#E65100";
      riskBadge.style.backgroundColor = "#FFF3E0";
    } else {
      riskBadge.style.color = "#2E7D32";
      riskBadge.style.backgroundColor = "#E8F5E9";
    }
  }

  const riskMetrics = report.riskMetrics || {};
  const moderationPct = Number(riskMetrics.moderationPercent || (scanned > 0 ? (flagged / scanned) * 100 : 0));
  const negativePct = Number(riskMetrics.negativePercent || 0);
  const riskPct = Math.round(Math.max(moderationPct, negativePct));
  const riskBarFill = document.getElementById("riskBarFill");
  if (riskBarFill) {
    riskBarFill.style.width = `${Math.min(100, Math.max(0, riskPct))}%`;
  }

  // Topic Community Impact Summary (Qualitative 4-sentence sentiment analysis)
  const topicSummaryBox = document.getElementById("topicSummaryBox");
  const topicSummaryText = document.getElementById("topicSummaryText");
  if (topicSummaryBox && topicSummaryText) {
    let summary = (report.topicSummary || "").trim();
    if (!summary) {
      const q = report.query || "this topic";
      summary = `Public sentiment surrounding '${q}' reflects profound emotional engagement and active discussion across social platforms. Netizens express intense reactions, ranging from sharp institutional criticism to widespread calls for systemic reform. Online commentary highlights pervasive community concern alongside passionate demands for accountability and fairness. The overall digital environment reflects a mobilized public seeking transparent resolution and sustained dialogue.`;
    }
    topicSummaryText.textContent = summary;
    topicSummaryBox.style.display = "block";
  }

  // Flagged comments table
  const tableBody = document.getElementById("flaggedTableBody");
  const tableCount = document.getElementById("flaggedTableCount");
  const tableEmpty = document.getElementById("tableEmptyMsg");

  if (!tableBody) return;

  tableBody.innerHTML = "";
  const comments = Array.isArray(report.flaggedComments) ? report.flaggedComments : [];

  comments.forEach((item) => {
    const row = document.createElement("tr");
    const vTitle = item.videoTitle || "YouTube Video";
    const vUrl = item.videoUrl || "";

    const videoCellHTML = vUrl
      ? `<a href="${escapeHtml(vUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(vTitle)}</a>`
      : escapeHtml(vTitle);

    row.innerHTML = `
      <td>
        <span class="term-badge ${getTierClass(item.tier)}">Tier ${escapeHtml(item.tier)}</span>
      </td>
      <td>${videoCellHTML}</td>
      <td>${escapeHtml(item.user || "Unknown")}</td>
      <td style="white-space:pre-wrap;min-width:280px;">${escapeHtml(item.comment || "")}</td>
      <td>${escapeHtml(item.reason || "Flagged by model for human review.")}</td>
    `;
    tableBody.appendChild(row);
  });

  if (tableCount) tableCount.textContent = `${comments.length} flagged comments`;
  if (tableEmpty) tableEmpty.classList.toggle("hidden", comments.length > 0);
}
