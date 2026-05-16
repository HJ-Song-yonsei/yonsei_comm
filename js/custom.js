
  (function ($) {
  
  "use strict";

    // COUNTER NUMBERS
    jQuery('.counter-thumb').appear(function() {
      jQuery('.counter-number').countTo();
    });
    
    // CUSTOM LINK
    $('.smoothscroll').click(function(){
    var el = $(this).attr('href');
    var elWrapped = $(el);
    var header_height = $('.navbar').height();

    scrollToDiv(elWrapped,header_height);
    return false;

    function scrollToDiv(element,navheight){
      var offset = element.offset();
      var offsetTop = offset.top;
      var totalScroll = offsetTop-navheight;

      $('body,html').animate({
      scrollTop: totalScroll
      }, 300);
    }
});
    

    // RECENT NEWS: horizontal rotate (3 cards per view on desktop)
    const recentNewsTrack = document.querySelector('.recent-news-track');

    if (recentNewsTrack) {
      const recentNewsItems = Array.from(recentNewsTrack.querySelectorAll('.recent-news-item'));
      let currentIndex = 0;

      const getVisibleCount = () => {
        if (window.innerWidth < 768) return 1;
        if (window.innerWidth < 992) return 2;
        return 3;
      };

      const slideRecentNews = () => {
        const visibleCount = getVisibleCount();

        if (recentNewsItems.length <= visibleCount) {
          recentNewsTrack.style.transform = 'translateX(0)';
          return;
        }

        const maxIndex = recentNewsItems.length - visibleCount;
        currentIndex = currentIndex >= maxIndex ? 0 : currentIndex + visibleCount;

        if (currentIndex > maxIndex) {
          currentIndex = maxIndex;
        }

        const movePercent = (100 / visibleCount) * currentIndex;
        recentNewsTrack.style.transform = `translateX(-${movePercent}%)`;
      };

      setInterval(slideRecentNews, 4000);

      window.addEventListener('resize', () => {
        currentIndex = 0;
        recentNewsTrack.style.transform = 'translateX(0)';
      });
    }

  })(window.jQuery);


