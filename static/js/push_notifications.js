(function() {
  function getCookie(name) {
    var cookieValue = null;
    if (!document.cookie) return cookieValue;
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i += 1) {
      var cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
    return cookieValue;
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var rawData = window.atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; i += 1) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function setButtonState(button, state, text) {
    button.dataset.state = state;
    button.disabled = state === 'loading' || state === 'unsupported';
    button.textContent = text;
  }

  async function fetchJson(url, options) {
    var response = await fetch(url, options || {});
    var data = {};
    try {
      data = await response.json();
    } catch (e) {}
    if (!response.ok) {
      throw new Error(data.error || ('Request failed: ' + response.status));
    }
    return data;
  }

  window.initPushNotificationsSettings = function initPushNotificationsSettings(options) {
    var configured = !!(options && options.configured);
    var vapidPublicKey = options && options.vapidPublicKey;
    var buttons = document.querySelectorAll('[data-push-toggle]');
    var statusEls = document.querySelectorAll('[data-push-status]');

    if (!buttons.length) return;

    if (!configured || !vapidPublicKey) {
      buttons.forEach(function(button) {
        setButtonState(button, 'unsupported', 'Not configured');
      });
      statusEls.forEach(function(el) {
        el.textContent = 'Push notifications are not configured on the server.';
      });
      return;
    }

    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      buttons.forEach(function(button) {
        setButtonState(button, 'unsupported', 'Unsupported');
      });
      statusEls.forEach(function(el) {
        el.textContent = 'This browser does not support push notifications.';
      });
      return;
    }

    var registrationPromise = navigator.serviceWorker.register('/push-sw.js');

    function statusElementForAccount(accountId) {
      return document.querySelector('[data-push-status][data-account-id="' + String(accountId) + '"]');
    }

    async function refreshAccountState(accountId, button) {
      try {
        var data = await fetchJson('/notifications/push/subscription/' + String(accountId) + '/');
        if (data.is_subscribed) {
          setButtonState(button, 'active', 'Disable Browser Push');
        } else {
          setButtonState(button, 'inactive', 'Enable Browser Push');
        }
      } catch (error) {
        setButtonState(button, 'inactive', 'Enable Browser Push');
      }
    }

    buttons.forEach(function(button) {
      var accountId = button.getAttribute('data-account-id');
      var statusEl = statusElementForAccount(accountId);
      refreshAccountState(accountId, button);

      button.addEventListener('click', async function() {
        var state = button.dataset.state || 'inactive';
        setButtonState(button, 'loading', 'Working...');

        try {
          var registration = await registrationPromise;
          var currentSubscription = await registration.pushManager.getSubscription();

          if (state === 'active') {
            await fetchJson('/notifications/push/subscription/' + String(accountId) + '/', {
              method: 'DELETE',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
              },
              body: JSON.stringify({
                endpoint: currentSubscription ? currentSubscription.endpoint : null
              })
            });
            setButtonState(button, 'inactive', 'Enable Browser Push');
            if (statusEl) statusEl.textContent = 'Browser push disabled for this account.';
            return;
          }

          var permission = Notification.permission;
          if (permission !== 'granted') {
            permission = await Notification.requestPermission();
          }
          if (permission !== 'granted') {
            setButtonState(button, 'blocked', 'Permission Blocked');
            if (statusEl) statusEl.textContent = 'Allow notifications in your browser settings to enable push.';
            return;
          }

          var subscription = currentSubscription;
          if (!subscription) {
            subscription = await registration.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
            });
          }

          await fetchJson('/notifications/push/subscription/' + String(accountId) + '/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
              subscription: subscription.toJSON(),
              user_agent: navigator.userAgent
            })
          });
          setButtonState(button, 'active', 'Disable Browser Push');
          if (statusEl) statusEl.textContent = 'Browser push is enabled for this account.';
        } catch (error) {
          setButtonState(button, 'inactive', 'Enable Browser Push');
          if (statusEl) statusEl.textContent = error.message || 'Unable to update push subscription.';
        }
      });
    });
  };
})();
