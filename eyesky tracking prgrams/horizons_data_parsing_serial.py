import numpy as np
import serial
import time
import pytz
from datetime import datetime, timezone, timedelta

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
                time.sleep(1)  # Wait for port to be released
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=5)
            time.sleep(2)  # Wait for ESP32 to initialize after serial connection
            connected = True
            print("Successfully connected to ESP32.")
        except (serial.SerialException, PermissionError, OSError) as e:
            print(f"Failed to connect to ESP32: {e}. Will retry later.")
            ser = None
            connected = False
            return  # Don't try to send if not connected
    
    # If connected, try to send the data
    if connected:
        try:
            ser.write((cmd + "\n").encode())
            time.sleep(0.1)  # Keep the original delay
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


with open('C:/Users/Owner/Downloads/horizons_results (14).txt', 'r') as file:
    data = file.read()

print("Data loaded from file.")

def parse_ephemeris_tuples(data_string):
    results = []
    lines = data_string.split('\n')
    in_data = False
    
    # Create UTC+10 timezone object
    tz = pytz.FixedOffset(10 * 60) # 10 hours * 60 minutes
    
    for line in lines:
        line = line.strip()
        
        if line == '$$SOE':
            in_data = True
            continue
        if line == '$$EOE':
            break
            
        if not in_data or not line or line.startswith('>'):
            continue
        
        parts = [p.strip() for p in line.split(',')]
        
        if len(parts) >= 5:
            try:
                # Parse datetime and set to UTC+10
                dt_naive = datetime.strptime(parts[0], '%Y-%b-%d %H:%M:%S.000')
                dt_aware = tz.localize(dt_naive)
                
                unix_time = int(dt_aware.timestamp())
                az = float(parts[3])
                el = float(parts[4])
                results.append((unix_time, az, el))
            except (ValueError, IndexError):
                continue
    return results

# Usage:
parsed = parse_ephemeris_tuples(data)

while True:
    current_sec = int(time.time())  # CRITICAL: Must floor to integer seconds (matches your list's integer timestamps)
    for entry in parsed:
        if entry[0] == current_sec:  # Exact second match (works even with irregular gaps)
            print(f"MATCH: {entry} (Unix time {entry[0]} = UTC {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(entry[0]))})")
            send_position(f"AZ:{entry[1]} ALT:{entry[2]}")
    time.sleep(1)  # Check exactly once per second (optimal for integer timestamps - never misses)
