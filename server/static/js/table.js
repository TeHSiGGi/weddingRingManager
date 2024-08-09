// Convert a UNIX timestamp to a human-readable date
function convertTimestampToDate(timestamp) {
  const date = new Date(timestamp * 1000);
  return date.toLocaleString();
}

// Play the audio file with a given ID
// The path parameter is used to determine the path to the binary file
// It can be either 'messages' or 'records'
function playbackEntry(id, path) {
  console.log(`Playback entry with ID: ${id}`);
  // Play the audio file that can be found /messages/:id/binary
  const audio = new Audio(`/${path}/${id}/binary`);
  audio.play();
}

// Delete an entry with a given ID
// The path parameter is used to determine the path to the binary file
// It can be either 'messages' or 'records'
function deleteEntry(id, path) {
  console.log(`Delete entry with ID: ${id}`);
  // Send a DELETE request to /messages/:id
  fetch(`/${path}/${id}`, {
    method: 'DELETE'
  }).then(response => {
    if (response.ok) {
      if (path === 'messages') {
        getMessagesData();
      } else {
        getRecordingsData();
      }
    }
  });
}

// Populate the table with data
// The path parameter is used to determine the path to the binary file
// It can be either 'messages' or 'records'
function populateTable(data, path) {
  const tableBody = document.querySelector('#dataTable tbody');
  tableBody.innerHTML = ''; // Clear any existing rows

  data.forEach(item => {
      const row = document.createElement('tr');

      const idCell = document.createElement('td');
      idCell.textContent = item.id;
      row.appendChild(idCell);

      const lengthCell = document.createElement('td');
      lengthCell.textContent = (item.length / 1000).toFixed(2);
      row.appendChild(lengthCell);

      const recordDateCell = document.createElement('td');
      recordDateCell.textContent = convertTimestampToDate(item.recordTimestamp);
      row.appendChild(recordDateCell);

      const actionsCell = document.createElement('td');
      const actionsContainer = document.createElement('div');
      actionsContainer.classList.add('action-buttons');
      
      const playbackButton = document.createElement('button');
      playbackButton.textContent = '▶️'; // Playback icon
      playbackButton.onclick = () => playbackEntry(item.id, path);
      actionsContainer.appendChild(playbackButton);
      
      const deleteButton = document.createElement('button');
      deleteButton.textContent = '❌'; // Delete icon
      deleteButton.onclick = () => {
        if (confirm('Are you sure you want to delete this item?')) {
          deleteEntry(item.id, path);
        }
      }
      actionsContainer.appendChild(deleteButton);

      const downloadButton = document.createElement('button');
      downloadButton.textContent = '⬇️'; // Download icon
      downloadButton.onclick = () => {
        window.open(`/${path}/${item.id}/binary`);
      };
      actionsContainer.appendChild(downloadButton);
      
      actionsCell.appendChild(actionsContainer);
      row.appendChild(actionsCell);

      tableBody.appendChild(row);
  });
}

function getMessagesData() {
  // Run a GET request to /messages to get the data
  fetch('/messages')
    .then(response => response.json())
    .then(data => {
      populateTable(data, 'messages');
    });
}

function getRecordingsData() {
  // Run a GET request to /recordings to get the data
  fetch('/records')
    .then(response => response.json())
    .then(data => {
      populateTable(data, 'records');
    });
}
