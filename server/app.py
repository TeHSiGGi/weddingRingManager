from flask import Flask
from flasgger import Swagger
from database import init_db, close_connection
from endpoints.records import records_bp
from endpoints.config import config_bp
from endpoints.messages import messages_bp
from flask_sock import Sock
from websocket_utils import connections
import RPi.GPIO as GPIO
import threading
from time import sleep

# Create the Flask app
app = Flask(__name__)
sock = Sock(app)
# Register the teardown function
app.teardown_appcontext(close_connection)

# Register the blueprints
app.register_blueprint(records_bp)
app.register_blueprint(config_bp)
app.register_blueprint(messages_bp)

# Initialize the Swagger extension
swagger = Swagger(app)

# WebSocket route
@sock.route('/socket')
def socket(ws):
    # Add the new connection to the list
    connections.append(ws)
    try:
        while True:
            data = ws.receive()
            if data is None:
                break
            # Broadcast the message to all connected clients
            for conn in connections:
                if conn != ws:
                    conn.send(data)
    finally:
        # Remove the connection when done
        connections.remove(ws)

# Heartbeat function running in a separate thread
# The heartbeat should toggle the Raspberry pi GPIO pin 24
# It is on 0.8 seconds and off 0.2 seconds
def heartbeat():
    while True:
        GPIO.output(24, GPIO.HIGH)
        sleep(0.8)
        GPIO.output(24, GPIO.LOW)
        sleep(0.2)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    # Set up the GPIO pin
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(24, GPIO.OUT)
    GPIO.setwarnings(False)
    # Start the heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    # Run the Flask app
    app.run(debug=True, port=8080, host='0.0.0.0')
