      // Global command handler for dialog close buttons
      document.addEventListener('DOMContentLoaded', function() {
        // Handle command="close" buttons
        document.addEventListener('click', function(e) {
          const button = e.target.closest('button[command="close"]');
          if (!button) return;
          
          const commandFor = button.getAttribute('commandfor');
          if (!commandFor) return;
          
          const dialog = document.getElementById(commandFor);
          if (dialog && typeof dialog.close === 'function') {
            e.preventDefault();
            e.stopPropagation();
            
            // Add data-closed attributes to hide the modal
            const backdrop = dialog.querySelector('el-dialog-backdrop');
            const panel = dialog.querySelector('el-dialog-panel');
            
            if (backdrop) {
              backdrop.setAttribute('data-closed', '');
            }
            if (panel) {
              panel.setAttribute('data-closed', '');
            }
            
            // Wait for transition, then close
            setTimeout(function() {
              dialog.close();
            }, 200);
          }
        });
        
        // Handle dialog close events to restore data-closed state
        document.addEventListener('close', function(e) {
          if (e.target.tagName === 'DIALOG') {
            const dialog = e.target;
            const backdrop = dialog.querySelector('el-dialog-backdrop');
            const panel = dialog.querySelector('el-dialog-panel');
            
            if (backdrop) {
              backdrop.setAttribute('data-closed', '');
            }
            if (panel) {
              panel.setAttribute('data-closed', '');
            }
          }
        });
      });
