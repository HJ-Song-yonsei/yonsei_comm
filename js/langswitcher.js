(function () {
  "use strict";

  const ENGLISH_PAGES = new Set([
    "index.html",
    "intro.html",
    "people.html",
    "people_emeritus.html",
    "curriculum.html",
    "curriculum_graduate.html",
    "scholarship.html",
    "research.html",
    "research_CnSC.html",
    "research_DPnAI.html",
    "research_JDnS.html",
    "research_PHnW.html",
    "research_institute.html",
    "yonsei_uva.html",
    "yonsei_cityu.html",
  ]);

  function repoBase() {
    const parts = location.pathname.split("/").filter(Boolean);
    const isGithubProjectPage = location.hostname.endsWith("github.io") && parts.length;
    return isGithubProjectPage ? `/${parts[0]}` : "";
  }

  function pathAfterBase() {
    const base = repoBase();
    return base && location.pathname.startsWith(base)
      ? location.pathname.slice(base.length) || "/"
      : location.pathname;
  }

  function isEnglishPage() {
    const path = pathAfterBase();
    return path === "/en" || path === "/en/" || path.startsWith("/en/");
  }

  function currentPageName() {
    let path = pathAfterBase().replace(/^\/en\/?/, "/");
    if (path === "/" || path === "") return "index.html";
    return path.split("/").filter(Boolean).pop() || "index.html";
  }

  function samePageEnglishTarget() {
    const base = repoBase();
    const page = currentPageName();
    const hash = location.hash || "";

    if (page === "index.html") return `${base}/en/${hash}`;
    if (ENGLISH_PAGES.has(page)) return `${base}/en/${page}${hash}`;
    if (page === "people_profpractice.html") return `${base}/en/people.html${hash}`;
    return `${base}/en/${hash}`;
  }

  function samePageKoreanTarget() {
    const base = repoBase();
    const page = currentPageName();
    const hash = location.hash || "";
    return page === "index.html" ? `${base}/${hash}` : `${base}/${page}${hash}`;
  }

  function renderToggle() {
    const switcher = document.getElementById("langSwitcher");
    if (!switcher) return;

    const english = isEnglishPage();
    document.documentElement.setAttribute("lang", english ? "en" : "ko");

    const link = document.createElement("a");
    link.className = "lang-direct-toggle";
    link.href = english ? samePageKoreanTarget() : samePageEnglishTarget();
    link.setAttribute("aria-label", english ? "한국어 페이지로 이동" : "Switch to English");

    const label = document.createElement("span");
    label.textContent = english ? "KO" : "EN";
    link.appendChild(label);

    const caret = document.createElement("span");
    caret.className = "lang-direct-toggle-caret";
    caret.setAttribute("aria-hidden", "true");
    caret.textContent = "▾";
    link.appendChild(caret);

    switcher.replaceChildren(link);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderToggle);
  } else {
    renderToggle();
  }
})();
