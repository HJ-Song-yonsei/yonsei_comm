
/*! click-scroll.safe.js
 * Robust smooth-scroll + scrollspy with guards for missing targets and cross-page links.
 * Works with jQuery but degrades if jQuery is absent.
 */
(function () {
  var $ = window.jQuery;
  var hasJQ = !!$;

  function samePage(href) {
    try {
      var u = new URL(href, window.location.href);
      return u.pathname === window.location.pathname;
    } catch (e) {
      return href && href.charAt(0) === '#';
    }
  }

  function getTargetElement(href) {
    try {
      var u = new URL(href, window.location.href);
      if (u.hash) {
        return document.querySelector(u.hash);
      }
    } catch (e) {
      if (href && href.charAt(0) === '#') return document.querySelector(href);
    }
    return null;
  }

  // Smooth click scroll
  function onClick(e) {
    var a = e.target.closest ? e.target.closest('a.click-scroll') : null;
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (!samePage(href)) return; // let browser navigate to other page

    var target = getTargetElement(href);
    if (!target) return; // nothing to do

    e.preventDefault();
    var top = target.getBoundingClientRect().top + window.pageYOffset;
    if (hasJQ) {
      $('html, body').stop(true).animate({ scrollTop: top }, 500);
    } else {
      window.scrollTo({ top: top, behavior: 'smooth' });
    }
  }

  // Scrollspy (highlight active link) with guards
  function setupScrollSpy() {
    var links = Array.prototype.slice.call(document.querySelectorAll('a.click-scroll'))
      .filter(function (a) { return samePage(a.getAttribute('href') || ''); });

    if (!links.length) return;

    var pairs = links.map(function (a) {
      var el = getTargetElement(a.getAttribute('href') || '');
      return el ? { a: a, el: el } : null;
    }).filter(Boolean);

    if (!pairs.length) return;

    var navHeight = (document.querySelector('.navbar') || {}).offsetHeight || 0;

    function onScroll() {
      var scrollPos = window.pageYOffset || document.documentElement.scrollTop || 0;
      var current = null;
      for (var i = 0; i < pairs.length; i++) {
        var rect = pairs[i].el.getBoundingClientRect();
        var top = rect.top + window.pageYOffset - navHeight - 5;
        if (scrollPos >= top) current = pairs[i];
      }
      links.forEach(function (lnk) { lnk.classList.remove('active'); });
      if (current) current.a.classList.add('active');
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  document.addEventListener('click', onClick, false);
  window.addEventListener('DOMContentLoaded', setupScrollSpy, false);
})();
