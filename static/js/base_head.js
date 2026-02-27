      // Theme management
      (function() {
        // Get theme from localStorage or default to dark
        const getTheme = () => {
          const stored = localStorage.getItem('theme');
          if (stored) return stored;
          // Check system preference
          return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        };

        // Sync browser UI chrome color and manifest with current theme.
        const syncBrowserTheme = (theme) => {
          const meta = document.getElementById('theme-color-meta');
          if (meta) {
            const lightColor = meta.getAttribute('data-light-color') || '#ffffff';
            const darkColor = meta.getAttribute('data-dark-color') || '#111827';
            meta.setAttribute('content', theme === 'dark' ? darkColor : lightColor);
          }

          const manifest = document.getElementById('app-manifest');
          if (manifest) {
            const lightHref = manifest.getAttribute('data-light-href');
            const darkHref = manifest.getAttribute('data-dark-href');
            const targetHref = theme === 'dark' ? darkHref : lightHref;
            if (targetHref && manifest.getAttribute('href') !== targetHref) {
              manifest.setAttribute('href', targetHref);
            }
          }
        };

        // Apply theme
        const applyTheme = (theme) => {
          const html = document.documentElement;
          if (theme === 'dark') {
            html.classList.add('dark');
          } else {
            html.classList.remove('dark');
          }
          syncBrowserTheme(theme);
        };

        // Set initial theme before page renders to prevent flash
        applyTheme(getTheme());

        // Expose theme toggle function
        window.toggleTheme = function() {
          const currentTheme = getTheme();
          const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
          localStorage.setItem('theme', newTheme);
          applyTheme(newTheme);
        };

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
          if (!localStorage.getItem('theme')) {
            applyTheme(e.matches ? 'dark' : 'light');
          }
        });
      })();

      // Handle warning modal form submissions
      document.addEventListener('DOMContentLoaded', function() {
        // Find all forms with data-warning-modal attribute
        document.querySelectorAll('form[data-warning-modal]').forEach(function(form) {
          const modalId = form.getAttribute('data-warning-modal');
          const confirmButton = document.getElementById(modalId + '-confirm');
          const modal = document.getElementById(modalId);
          
          if (!modal) {
            console.warn('Modal not found:', modalId);
            return;
          }
          
          if (!confirmButton) {
            console.warn('Confirm button not found for modal:', modalId);
            return;
          }
          
          // Prevent default form submission
          form.addEventListener('submit', function(e) {
            e.preventDefault();
            e.stopPropagation();
            // Show the modal using native dialog API
            if (modal && typeof modal.showModal === 'function') {
              modal.showModal();
            } else {
              console.error('Modal showModal method not available:', modalId, modal);
            }
            return false;
          });
          
          // Handle confirm button click
          confirmButton.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            // Close modal first
            if (modal && typeof modal.close === 'function') {
              modal.close();
            }
            // Submit the form after a short delay to ensure modal closes
            setTimeout(function() {
              // Create a hidden submit button and click it to ensure proper form submission
              const submitBtn = document.createElement('button');
              submitBtn.type = 'submit';
              submitBtn.style.display = 'none';
              form.appendChild(submitBtn);
              submitBtn.click();
            }, 150);
            return false;
          });
        });
      });
