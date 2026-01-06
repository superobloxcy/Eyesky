import numpy as np
import socket
import time

ESP32_IP = "192.168.1.56"
ESP32_PORT = 10000

sock = None
connected = False

def send_position(cmd):
    """
    Sends a command to the ESP32. Manages connection and reconnection attempts.
    """
    global sock, connected # Declare intent to modify global variables
    
    print(f"---> {cmd}")
    
    # Try to establish connection if not already connected
    if not connected:
        print(f"Attempting to connect to ESP32 at {ESP32_IP}:{ESP32_PORT}...")
        try:
            # Ensure any previous broken socket is closed before creating a new one
            if sock:
                sock.close() 
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set a timeout for connect to prevent hanging indefinitely
            sock.settimeout(5) 
            sock.connect((ESP32_IP, ESP32_PORT))
            connected = True
            print("Successfully connected to ESP32.")
            # Revert to blocking or set a specific send timeout if preferred
            # sock.settimeout(None) # Can remove this if 5s timeout is acceptable for sends too
        except (ConnectionRefusedError, OSError) as e:
            print(f"Failed to connect to ESP32: {e}. Will retry later.")
            sock = None # Ensure sock is None if connection failed
            connected = False
            return # Don't try to send if not connected
    
    # If connected, try to send the data
    if connected:
        try:
            sock.sendall((cmd+"\n").encode())
            time.sleep(0.05) # Keep the original delay
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(f"Error sending data to ESP32: {e}. Connection lost, will attempt to reconnect next cycle.")
            if sock:
                sock.close() # Close the broken socket
            sock = None
            connected = False
        except Exception as e: # Catch any other unexpected errors during send
            print(f"An unexpected error occurred during send: {e}. Connection might be lost.")
            if sock:
                sock.close()
            sock = None
            connected = False
    else:
        print("Not connected to ESP32, skipping data send.")


A=45
for i in range(541):
    ALT=A*np.cos(np.deg2rad(i*3))
    AZ=45*np.sin(np.deg2rad(i*3))
    print(f'AZ:{AZ:.5f} ALT:{ALT:.5f}')
    cmd=f'AZ:{AZ:.5f} ALT:{ALT:.5f}'
    time.sleep(0.5)
    
    send_position(cmd)