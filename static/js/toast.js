// Shared toast API (Sonner-style)
(function() {
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) return;

  let toastIdCounter = 0;
  const toasts = new Map();

  function createToast(message, type = 'info', duration = 5000) {
    const toastId = `toast-${toastIdCounter++}`;
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `pointer-events-auto flex items-start gap-3 rounded-lg border p-4 shadow-sm transition-all duration-300 animate-in slide-in-from-bottom-2 ${
      type === 'success'
        ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-900 dark:text-emerald-100 border-emerald-200 dark:border-emerald-800'
        : type === 'error'
        ? 'bg-red-50 dark:bg-red-900/20 text-red-900 dark:text-red-100 border-red-200 dark:border-red-800'
        : 'bg-cyan-50 dark:bg-cyan-900/20 text-cyan-900 dark:text-cyan-100 border-cyan-200 dark:border-cyan-800'
    }`;
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(20px)';

    const icon = document.createElement('div');
    icon.className = 'flex-shrink-0 mt-0.5';
    if (type === 'success') {
      icon.innerHTML = '<span class="material-icons size-5 text-emerald-600 dark:text-emerald-400">check_circle</span>';
    } else if (type === 'error') {
      icon.innerHTML = '<span class="material-icons size-5 text-red-600 dark:text-red-400">cancel</span>';
    } else {
      icon.innerHTML = '<span class="material-icons size-5 text-cyan-600 dark:text-cyan-400">info</span>';
    }

    const content = document.createElement('div');
    content.className = 'flex-1 text-sm font-medium';
    content.textContent = message;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors';
    closeBtn.innerHTML = '<span class="material-icons size-4">close</span>';
    closeBtn.onclick = () => removeToast(toastId);

    toast.appendChild(icon);
    toast.appendChild(content);
    toast.appendChild(closeBtn);
    toastContainer.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });

    toasts.set(toastId, { element: toast, timeout: null });

    if (duration > 0) {
      const timeout = setTimeout(() => {
        removeToast(toastId);
      }, duration);
      toasts.get(toastId).timeout = timeout;
    }

    return toastId;
  }

  function removeToast(toastId) {
    const toastData = toasts.get(toastId);
    if (!toastData) return;

    if (toastData.timeout) {
      clearTimeout(toastData.timeout);
    }

    const toast = toastData.element;
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-20px)';

    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
      toasts.delete(toastId);
    }, 300);
  }

  window.toast = {
    success: (message, duration) => createToast(message, 'success', duration),
    error: (message, duration) => createToast(message, 'error', duration),
    info: (message, duration) => createToast(message, 'info', duration),
    remove: removeToast,
  };
})();
