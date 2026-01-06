(function () {
  // jQuery 의존 (현재 사이트가 jQuery 기반이므로)
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

    // 버튼 클릭: 토글
    $btn.on("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if ($switcher.hasClass("is-open")) closeMenu();
      else openMenu();
    });

    // 메뉴 항목 클릭: 닫기(번역 동작은 기존 #lang_* 핸들러가 수행)
    $menu.on("click", "a", function () {
      closeMenu();
    });

    // 바깥 클릭: 닫기
    $(document).on("click", function () {
      closeMenu();
    });

    // ESC: 닫기
    $(document).on("keydown", function (e) {
      if (e.key === "Escape") closeMenu();
    });
  });
})();

// langswitcher.js
(function () {
  let gtLoading = null;

  // 1) 전역 콜백을 반드시 window에 등록
  window.googleTranslateElementInit = function () {
    new google.translate.TranslateElement(
      {
        pageLanguage: "ko",
        includedLanguages: "en,ja,zh-CN",
        layout: google.translate.TranslateElement.InlineLayout.VERTICAL,
      },
      "google_translate_element"
    );
  };

  // 2) element.js 로드 (1회)
  function loadGoogleTranslateWidget() {
    if (gtLoading) return gtLoading;

    gtLoading = new Promise((resolve, reject) => {
      // 이미 로드된 경우
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

  // 3) 콤보박스가 실제로 생길 때까지 폴링
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

  async function changeLanguage(langCode) {
    await loadGoogleTranslateWidget();
    const combo = await waitForCombo();
    combo.value = langCode;
    combo.dispatchEvent(new Event("change"));
    // 체크표시용(선택): html lang도 같이 갱신
    document.documentElement.setAttribute("lang", langCode);
  }

  function deleteGoogleTranslateCookies() {
    ["googtrans", "googtransopt"].forEach((name) => {
      document.cookie = name + "=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT";
    });
  }

  // 4) 이벤트 바인딩
  document.addEventListener("DOMContentLoaded", () => {
    // 위젯 로드는 페이지 로드 시 미리 시작(클릭 반응성↑)
    loadGoogleTranslateWidget().catch(() => {});

    const bind = (id, handler) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("click", handler);
    };

    bind("lang_en", async (e) => {
      e.preventDefault();
      try { await changeLanguage("en"); } catch (err) { console.error(err); }
      // loadGlossary("en"); // 필요 시
    });

    bind("lang_ja", async (e) => {
      e.preventDefault();
      try { await changeLanguage("ja"); } catch (err) { console.error(err); }
      // loadGlossary("ja");
    });

    bind("lang_zh-CN", async (e) => {
      e.preventDefault();
      try { await changeLanguage("zh-CN"); } catch (err) { console.error(err); }
      // loadGlossary("zh-CN");
    });

    bind("lang_ko", (e) => {
      e.preventDefault();
      deleteGoogleTranslateCookies();
      setTimeout(() => location.reload(), 300);
    });
  });
})();