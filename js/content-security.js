/* Helpers for safe rendering of repository-managed content. */
(function (root) {
  "use strict";
  function escapeHTML(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
    });
  }

  function safeURL(input) {
    const raw = String(input == null ? "" : input).trim();
    if (!raw || /[\u0000-\u001F\u007F]/.test(raw)) return null;
    try {
      const url = new URL(raw, root.location.href);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
    } catch (_) {
      return null;
    }
  }

  // Fail closed to escaped text if DOMPurify cannot load.
  function sanitizeHTML(input) {
    const html = String(input == null ? "" : input);
    if (!root.DOMPurify || typeof root.DOMPurify.sanitize !== "function") {
      return "<pre>" + escapeHTML(html) + "</pre>";
    }
    return root.DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ["script", "style", "iframe", "object", "embed", "form"],
      FORBID_ATTR: ["srcdoc"]
    });
  }

  root.ContentSecurity = Object.freeze({ escapeHTML, safeURL, sanitizeHTML });
})(window);
