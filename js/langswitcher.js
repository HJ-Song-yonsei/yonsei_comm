(function () {
  // Dropdown UI: keep the existing look/feel and behavior.
  if (typeof window.jQuery === "undefined") return;

  window.jQuery(function ($) {
    var $switcher = $("#langSwitcher");
    if ($switcher.length === 0) return;

    var $btn = $switcher.find(".lang-toggle");
    var $menu = $("#langMenu");

    function openMenu() {
      $switcher.addClass("is-open");
      $btn.attr("aria-expanded", "true");
    }

    function closeMenu() {
      $switcher.removeClass("is-open");
      $btn.attr("aria-expanded", "false");
    }

    $btn.on("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if ($switcher.hasClass("is-open")) closeMenu();
      else openMenu();
    });

    $menu.on("click", "a", function () {
      closeMenu();
    });

    $(document).on("click", closeMenu);
    $(document).on("keydown", function (e) {
      if (e.key === "Escape") closeMenu();
    });
  });
})();

(function () {
  let gtLoading = null;

  function repoBase() {
    // Custom domain: /index.html or /en/index.html => ""
    // GitHub project page: /yonsei_comm/... => "/yonsei_comm"
    const parts = location.pathname.split("/").filter(Boolean);
    const isGithubIo = location.hostname.endsWith("github.io");
    return isGithubIo && parts.length ? `/${parts[0]}` : "";
  }

  function pathAfterRepoBase() {
    const base = repoBase();
    return base && location.pathname.startsWith(base)
      ? location.pathname.slice(base.length) || "/"
      : location.pathname;
  }

  function isEnglishPage() {
    const path = pathAfterRepoBase();
    return path === "/en" || path.startsWith("/en/");
  }

  function currentPageName() {
    let path = pathAfterRepoBase();
    if (path === "/" || path === "/en" || path === "/en/") return "index.html";
    path = path.replace(/^\/en\//, "/");
    const last = path.split("/").filter(Boolean).pop();
    return last || "index.html";
  }

  function currentHash() {
    return location.hash || "";
  }

  function englishUrl() {
    const base = repoBase();
    const page = currentPageName();
    return page === "index.html"
      ? `${base}/en/${currentHash()}`
      : `${base}/en/${page}${currentHash()}`;
  }

  function koreanUrl(extraQuery = "") {
    const base = repoBase();
    const page = currentPageName();
    const pagePath = page === "index.html" ? `${base}/` : `${base}/${page}`;
    return `${pagePath}${extraQuery}${currentHash()}`;
  }

  window.googleTranslateElementInit = function () {
    new google.translate.TranslateElement(
      {
        pageLanguage: "ko",
        includedLanguages: "ja,zh-CN",
        layout: google.translate.TranslateElement.InlineLayout.VERTICAL,
      },
      "google_translate_element"
    );
  };

  function loadGoogleTranslateWidget() {
    if (gtLoading) return gtLoading;

    gtLoading = new Promise((resolve, reject) => {
      if (window.google && window.google.translate && document.querySelector(".goog-te-combo")) {
        resolve();
        return;
      }

      const s = document.createElement("script");
      s.src = "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
      s.async = true;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error("Failed to load Google Translate widget script."));
      document.head.appendChild(s);
    });

    return gtLoading;
  }

  function waitForCombo(maxTries = 20, intervalMs = 150) {
    return new Promise((resolve, reject) => {
      let tries = 0;
      const timer = setInterval(() => {
        const combo = document.querySelector(".goog-te-combo");
        if (combo) {
          clearInterval(timer);
          resolve(combo);
          return;
        }
        tries += 1;
        if (tries >= maxTries) {
          clearInterval(timer);
          reject(new Error("Google Translate combo not found. (widget not initialized)"));
        }
      }, intervalMs);
    });
  }

  async function changeGoogleLanguage(langCode) {
    await loadGoogleTranslateWidget();
    const combo = await waitForCombo();
    combo.value = langCode;
    combo.dispatchEvent(new Event("change"));
    document.documentElement.setAttribute("lang", langCode);
  }

  function deleteGoogleTranslateCookies() {
    ["googtrans", "googtransopt"].forEach((name) => {
      document.cookie = `${name}=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT`;
    });
  }

  function bind(id, handler) {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", handler);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const english = isEnglishPage();

    // English is now a first-class static site; do not run Google Translate for EN.
    bind("lang_en", (e) => {
      e.preventDefault();
      deleteGoogleTranslateCookies();
      if (!english) location.assign(englishUrl());
    });

    bind("lang_ko", (e) => {
      e.preventDefault();
      deleteGoogleTranslateCookies();
      if (english) location.assign(koreanUrl());
      else setTimeout(() => location.reload(), 50);
    });

    // Japanese/Chinese continue to use the existing Google widget until their
    // dedicated static builds are introduced. If clicked from /en/, return to
    // the Korean counterpart first, then translate there.
    [
      ["lang_ja", "ja"],
      ["lang_zh-CN", "zh-CN"],
    ].forEach(([id, lang]) => {
      bind(id, async (e) => {
        e.preventDefault();
        if (english) {
          location.assign(koreanUrl(`?gt=${encodeURIComponent(lang)}`));
          return;
        }
        try {
          await changeGoogleLanguage(lang);
        } catch (err) {
          console.error(err);
        }
      });
    });

    // Handle a JA/ZH handoff originating from an English page.
    if (!english) {
      const params = new URLSearchParams(location.search);
      const gt = params.get("gt");
      if (gt === "ja" || gt === "zh-CN") {
        loadGoogleTranslateWidget()
          .then(() => changeGoogleLanguage(gt))
          .then(() => {
            params.delete("gt");
            const query = params.toString();
            history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}${location.hash}`);
          })
          .catch(console.error);
      } else {
        // Preserve current Korean-page behavior and responsiveness.
        loadGoogleTranslateWidget().catch(() => {});
      }
    }
  });
})();
