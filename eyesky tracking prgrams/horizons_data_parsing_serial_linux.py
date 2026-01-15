#!/usr/bin/env python3
import numpy as np
import serial
import time
import pytz
import os
import glob
import sys
from datetime import datetime, timezone, timedelta

BAUD_RATE_DEFAULT = 115200

ser = None
connected = False


def find_serial_port(preferred=None):
    """Find available serial port with preference for specified port."""
    if preferred:
        return preferred
    env_port = os.environ.get("SERIAL_PORT")
    if env_port:
        return env_port

    if os.name == 'nt':
        return 'COM5'

    patterns = ['/dev/serial/by-id/*', '/dev/ttyUSB*', '/dev/ttyACM*', '/dev/cu.*']
    matches = []
    for p in patterns:
        matches.extend(glob.glob(p))
    matches = sorted(matches)
    return matches[0] if matches else None


def send_position(cmd, port, baud):
    """Send command over serial, handling reconnects."""
    global ser, connected
    print(f"---> {cmd}")

    if not connected:
        try:
            if ser:
                ser.close()
            ser = serial.Serial(port, baud, timeout=5)
            time.sleep(2)
            connected = True
            print(f"Connected to {port} at {baud} baud.")
        except (serial.SerialException, OSError) as e:
            msg = str(e)
            print(f"Failed to open {port}: {msg}")
            if 'Permission denied' in msg or getattr(e, 'errno', None) == 13:
                print("Permission denied when opening the serial port.")
                print("Suggested fixes:")
                print(" - Add your user to the 'dialout' group: sudo usermod -a -G dialout $USER")
                print("   then re-login or run: newgrp dialout")
                print(" - Temporary test: sudo chmod 666 {0}".format(port))
                print(" - Create a udev rule for persistent permissions (see udevadm info for ids).")
                print("Or run the script with sudo (not recommended long-term).")
            ser = None
            connected = False
            return

    if connected:
        try:
            ser.write((cmd + "\n").encode())
            time.sleep(0.1)
        except (serial.SerialException, OSError) as e:
            print(f"Error sending data: {e}. Will reconnect next loop.")
            if ser:
                ser.close()
            ser = None
            connected = False
        except Exception as e:
            print(f"Unexpected error during send: {e}")
            if ser:
                ser.close()
            ser = None
            connected = False


def cleanup():
    """Close serial connection on exit."""
    global ser, connected
    if ser:
        try:
            ser.close()
        except Exception:
            pass
    connected = False
    print("Serial connection closed.")


def parse_ephemeris_tuples(data_string):
    """Parse Horizons ephemeris data."""
    results = []
    lines = data_string.split('\n')
    in_data = False
    
    # Create UTC+10 timezone object
    tz = pytz.FixedOffset(10 * 60)  # 10 hours * 60 minutes
    
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


def main():
    # Load ephemeris data
    data_file = 'C:/Users/Owner/Downloads/horizons_results (14).txt'
    try:
        with open(data_file, 'r') as file:
            data = file.read()
        print(f"Data loaded from file: {data_file}")
    except FileNotFoundError:
        print(f"Error: File not found: {data_file}")
        sys.exit(1)

    parsed = parse_ephemeris_tuples(data)
    if not parsed:
        print("Error: No valid ephemeris data parsed from file.")
        sys.exit(1)
    print(f"Parsed {len(parsed)} ephemeris entries.")

    # Find serial port
    port = find_serial_port()
    if not port:
        print("No serial port found.")
        print("Set SERIAL_PORT env var or connect your device.")
        candidates = []
        for p in ['/dev/serial/by-id/*', '/dev/ttyUSB*', '/dev/ttyACM*', '/dev/cu.*']:
            candidates.extend(glob.glob(p))
        if candidates:
            print("Available candidates:")
            for c in sorted(candidates):
                print(" -", c)
        sys.exit(1)

    print(f"Using serial port: {port} at {BAUD_RATE_DEFAULT} baud")

    try:
        while True:
            current_sec = int(time.time())
            for entry in parsed:
                if entry[0] == current_sec:
                    print(f"MATCH: {entry} (Unix time {entry[0]} = UTC {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(entry[0]))})")
                    out = f"AZ:{entry[1]} ALT:{entry[2]}"
                    send_position(out, port, BAUD_RATE_DEFAULT)
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nInterrupted by user.')
    finally:
        cleanup()


if __name__ == '__main__':
    main()
