// Connect to WebSocket server
var socket = new WebSocket("wss://" + window.location.host + "/socket");

// Send message to WebSocket server
function sendWebSocketMessage() {
    var message = document.getElementById("message").value;
    var messages = document.getElementById("webSocketMessages");
    socket.send(message);
    if (message) {
        messages.innerHTML += "<br><span class='localMessage'>" + message + "</span>";
    }
}

// Receive message from WebSocket server
socket.onmessage = function(event) {
    var messages = document.getElementById("webSocketMessages");
    if (messages) {
        messages.innerHTML += "<br><span class='remoteMessage'>" + event.data + "</span>";
    }
}