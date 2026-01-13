#!/usr/bin/env python3
import numpy as np
import serial
import time
import os
import glob
import argparse
import sys

BAUD_RATE_DEFAULT = 115200

ser = None
connected = False


def find_serial_port(preferred=None):
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
            time.sleep(0.05)
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
    global ser, connected
    if ser:
        try:
            ser.close()
        except Exception:
            pass
    connected = False
    print("Serial connection closed.")


def main():
    parser = argparse.ArgumentParser(description='Linux-friendly circle-test serial sender')
    parser.add_argument('--port', help='Serial port to use (e.g. /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=BAUD_RATE_DEFAULT, help='Baud rate')
    parser.add_argument('--retry', action='store_true', help='Keep retrying until device appears')
    parser.add_argument('--simulate', action='store_true', help='Do not open serial; just print commands')
    args = parser.parse_args()

    port = find_serial_port(args.port)
    if not port and not args.retry and not args.simulate:
        print("No serial port found.")
        print("Set SERIAL_PORT env var, use --port, or run with --retry to wait for a device.")
        # list candidates
        candidates = []
        for p in ['/dev/serial/by-id/*', '/dev/ttyUSB*', '/dev/ttyACM*', '/dev/cu.*']:
            candidates.extend(glob.glob(p))
        if candidates:
            print("Available candidates:")
            for c in sorted(candidates):
                print(" -", c)
        sys.exit(1)

    if args.retry and not args.simulate:
        while not port:
            print("Waiting for serial device...")
            time.sleep(2)
            port = find_serial_port(args.port)

    if args.simulate:
        print("Running in simulation mode (no serial).")
    else:
        print(f"Using serial port: {port} at {args.baud} baud")

    A = 45
    try:
        for i in range(1081):
            ALT = A * np.cos(np.deg2rad(i/12))
            AZ = 90 * np.sin(np.deg2rad(3*i))
            out = f'AZ:{AZ:.5f} ALT:{ALT:.5f}'
            print(out)
            if args.simulate:
                time.sleep(0.025)
                continue
            send_position(out, port, args.baud)
            time.sleep(0.025)
    except KeyboardInterrupt:
        print('\nInterrupted by user.')
    finally:
        cleanup()


if __name__ == '__main__':
    main()
