import numpy as np
import serial
import time
import sys
# Serial port configuration
SERIAL_PORT = "COM5"  # Change this to your ESP32's COM port
BAUD_RATE = 115200

ser = None
connected = False

def send_position(cmd):
    """
    Sends a command to the ESP32 via serial port. Manages connection and reconnection attempts.
    """
    global ser, connected
    
    print(f"---> {cmd}")
    
    # Try to establish connection if not already connected
    if not connected:
        print(f"Attempting to connect to ESP32 on {SERIAL_PORT} at {BAUD_RATE} baud...")
        try:
            # Ensure any previous broken serial connection is closed before creating a new one
            if ser:
                ser.close()
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=5)
            time.sleep(2)  # Wait for ESP32 to initialize after serial connection
            connected = True
            print("Successfully connected to ESP32.")
        except (serial.SerialException, OSError) as e:
            print(f"Failed to connect to ESP32: {e}. Will retry later.")
            ser = None
            connected = False
            return  # Don't try to send if not connected
    
    # If connected, try to send the data
    if connected:
        try:
            ser.write((cmd + "\n").encode())
            time.sleep(0.05)  # Keep the original delay
        except (serial.SerialException, OSError) as e:
            print(f"Error sending data to ESP32: {e}. Connection lost, will attempt to reconnect next cycle.")
            if ser:
                ser.close()
            ser = None
            connected = False
        except Exception as e:  # Catch any other unexpected errors during send
            print(f"An unexpected error occurred during send: {e}. Connection might be lost.")
            if ser:
                ser.close()
            ser = None
            connected = False
    else:
        print("Not connected to ESP32, skipping data send.")


def cleanup():
    """Close serial connection on exit"""
    global ser, connected
    if ser:
        ser.close()
        connected = False
        print("\nSerial connection closed.")


# Main tracking loop
A = 45
try:
    for i in range(1081):
        ALT = A * np.cos(np.deg2rad(i/2))
        AZ = 45 * np.sin(np.deg2rad(i/2))
        print(f'AZ:{AZ:.5f} ALT:{ALT:.5f}')
        cmd = f'AZ:{AZ:.5f} ALT:{ALT:.5f}'
        time.sleep(0.025)
        
        send_position(cmd)
except KeyboardInterrupt:
    print("\nTracking interrupted by user.")
finally:
    cleanup()
