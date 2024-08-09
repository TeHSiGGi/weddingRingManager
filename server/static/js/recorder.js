
// Get the controls we need to check
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const saveBtn = document.getElementById('saveBtn');
const discardBtn = document.getElementById('discardBtn');
const volumeControl = document.getElementById('volumeControl');
const playback = document.getElementById('playback');

// Variables to store the recorded audio
let mediaRecorder;
let audioChunks = [];
let recordedBlob;

// Add listener to the start button
startBtn.addEventListener('click', async () => {
  // Build the audio context and add a gain node to it so we can control the volume
  let audioContext = new (window.AudioContext || window.webkitAudioContext)();
  let gainNode = audioContext.createGain();
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const source = audioContext.createMediaStreamSource(stream);
  source.connect(gainNode);

  const destination = audioContext.createMediaStreamDestination();
  gainNode.connect(destination);

  // The gain will be taken from the volume control input
  gainNode.gain.value = volumeControl.value;

  // Clear the audio chunks and create a new media recorder
  audioChunks = [];
  mediaRecorder = new MediaRecorder(destination.stream);

  // When the recorder has data available, add it to the audio chunks
  mediaRecorder.ondataavailable = (event) => {
    audioChunks.push(event.data);
  };

  // When the recorder is stopped, create a blob from the audio chunks
  mediaRecorder.onstop = async () => {
    // Create a blob from the audio chunks
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    // Create an array buffer from the blob
    const arrayBuffer = await audioBlob.arrayBuffer();
    // Decode the audio buffer from the array buffer
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

    // Create an offline audio context to render the audio buffer at a higher sample rate
    const offlineContext = new OfflineAudioContext({
      numberOfChannels: audioBuffer.numberOfChannels,
      length: audioBuffer.length * 96000 / audioBuffer.sampleRate,
      sampleRate: 96000 // 96kHz
    });

    // Create a buffer source node and connect it to the offline context
    const source = offlineContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineContext.destination);
    source.start();

    // Start rendering the audio buffer
    const renderedBuffer = await offlineContext.startRendering();
    const wavBlob = bufferToWav(renderedBuffer, 32); // 32-bit depth
    const url = URL.createObjectURL(wavBlob);
    recordedBlob = wavBlob;

    playback.src = url;
    downloadLink.href = url;
    downloadLink.download = 'recording.wav';
  };

  // Start the media recorder
  mediaRecorder.start();
  // Disable controls
  startBtn.disabled = true;
  stopBtn.disabled = false;
  saveBtn.disabled = true;
  discardBtn.disabled = true;

});

// Add listener to the stop button
stopBtn.addEventListener('click', () => {
  // Stop the recording
  mediaRecorder.stop();
  // Configure controls
  startBtn.disabled = true;
  stopBtn.disabled = true;
  saveBtn.disabled = false;
  discardBtn.disabled = false;
});

// Add listener to the save button
saveBtn.addEventListener('click', () => {
  // Create a form data object
  const formData = new FormData();
  // Append the audio blob to the form data
  formData.append('file', recordedBlob, 'recording.wav');
  // Send the form data to the server
  fetch('/messages', {
    method: 'POST',
    body: formData
  }).then(response => {
    if (response.ok) {
      playback.src = '';
      startBtn.disabled = false;
      stopBtn.disabled = true;
      saveBtn.disabled = true;
      discardBtn.disabled = true;
      alert('Audio saved successfully!');
      getMessagesData();
    }
  });
});

// Add listener to the discard button
discardBtn.addEventListener('click', () => {
  // Clear the audio chunks
  audioChunks = [];
  // Configure controls
  startBtn.disabled = false;
  stopBtn.disabled = true;
  saveBtn.disabled = true;
  discardBtn.disabled = true;
  playback.src = '';
});

// Function to convert a buffer to a wav file
function bufferToWav(buffer, bitDepth) {
  let numOfChan = buffer.numberOfChannels,
    length = buffer.length * numOfChan * (bitDepth / 8),
    bufferLength = buffer.length,
    result = new ArrayBuffer(44 + length),
    view = new DataView(result),
    channels = [],
    i,
    sample,
    offset = 0,
    pos = 0;

  setUint32(0x46464952); // "RIFF"
  setUint32(length + 36); // file length - 8
  setUint32(0x45564157); // "WAVE"

  setUint32(0x20746d66); // "fmt " chunk
  setUint32(16); // length = 16
  setUint16(1); // PCM (uncompressed)
  setUint16(numOfChan);
  setUint32(buffer.sampleRate);
  setUint32(buffer.sampleRate * numOfChan * (bitDepth / 8)); // avg. bytes/sec
  setUint16(numOfChan * (bitDepth / 8)); // block-align
  setUint16(bitDepth); // 32-bit

  setUint32(0x61746164); // "data" - chunk
  setUint32(length);

  // Write interleaved data
  for (i = 0; i < buffer.numberOfChannels; i++)
    channels.push(buffer.getChannelData(i));

  while (pos < bufferLength) {
    for (i = 0; i < numOfChan; i++) { // interleave channels
      sample = Math.max(-1, Math.min(1, channels[i][pos])); // clamp
      sample = (sample < 0 ? sample * 0x80000000 : sample * 0x7FFFFFFF) | 0; // scale to 32-bit
      view.setInt32(offset, sample, true); // write 32-bit sample
      offset += 4;
    }
    pos++;
  }

  return new Blob([result], { type: 'audio/wav' });

  function setUint16(data) {
    view.setUint16(offset, data, true);
    offset += 2;
  }

  function setUint32(data) {
    view.setUint32(offset, data, true);
    offset += 4;
  }
}