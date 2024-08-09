import asyncio
import websockets
from transitions import Machine
from gpioConstants import *
import RPi.GPIO as GPIO
from time import sleep
import threading
import requests
import subprocess
import random
import time
import os

# Function to get the current phone interface status
# This function reads the GPIOs for the phone interface
# The GPIOs are connected to the line interface of the phone
# The function returns the current state of the phone interface
# The states are 'ON_HOOK', 'OFF_HOOK', or 'INVALID_STATE'
def getCurrentPhoneInterfaceStatus():
    upperThreshold = GPIO.input(GPIO_LA_UPPER)
    lowerThreshold = GPIO.input(GPIO_LA_LOWER)
    if upperThreshold == GPIO.HIGH and lowerThreshold == GPIO.HIGH:
        return "ON_HOOK"
    elif upperThreshold == GPIO.LOW and lowerThreshold == GPIO.HIGH:
        return "OFF_HOOK"
    else:
        return "INVALID_STATE"

# Define the state machine class
class PhoneStateMachine:
    # Define the states of the state machine
    states = ['onHook', 'offHook', 'ringing']

    # Initialize the state machine
    # The state machine is initialized with the states defined above
    def __init__(self, loop):
        self.loop = loop  # Reference to the event loop
        # Initialize the state machine
        self.machine = Machine(model=self, states=PhoneStateMachine.states, initial='onHook')
        
        # Add transitions
        self.machine.add_transition(trigger='pick_up', source='onHook', dest='offHook')
        self.machine.add_transition(trigger='hang_up', source='offHook', dest='onHook')
        self.machine.add_transition(trigger='incoming_call', source='onHook', dest='ringing')
        self.machine.add_transition(trigger='answer_call', source='ringing', dest='offHook')
        self.machine.add_transition(trigger='miss_call', source='ringing', dest='onHook')

        # Initialize websocket attribute
        self.websocket = None

        # Initialize recording and playback processes
        self.recording_process = None
        self.playback_process = None

        # Initialize recording filename
        self.recording_filename = None

        # Initialize debug state attribute
        self.debug = False

        # Setup GPIO event detection
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # GPIOs for phone interface
        GPIO.setup(GPIO_LA_UPPER, GPIO.IN)
        GPIO.setup(GPIO_LA_LOWER, GPIO.IN)
        GPIO.setup(GPIO_RING_RELAY, GPIO.OUT)
        # GPIOs for LEDs
        GPIO.setup(GPIO_ON_HOOK, GPIO.OUT)
        GPIO.setup(GPIO_OFF_HOOK, GPIO.OUT)
        GPIO.setup(GPIO_HEARTBEAT_A, GPIO.OUT)
        # Add event detection for the phone interface
        GPIO.add_event_detect(GPIO_LA_UPPER, GPIO.BOTH, callback=self.phoneInterfaceCallback)

        # Start the heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self.heartbeat, daemon=True)
        self.heartbeat_thread.start()

        # Message index
        self.message_index = 0

        # Initialize an default config
        self.config = {
            'autoRing': False,
            'autoRingMinSpan': 60,
            'autoRingMaxSpan': 600,
            'ringOnTime': 1,
            'ringOffTime': 1,
            'ringCount': 4,
            'messages': True,
            'randomMessages': True
        }

        # Run auto ring daemon
        self.start_auto_ringing()


    # Wait overall N seconds, but do it in 0.1s intervals
    # and check interface status in between
    async def waitAfterRing(self, time):
        for _ in range(int(time / 0.1)):
            await asyncio.sleep(0.1)
            # Before we wait to ring again, we check if the interface tells us the phone is off-hook
            if getCurrentPhoneInterfaceStatus() == 'OFF_HOOK':
                print("Phone is off-hook, stopping ringer")
                self.answer_call()
                return True
        return False

    # This function will toggle the ringer
    # The ringer will ring for 2 seconds and then wait for 2 seconds
    # This will be repeated 4 times
    # If the phone is picked up during this time, the ringer will stop
    # If the phone is not picked up, the ringer will stop
    async def toggle_ringer(self):
        print("Toggling ringer")
        for _ in range(self.config['ringCount']):
            # We ring the bell
            # Before we ring again, we check if the interface tells us the phone is off-hook
            if getCurrentPhoneInterfaceStatus() == 'OFF_HOOK':
                print("Phone is off-hook, stopping ringer")
                self.answer_call()
                return
            GPIO.output(GPIO_RING_RELAY, GPIO.HIGH)
            await asyncio.sleep(self.config['ringOnTime'])
            GPIO.output(GPIO_RING_RELAY, GPIO.LOW)
            # We wait for a while before ringing again
            waitResult = await self.waitAfterRing(self.config['ringOffTime'])
            if waitResult:
                return

        # If we reach this point, we missed the call
        # Make sure we stop the ringer
        GPIO.output(GPIO_RING_RELAY, GPIO.LOW)
        print("No one picked up, we missed the call")
        self.miss_call()
        
    # Callback function for the phone interface
    # This function is called when the phone interface changes state
    # It will check the current state of the phone interface and transition the state machine accordingly
    # The function will only check the interface if the state is not ringing
    def phoneInterfaceCallback(self, channel):
        # We only check the interface if we're not in state ringing
        if self.state != 'ringing':
            newState = getCurrentPhoneInterfaceStatus()
            sleep(0.3)
            newStateCheck = getCurrentPhoneInterfaceStatus()
            if newState == newStateCheck:
                print(f"Phone interface returned {newState}")
                if newState == 'ON_HOOK' and self.state == 'offHook':
                    asyncio.run_coroutine_threadsafe(self.transition_to_hang_up(), self.loop)
                elif newState == 'OFF_HOOK' and self.state == 'onHook':
                    asyncio.run_coroutine_threadsafe(self.transition_to_pick_up(), self.loop)
                else:
                    print('This state transition is not supported')
            else:
                print("Interface status is not stable, retrying...")
        # else:
        #     print("Phone is ringing, no need to check interface status")

    # Transition to hang up state
    async def transition_to_hang_up(self):
        print("Transitioning to hang up")
        self.hang_up()
    
    # Transition to pick up state
    async def transition_to_pick_up(self):
        print("Transitioning to pick up")
        self.pick_up()

    # Transition to ringing state
    async def transition_to_ringing(self):
        print("Transitioning to ringing")
        self.incoming_call()

    # This function is called when the state machine enters the onHook state
    # It will set the GPIOs to the correct state and send a message to the server
    # The function will also stop recording and playback
    def on_enter_onHook(self):
        print("Entering onHook state")
        GPIO.output(GPIO_ON_HOOK, GPIO.HIGH)
        GPIO.output(GPIO_OFF_HOOK, GPIO.LOW)
        # Example use of the websocket
        asyncio.create_task(self.send_message("STATUS:ON_HOOK"))

        if self.debug == False:
            # Stop recording and playback when entering onHook
            self.stop_recording()
            self.stop_playback()

    # This function is called when the state machine enters the offHook state
    # It will set the GPIOs to the correct state and send a message to the server
    # The function will also start recording and playback
    # The recording is done in a separate process
    # The playback is done in a separate process
    def on_enter_offHook(self):
        print("Entering offHook state")
        GPIO.output(GPIO_ON_HOOK, GPIO.LOW)
        GPIO.output(GPIO_OFF_HOOK, GPIO.HIGH)
        asyncio.create_task(self.send_message('STATUS:OFF_HOOK'))

        if self.debug == False:
            # Start recording and playback
            self.start_recording()
            self.start_playback()

    # This function is called when the state machine enters the ringing state
    # It will set the GPIOs to the correct state and send a message to the server
    # The function will also start the ringer
    def on_enter_ringing(self):
        GPIO.output(GPIO_ON_HOOK, GPIO.LOW)
        GPIO.output(GPIO_OFF_HOOK, GPIO.LOW)
        print("Entering ringing state")
        asyncio.create_task(self.send_message('STATUS:RINGING'))
        asyncio.create_task(self.toggle_ringer())

    # Connect to the WebSocket server
    # This function will keep trying to connect to the server
    async def connect_to_websocket(self, uri):
        while True:
            try:
                print("Connecting to WebSocket...")
                async with websockets.connect(uri) as websocket:
                    print("Connected to WebSocket.")
                    self.websocket = websocket
                    # Start the message listener
                    await asyncio.gather(self.listen_for_messages(), self.run_state_machine())
                    # Get the latest config
                    self.get_latest_config()
                    break  # Exit the loop if the connection was successful
            except Exception as e:
                print(f"Connection failed: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)

    # Listen for incoming websocket messages from the server
    async def listen_for_messages(self):
        try:
            async for message in self.websocket:
                message = message.strip()
                print(f"Received message: {message}")
                # Handle incoming messages here
                # This command will ring the phone with the correct ringing logic
                if message == "COMMAND:RING":
                    if self.state == 'onHook':
                        self.incoming_call()
                    else:
                        print('Can not ring, since we are already off-hook.')
                # This command will force us to get the latest config
                elif message == "COMMAND:UPDATE_CONFIG":
                    print("Received config update command")
                    # Handle the config update command here
                    await self.send_message("STATUS:CONFIG_UPDATED")
                    self.get_latest_config()
                # This command will send the current status to the server
                elif message == "COMMAND:SEND_STATUS":
                    print("Received status request command")
                    # Send the current status to the server
                    if self.state == 'onHook':
                        await self.send_message('STATUS:ON_HOOK')
                    elif self.state == 'offHook':
                        await self.send_message('STATUS:OFF_HOOK')
                    elif self.state == 'ringing':
                        await self.send_message('STATUS:RINGING')
                # This command will play a message to the user
                elif message.startswith("COMMAND:START_PLAYBACK"):
                    print("Received play message command")
                    if self.state == 'offHook':
                        # Play a message
                        # The message should be in the format "COMMAND:START_PLAYBACK:<message_id>"
                        parts = message.split(":")
                        if len(parts) == 3:
                            message_id = parts[2]
                            print(f"Playing message with ID: {message_id}")
                            await self.send_message("STATUS:DEBUG:START_PLAYBACK:" + message_id)
                            # Get the message from the server
                            response = requests.get(f"http://localhost:8080/messages/{message_id}/binary")
                            if response.status_code == 200:
                                with open("playback.wav", "wb") as f:
                                    f.write(response.content)
                                self.start_playback()
                            else:
                                print(f"Failed to get message: {response.status_code}")
                        else:
                            print(f"Invalid message format: {message}")
                    else:
                        print("Can not play message, since we are not off-hook.")
                # This command will stop the playback
                elif message == "COMMAND:STOP_PLAYBACK":
                    print("Received stop playback command")
                    if self.state == 'offHook' and self.playback_process:
                        # Stop the playback
                        await self.send_message("STATUS:DEBUG:STOP_PLAYBACK")
                        self.stop_playback()
                # This command will enable debug mode
                elif message == "COMMAND:DEBUG_ON":
                    print("Received debug on command")
                    await self.send_message("STATUS:DEBUG:ON")
                    self.debug = True
                # This command will disable debug mode
                elif message == "COMMAND:DEBUG_OFF":
                    print("Received debug off command")
                    # send acknowledgement message
                    await self.send_message("STATUS:DEBUG:OFF")
                    self.debug = False
                # This command will start the recording
                elif message == "COMMAND:START_RECORDING":
                    print("Received start recording command")
                    if self.state == 'offHook':
                        # Start recording
                        await self.send_message("STATUS:DEBUG:START_RECORDING")
                        self.start_recording()
                    else:
                        print("Can not start recording, since we are not off-hook.")
                # This command will stop the recording
                elif message == "COMMAND:STOP_RECORDING":
                    print("Received stop recording command")
                    if self.state == 'offHook' and self.recording_process:
                        # Stop the recording
                        await self.send_message("STATUS:DEBUG:STOP_RECORDING")
                        self.stop_recording()
                else:
                    print(f"Unknown command: {message}")
        except Exception as e:
            print(f"Connection closed or error encountered: {e}")

    # Send a websocket message to the server
    async def send_message(self, message):
        if self.websocket:
            try:
                await self.websocket.send(message)
                print(f"Sent message: {message}")
            except Exception as e:
                print(f"Failed to send message, connection closed or error encountered: {e}")

    # Run the state machine
    async def run_state_machine(self):
        print(f"Current state: {self.state}")

    # Heartbeat function that blinks the heartbeat LED
    # This function runs in a separate thread
    # The heartbeat LED is connected to GPIO_HEARTBEAT_A
    # This is used to indicate that the program is running
    def heartbeat(self):
        while True:
            GPIO.output(GPIO_HEARTBEAT_A, GPIO.HIGH)
            sleep(0.1)
            GPIO.output(GPIO_HEARTBEAT_A, GPIO.LOW)
            sleep(0.4)

    # Starts the actual recording using arecord with the correct settings
    # The recording is saved to a file called recorded.wav
    # The file is recorded in 32-bit signed little-endian format, with a sample rate of 96kHz and 2 channels
    # The recording is started in a separate process, which is stored in the recording_process attribute
    # This allows us to stop the recording later on demand
    def start_recording(self):
        print("Starting recording")
        self.recording_filename = f"recorded_{int(time.time())}.wav"
        self.recording_process = subprocess.Popen([
            'arecord', '-D', 'plughw:0', '-c', '2', '-r', '96000', '-f', 'S32_LE', '-t', 'wav', self.recording_filename
        ])

    # Stops the recording process
    # This is done by terminating the process
    # After stopping the recording, we post-process the recording
    def stop_recording(self):
        print("Stopping recording")
        if self.recording_process:
            self.recording_process.terminate()
            self.recording_process = None
            # Post-process the recording asynchronously
            self.post_process_recording(self.recording_filename)

    # Starts the playback of the message
    # The message is played back using aplay with the correct settings
    # The playback is done in a separate process, which is stored in the playback_process attribute
    # This allows us to stop the playback later on demand
    def start_playback(self):
        if self.config['messages'] == False:
            print("Messages are disabled, can not play message")
            return
        print("Starting playback")
        # Get list of messages from server
        messageList = requests.get("http://localhost:8080/messages").json()
        messageCount = len(messageList)
        # Determine which message to use
        if self.config['randomMessages']:
            # Use a random message
            # The message_index is set to a random number between 0 and the number of messages
            self.message_index = random.randint(0, messageCount - 1)
        else:
            # Use the next message in the list
            # If we reach the end of the list, start over
            # This is done by using the modulo operator
            # The message_index will be incremented by 1 and then taken modulo the messageCount
            # This will result in the message_index being reset to 0 when it reaches the end of the list
            self.message_index = (self.message_index + 1) % messageCount
        # Get the message ID from the message list
        message_id = messageList[self.message_index]['id']
        print(f"Playing message with ID: {message_id}")
        # # Get the message from the server
        # response = requests.get(f"http://localhost:8080/messages/{message_id}/binary")
        if response.status_code == 200:
            with open("playback.wav", "wb") as f:
                f.write(response.content)
            # Start the playback process
            self.playback_process = subprocess.Popen([
                'aplay', '-D', 'plughw:0', '-c', '2', '-r', '96000', '-f', 'S32_LE', "/home/pi/weddingRingManager/server/messages/{message_id}.wav"
            ])
        else:
            print(f"Failed to get message: {response.status_code}")

    # Stops the playback process
    # This is done by terminating the process
    def stop_playback(self):
        print("Stopping playback")
        if self.playback_process:
            self.playback_process.terminate()
            self.playback_process = None

    # Upload the recording to the server
    # This function will upload the recording to the server
    # The recording is uploaded as a file to the server
    def upload_recording(self, file_path):
        try:
            with open(file_path, "rb") as f:
                response = requests.post("http://localhost:8080/records", files={"file": f})
            if response.status_code == 201:
                print("Upload successful")
            else:
                print(f"Upload failed with status code: {response.status_code}")
        except Exception as e:
            print(f"Failed to upload recording: {e}")
        finally:
            # Delete the file after uploading
            os.remove(file_path)
            print(f"Deleted file: {file_path}")

    # Post-process the recording
    # This function is called after the recording has been stopped
    def post_process_recording(self, file_path):
        print("Post-processing recording")
        threading.Thread(target=self.upload_recording, args=(file_path,), daemon=True).start()

    # Get the latest config from the server and apply it
    # This function sends a request to the server to get the latest config
    # The config is stored in the config attribute
    def get_latest_config(self):
        response = requests.get("http://localhost:8080/config")
        if response.status_code == 200:
            self.config = response.json()
            print("Received config:", self.config)
        else:
            print("Failed to get config:", response.status_code)

    # Starts a separate thread that will perform the randomized ringing
    # The ringing will be done according to the config settings
    # The ringing will be done in a separate thread to not block the main thread
    def start_auto_ringing(self):
        print("Starting auto ringing daemon")
        threading.Thread(target=self.auto_ringing_thread, daemon=True).start()

    # The auto ringing thread function
    # This function will perform the randomized ringing
    # The ringing will be done according to the config settings
    def auto_ringing_thread(self):
        while True:
            if self.config['autoRing'] and self.debug == False:
                # Calculate the random time to wait
                wait_time = random.randint(self.config['autoRingMinSpan'] * 60, self.config['autoRingMaxSpan'] * 60)
                print(f"Waiting {wait_time} seconds before ringing")
                sleep(wait_time)
                if self.state == 'onHook':
                    asyncio.run_coroutine_threadsafe(self.transition_to_ringing(), self.loop)
                else:
                    print("Can not ring, since we are already off-hook.")
            else:
                sleep(10)

# Main function
async def main():
    loop = asyncio.get_running_loop()
    phone = PhoneStateMachine(loop)
    await phone.connect_to_websocket("ws://localhost:8080/socket")

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
