      // Global function to open edit task modal
      window.openEditTaskModal = function(taskPk) {
        console.log('openEditTaskModal called with taskPk:', taskPk, typeof taskPk);
        
        // Ensure taskPk is a number/string
        if (!taskPk) {
          console.error('Invalid taskPk:', taskPk);
          return;
        }
        
        const modalId = 'edit-task-' + String(taskPk);
        console.log('Looking for modal with ID:', modalId);
        
        // Wait a bit for DOM to be ready if needed
        const findModal = () => {
          const modal = document.getElementById(modalId);
          const contentDiv = document.getElementById(modalId + '-content');
          
          if (!modal) {
            console.error('Edit modal not found:', modalId);
            const allModals = Array.from(document.querySelectorAll('dialog[id^="edit-task-"]'));
            console.log('Available edit modals:', allModals.map(d => d.id));
            console.log('Total dialogs:', document.querySelectorAll('dialog').length);
            return null;
          }
          
          if (!contentDiv) {
            console.error('Content div not found:', modalId + '-content');
            return null;
          }
          
          return { modal, contentDiv };
        };
        
        let modalData = findModal();
        
        // If not found immediately, try again after a short delay
        if (!modalData) {
          setTimeout(() => {
            modalData = findModal();
            if (modalData) {
              openModal(modalData.modal, modalData.contentDiv, taskPk, modalId);
            }
          }, 100);
          return;
        }
        
        openModal(modalData.modal, modalData.contentDiv, taskPk, modalId);
      };
      
      function openModal(modal, contentDiv, taskPk, modalId) {
        console.log('Opening modal:', modalId);
        
        if (typeof modal.showModal !== 'function') {
          console.error('Modal does not have showModal method');
          return;
        }
        
        modal.showModal();
        
        
        // Load form content if not already loaded
        if (!contentDiv.hasAttribute('data-loaded')) {
          // Construct the URL properly
          const url = '/tasks/' + String(taskPk) + '/edit/';
          console.log('Fetching form from:', url);
          fetch(url)
            .then(response => {
              if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.status);
              }
              return response.text();
            })
            .then(html => {
              console.log('Form loaded successfully');
              contentDiv.innerHTML = html;
              contentDiv.setAttribute('data-loaded', 'true');
              // Update form action and drawer_id references to use modal_id
              const form = contentDiv.querySelector('form');
              if (form) {
                // Update the cancel button to close the modal
                const cancelButton = form.querySelector('button[command="close"]');
                if (cancelButton) {
                  cancelButton.setAttribute('commandfor', modalId);
                }
                // Initialize date pickers for dynamically loaded content
                if (window.initDatePickers) {
                  window.initDatePickers();
                }
                // Initialize priority sliders for dynamically loaded content
                if (window.initPrioritySliders) {
                  window.initPrioritySliders();
                }
                // Apply styles to select elements
                const selects = form.querySelectorAll('.select-wrapper select');
                selects.forEach(select => {
                  select.classList.add('col-start-1', 'row-start-1', 'block', 'w-full', 'rounded-md', 'bg-gray-100', 'dark:bg-white/5', 'px-3', 'py-1.5', 'text-sm', 'text-gray-900', 'dark:text-white', 'border-0', 'focus:ring-2', 'focus:ring-cyan-600', 'appearance-none');
                });
              }
            })
            .catch(error => {
              console.error('Error loading form:', error);
              contentDiv.innerHTML = '<p class="text-red-400">Error loading form. Please refresh the page.</p>';
            });
        } else {
          console.log('Form already loaded, reinitializing');
          // Initialize date pickers if content already loaded
          if (window.initDatePickers) {
            window.initDatePickers();
          }
          // Initialize priority sliders if content already loaded
          if (window.initPrioritySliders) {
            window.initPrioritySliders();
          }
        }
      }

      // Keep the old function name for backwards compatibility
      window.openEditTaskDrawer = window.openEditTaskModal;
      
      // Add event delegation for edit task buttons
      document.addEventListener('DOMContentLoaded', function() {
        // Use event delegation to handle edit button clicks
        document.addEventListener('click', function(e) {
          const editBtn = e.target.closest('.edit-task-btn');
          if (editBtn) {
            e.preventDefault();
            e.stopPropagation();
            const taskPk = editBtn.getAttribute('data-task-pk');
            if (taskPk && window.openEditTaskModal) {
              console.log('Edit button clicked, taskPk:', taskPk);
              window.openEditTaskModal(parseInt(taskPk));
            } else {
              console.error('Edit button clicked but taskPk or function not found', { taskPk, hasFunction: !!window.openEditTaskModal });
            }
          }
        });
      });
