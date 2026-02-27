      // Theme management
      (function() {
        // Get theme from localStorage or default to dark
        const getTheme = () => {
          const stored = localStorage.getItem('theme');
          if (stored) return stored;
          // Check system preference
          return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        };

        // Apply theme
        const applyTheme = (theme) => {
          const html = document.documentElement;
          if (theme === 'dark') {
            html.classList.add('dark');
          } else {
            html.classList.remove('dark');
          }
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
