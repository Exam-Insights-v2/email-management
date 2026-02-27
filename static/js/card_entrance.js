      // Global card entrance animation
      (function() {
        function runCardEntranceAnimations(root, options) {
          const opts = options || {};
          const animate = opts.animate !== false;
          const scope = root || document;
          const cards = Array.from(
            scope.querySelectorAll(
              '.fade-in-card:not(.card-entered), .fade-in-card-simple:not(.card-entered)'
            )
          );
          if (!cards.length) return;

          if (!animate) {
            const visibleCards = cards.filter(function(card) {
              return card.getClientRects().length > 0;
            });
            const targetCards = visibleCards.length ? visibleCards : cards;
            targetCards.forEach(function(card) {
              card.classList.add('card-entered');
              card.classList.remove('card-entering');
              card.style.removeProperty('--card-enter-delay');
            });
            return;
          }

          cards.forEach(function(card, index) {
            const enteringClass = card.classList.contains('fade-in-card-simple')
              ? 'card-entering-simple'
              : 'card-entering';
            card.classList.add(enteringClass);
            const delay = Math.min(index * 22, 220);
            card.style.setProperty('--card-enter-delay', delay + 'ms');
          });

          requestAnimationFrame(function() {
            cards.forEach(function(card) {
              card.classList.add('card-entered');
              card.classList.remove('card-entering');
              card.classList.remove('card-entering-simple');
            });
          });
        }

        window.runCardEntranceAnimations = runCardEntranceAnimations;
        document.addEventListener('DOMContentLoaded', function() {
          // Avoid first-paint flash: mark cards entered on initial page load.
          runCardEntranceAnimations(document, { animate: false });
        });
      })();
