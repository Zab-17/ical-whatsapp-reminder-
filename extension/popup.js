document.addEventListener('DOMContentLoaded', function() {

  function show(id) {
    var views = document.querySelectorAll('.view');
    for (var i = 0; i < views.length; i++) {
      views[i].classList.remove('active');
    }
    document.getElementById(id).classList.add('active');
  }

  // Check state on load
  chrome.storage.local.get(['connected', 'phone', 'name'], function(data) {
    if (data.connected) {
      show('v-done');
    } else if (data.phone) {
      show('v-canvas');
    }
  });

  // Save button
  var saveBtn = document.getElementById('saveBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', function() {
      var nameVal = document.getElementById('name').value.trim();
      var phoneVal = document.getElementById('phone').value.replace(/[^0-9]/g, '').trim();

      if (!nameVal) { alert('Enter your name'); return; }
      // Auto-fix: if starts with 0, prepend 20 (Egypt)
      if (phoneVal.startsWith('0')) { phoneVal = '20' + phoneVal.substring(1); }
      // Validate: must be 20 + 10 digits = 12 digits total, starting with 20
      if (!/^20\d{10}$/.test(phoneVal)) {
        alert('Phone must be in format: 201XXXXXXXXX\n(Country code 20 + 10-digit number)\n\nExample: 201154069714');
        return;
      }

      chrome.storage.local.set({ phone: phoneVal, name: nameVal }, function() {
        show('v-canvas');
      });
    });
  }

  // Done button
  var doneBtn = document.getElementById('doneBtn');
  if (doneBtn) {
    doneBtn.addEventListener('click', function() {
      var msg = document.getElementById('statusMsg');
      msg.style.display = 'block';
      msg.className = 'msg info';
      msg.textContent = 'Grabbing your Canvas session...';

      chrome.storage.local.get(['phone', 'name'], function(data) {
        chrome.cookies.getAll({ domain: 'aucegypt.instructure.com' }, function(cookies) {
          if (!cookies || cookies.length === 0) {
            msg.textContent = 'No Canvas cookies found. Log into Canvas first.';
            return;
          }

          var cookieList = [];
          for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i];
            cookieList.push({
              name: c.name,
              value: c.value,
              domain: c.domain,
              path: c.path,
              httpOnly: c.httpOnly,
              secure: c.secure,
              sameSite: c.sameSite === 'unspecified' ? 'Lax' : c.sameSite
            });
          }

          fetch('https://canvas-reminder-auc.fly.dev/api/register-cookies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: data.phone, name: data.name, cookies: cookieList })
          })
          .then(function(resp) { return resp.json(); })
          .then(function(result) {
            if (result.success) {
              chrome.storage.local.set({ connected: true });
              show('v-done');
            } else {
              msg.textContent = result.error || 'Failed. Try again.';
            }
          })
          .catch(function(err) {
            msg.textContent = 'Error: ' + err.message;
          });
        });
      });
    });
  }

});
