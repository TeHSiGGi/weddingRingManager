# websocket_utils.py

# List to store active WebSocket connections
connections = []

# Expose a function that can be used to send a message to all connected clients
def broadcast(data):
    for conn in connections:
        conn.send(data)