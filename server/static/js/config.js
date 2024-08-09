// Initiate the settings form
function loadSettings() {
  fetch('/config')
    .then(response => response.json())
    .then(data => {
      document.getElementById('autoRing').checked = data.autoRing;
      document.getElementById('autoRingMinSpan').value = data.autoRingMinSpan;
      document.getElementById('autoRingMaxSpan').value = data.autoRingMaxSpan;
      document.getElementById('ringOnTime').value = data.ringOnTime;
      document.getElementById('ringOffTime').value = data.ringOffTime;
      document.getElementById('messages').checked = data.messages;
      document.getElementById('randomMessages').checked = data.randomMessages;
      document.getElementById('ringCount').value = data.ringCount;
    })
    .catch((error) => {
      console.error('Error:', error);
    });
}

// Save settings
function saveSettings() {
  const form = document.getElementById('settingsForm');
  const formData = new FormData(form);
  const data = {};

  // Handle checkbox fields separately
  const checkboxes = ['autoRing', 'messages', 'randomMessages'];
  checkboxes.forEach(key => {
    data[key] = formData.has(key) ? true : false;
  });

  // Handle number fields
  formData.forEach((value, key) => {
    if (!checkboxes.includes(key)) {
      data[key] = !isNaN(Number(value)) ? Number(value) : value;
    }
  });

  fetch('/config', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })
    .then(response => response.json())
    .then(data => {
      alert('Settings saved successfully!');
    })
    .catch((error) => {
      console.error('Error:', error);
    });
}