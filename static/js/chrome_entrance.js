      // Global app chrome entrance animation (sidebar/header/shell)
      (function() {
        function runChromeEntranceAnimations(root, options) {
          const opts = options || {};
          const animate = opts.animate !== false;
          const scope = root || document;
          const chromeEls = Array.from(scope.querySelectorAll('.fade-in-chrome:not(.chrome-entered)'));
          if (!chromeEls.length) return;

          if (!animate) {
            chromeEls.forEach(function(el) {
              el.classList.add('chrome-entered');
              el.classList.remove('chrome-entering');
              el.style.removeProperty('--chrome-enter-delay');
            });
            return;
          }

          chromeEls.forEach(function(el, index) {
            el.classList.add('chrome-entering');
            const orderAttr = parseInt(el.getAttribute('data-chrome-order') || '', 10);
            const order = Number.isFinite(orderAttr) ? orderAttr : index;
            const delay = Math.min(order * 28, 140);
            el.style.setProperty('--chrome-enter-delay', delay + 'ms');
          });

          requestAnimationFrame(function() {
            chromeEls.forEach(function(el) {
              el.classList.add('chrome-entered');
              el.classList.remove('chrome-entering');
            });
          });
        }

        window.runChromeEntranceAnimations = runChromeEntranceAnimations;
        document.addEventListener('DOMContentLoaded', function() {
          // Avoid first-paint flash: mark chrome entered on initial page load.
          runChromeEntranceAnimations(document, { animate: false });
        });
      })();
