#!/usr/bin/env python3
import time
import re
import os
import sys
import glob
import numpy as np
import serial
import threading
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from collections import deque
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions

BAUD_RATE_DEFAULT = 115200

ser = None
connected = False

# Global variable for prediction time (seconds)
prediction_time = 0.0
prediction_lock = threading.Lock()

# Global variables for plotting data (thread-safe)
plot_data_lock = threading.Lock()
MAX_POINTS = 100  # Maximum number of points to display

# Data storage for plotting
actual_positions = deque(maxlen=MAX_POINTS)
predicted_positions = deque(maxlen=MAX_POINTS)
prediction_errors = deque(maxlen=MAX_POINTS)  # Actual prediction errors
error_timestamps = deque(maxlen=MAX_POINTS)   # Timestamps for errors
timestamps = deque(maxlen=MAX_POINTS)
start_time = None

# Buffer to store predictions for later comparison
# Format: {timestamp: (predicted_lat, predicted_lon, prediction_time_used)}
prediction_buffer = {}
BUFFER_MAX_AGE = 30  # Keep predictions for up to 30 seconds

# Current values for display
current_error = 0.0
current_actual = (0.0, 0.0)
current_predicted = (0.0, 0.0)
avg_error = 0.0

# Home position (will be loaded from config)
home_lat = None
home_lon = None
home_alt = None


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


def load_config(config_path):
    """Load configuration from file."""
    global home_lat, home_lon, home_alt
    
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('home_lat='):
                    home_lat = float(line.split('=')[1])
                elif line.startswith('home_lon='):
                    home_lon = float(line.split('=')[1])
                elif line.startswith('home_alt='):
                    home_alt = float(line.split('=')[1])
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    except ValueError:
        print("Error: Invalid values in config.txt")
        sys.exit(1)

    if home_lat is None or home_lon is None or home_alt is None:
        print("Error: Could not load home position from config.txt")
        sys.exit(1)


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees).
    Returns distance in meters.
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    # Earth's radius in meters
    r = 6371000
    return c * r


def update_plot_data(actual_lat, actual_lon, predicted_lat, predicted_lon, pred_time_used):
    """
    Thread-safe update of plot data.
    Stores current prediction and checks past predictions against current actual position.
    """
    global start_time, current_error, current_actual, current_predicted, avg_error, prediction_buffer
    
    with plot_data_lock:
        if start_time is None:
            start_time = time.time()
        
        current_time = time.time() - start_time
        absolute_time = time.time()
        
        # Store positions for path plotting
        actual_positions.append((actual_lat, actual_lon, current_time))
        predicted_positions.append((predicted_lat, predicted_lon, current_time))
        timestamps.append(current_time)
        
        current_actual = (actual_lat, actual_lon)
        current_predicted = (predicted_lat, predicted_lon)
        
        # Store this prediction for future comparison
        if pred_time_used > 0:
            prediction_buffer[absolute_time] = (predicted_lat, predicted_lon, pred_time_used)
        
        # Check past predictions against current actual position
        predictions_to_remove = []
        
        for pred_timestamp, (pred_lat, pred_lon, pred_dt) in prediction_buffer.items():
            age = absolute_time - pred_timestamp
            
            # If this prediction's target time has arrived (within a tolerance window)
            time_diff = abs(age - pred_dt)
            
            if time_diff < 0.75:  # Within 0.75 second tolerance
                # Calculate error between what we predicted and where aircraft actually is
                error = haversine_distance(pred_lat, pred_lon, actual_lat, actual_lon)
                
                prediction_errors.append(error)
                error_timestamps.append(current_time)
                current_error = error
                
                predictions_to_remove.append(pred_timestamp)
            
            # Remove old predictions that we'll never match
            elif age > pred_dt + 2:  # More than 2 seconds past target time
                predictions_to_remove.append(pred_timestamp)
            
            # Also remove very old predictions to prevent memory buildup
            elif age > BUFFER_MAX_AGE:
                predictions_to_remove.append(pred_timestamp)
        
        # Clean up processed/old predictions
        for ts in predictions_to_remove:
            del prediction_buffer[ts]
        
        # Calculate average error
        if len(prediction_errors) > 0:
            avg_error = sum(prediction_errors) / len(prediction_errors)


class PlotGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ADS-B Delay Compensation & Tracking (Serial)")
        self.root.geometry("1000x750")
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top control panel
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Prediction time slider
        slider_frame = ttk.Frame(control_frame)
        slider_frame.pack(fill=tk.X)
        
        ttk.Label(slider_frame, text="Prediction Time:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        self.value_label = ttk.Label(slider_frame, text="0.0 s", font=("Arial", 10), width=8)
        self.value_label.pack(side=tk.RIGHT)
        
        self.slider = ttk.Scale(
            slider_frame,
            from_=0,
            to=10,
            orient=tk.HORIZONTAL,
            command=self.on_slider_change,
            length=300
        )
        self.slider.set(0)
        self.slider.pack(side=tk.RIGHT, padx=10)
        
        # Info panel
        info_frame = ttk.LabelFrame(main_frame, text="Current Status", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Grid for info display
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X)
        
        # Error display - prominent
        error_frame = ttk.Frame(info_grid)
        error_frame.pack(fill=tk.X, pady=5)
        
        self.error_label = ttk.Label(
            error_frame, 
            text="Prediction Error: --- m", 
            font=("Arial", 12, "bold"),
            foreground="blue"
        )
        self.error_label.pack(side=tk.LEFT, padx=10)
        
        self.avg_error_label = ttk.Label(
            error_frame, 
            text="Avg Error: --- m", 
            font=("Arial", 11),
            foreground="green"
        )
        self.avg_error_label.pack(side=tk.LEFT, padx=20)
        
        self.buffer_label = ttk.Label(
            error_frame, 
            text="Pending: 0", 
            font=("Arial", 10),
            foreground="gray"
        )
        self.buffer_label.pack(side=tk.RIGHT, padx=10)
        
        # Position info
        pos_frame = ttk.Frame(info_grid)
        pos_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pos_frame, text="Actual:", font=("Arial", 10)).pack(side=tk.LEFT)
        self.actual_label = ttk.Label(pos_frame, text="Lat: ---, Lon: ---", font=("Arial", 10))
        self.actual_label.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(pos_frame, text="Predicted:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(30, 0))
        self.predicted_label = ttk.Label(pos_frame, text="Lat: ---, Lon: ---", font=("Arial", 10))
        self.predicted_label.pack(side=tk.LEFT, padx=10)
        
        # Create matplotlib figure with two subplots
        self.fig = Figure(figsize=(10, 5), dpi=100)
        
        # Position plot (left)
        self.ax_pos = self.fig.add_subplot(121)
        self.ax_pos.set_title("Position Tracking")
        self.ax_pos.set_xlabel("Longitude")
        self.ax_pos.set_ylabel("Latitude")
        self.ax_pos.grid(True, alpha=0.3)
        
        # Initialize plot lines
        self.actual_line, = self.ax_pos.plot([], [], 'b-', label='Actual', linewidth=1.5, alpha=0.7)
        self.predicted_line, = self.ax_pos.plot([], [], 'r--', label='Predicted', linewidth=1.5, alpha=0.7)
        self.actual_point, = self.ax_pos.plot([], [], 'bo', markersize=8)
        self.predicted_point, = self.ax_pos.plot([], [], 'r^', markersize=8)
        self.ax_pos.legend(loc='upper left')
        
        # Error plot (right)
        self.ax_err = self.fig.add_subplot(122)
        self.ax_err.set_title("Prediction Error Over Time")
        self.ax_err.set_xlabel("Time (s)")
        self.ax_err.set_ylabel("Error (m)")
        self.ax_err.grid(True, alpha=0.3)
        
        self.err_line, = self.ax_err.plot([], [], 'r-', linewidth=2, label='Error')
        self.avg_line, = self.ax_err.plot([], [], 'g--', linewidth=2, alpha=0.7, label='Average')
        self.ax_err.legend(loc='upper right')
        self.ax_err.set_ylim(0, 100)  # Initial y-limit, will auto-adjust
        
        self.fig.tight_layout()
        
        # Embed matplotlib in tkinter
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Explanation label
        explain_label = ttk.Label(
            main_frame, 
            text="Error = distance between where we predicted the aircraft would be vs where it actually is",
            font=("Arial", 9, "italic"),
            foreground="gray"
        )
        explain_label.pack(pady=5)
        
        # Start update loop
        self.update_plot()
    
    def on_slider_change(self, val):
        global prediction_time
        with prediction_lock:
            prediction_time = float(val)
        self.value_label.config(text=f"{float(val):.1f} s")
    
    def update_plot(self):
        """Update the plots with latest data."""
        with plot_data_lock:
            if len(actual_positions) > 0:
                # Update position plot
                actual_lats = [p[0] for p in actual_positions]
                actual_lons = [p[1] for p in actual_positions]
                pred_lats = [p[0] for p in predicted_positions]
                pred_lons = [p[1] for p in predicted_positions]
                
                self.actual_line.set_data(actual_lons, actual_lats)
                self.predicted_line.set_data(pred_lons, pred_lats)
                
                # Update current position markers
                if len(actual_positions) > 0:
                    self.actual_point.set_data([actual_lons[-1]], [actual_lats[-1]])
                    self.predicted_point.set_data([pred_lons[-1]], [pred_lats[-1]])
                
                # Auto-scale position plot
                if len(actual_lons) > 0:
                    all_lons = actual_lons + pred_lons
                    all_lats = actual_lats + pred_lats
                    
                    lon_margin = max(0.001, (max(all_lons) - min(all_lons)) * 0.1)
                    lat_margin = max(0.001, (max(all_lats) - min(all_lats)) * 0.1)
                    
                    self.ax_pos.set_xlim(min(all_lons) - lon_margin, max(all_lons) + lon_margin)
                    self.ax_pos.set_ylim(min(all_lats) - lat_margin, max(all_lats) + lat_margin)
                
                # Update error plot
                if len(prediction_errors) > 0:
                    times_list = list(error_timestamps)
                    err_list = list(prediction_errors)
                    
                    self.err_line.set_data(times_list, err_list)
                    
                    # Draw average line
                    if len(times_list) > 1:
                        self.avg_line.set_data(
                            [times_list[0], times_list[-1]], 
                            [avg_error, avg_error]
                        )
                    
                    if len(times_list) > 0:
                        self.ax_err.set_xlim(max(0, times_list[-1] - 60), times_list[-1] + 5)
                        max_err = max(err_list) if err_list else 100
                        self.ax_err.set_ylim(0, max(50, max_err * 1.2))
                
                # Update info labels
                if current_error > 0:
                    self.error_label.config(text=f"Prediction Error: {current_error:.1f} m")
                else:
                    self.error_label.config(text="Prediction Error: waiting...")
                    
                self.avg_error_label.config(text=f"Avg Error: {avg_error:.1f} m")
                self.buffer_label.config(text=f"Pending: {len(prediction_buffer)}")
                self.actual_label.config(text=f"Lat: {current_actual[0]:.6f}, Lon: {current_actual[1]:.6f}")
                self.predicted_label.config(text=f"Lat: {current_predicted[0]:.6f}, Lon: {current_predicted[1]:.6f}")
                
                self.canvas.draw_idle()
        
        # Schedule next update
        self.root.after(200, self.update_plot)
    
    def run(self):
        self.root.mainloop()


def create_gui():
    """Creates and runs the Tkinter GUI."""
    gui = PlotGUI()
    gui.run()


def get_future_position(lat, lon, alt_m, track_deg, speed_kts, vert_rate_fpm, dt_seconds):
    """
    Predicts future position based on current state and time delta.
    
    Args:
        lat: Current latitude (degrees)
        lon: Current longitude (degrees)
        alt_m: Current altitude (meters)
        track_deg: Track/heading (degrees, 0=North, clockwise)
        speed_kts: Ground speed (knots)
        vert_rate_fpm: Vertical rate (feet per minute)
        dt_seconds: Time into the future to predict (seconds)
    
    Returns:
        tuple: (future_lat, future_lon, future_alt_m)
    """
    if dt_seconds <= 0:
        return lat, lon, alt_m
    
    # Convert speed from knots to meters per second
    speed_mps = speed_kts * 0.514444
    
    # Convert vertical rate from feet per minute to meters per second
    vert_rate_mps = vert_rate_fpm * 0.3048 / 60.0
    
    # Calculate distance traveled in dt_seconds
    distance_m = speed_mps * dt_seconds
    
    # Convert track to radians (0=North, clockwise)
    track_rad = np.radians(track_deg)
    
    # Calculate displacement in North and East directions
    delta_north = distance_m * np.cos(track_rad)
    delta_east = distance_m * np.sin(track_rad)
    
    # Convert displacement to lat/lon changes
    # Approximate meters per degree at given latitude
    meters_per_deg_lat = 111320.0  # Roughly constant
    meters_per_deg_lon = 111320.0 * np.cos(np.radians(lat))
    
    # Calculate new position
    future_lat = lat + (delta_north / meters_per_deg_lat)
    future_lon = lon + (delta_east / meters_per_deg_lon)
    
    # Calculate new altitude
    delta_alt_m = vert_rate_mps * dt_seconds
    future_alt_m = alt_m + delta_alt_m
    
    return future_lat, future_lon, future_alt_m


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


def string_to_float(s):
    """Extract latitude and longitude from position string."""
    pattern = r"(-?\d+\.?\d*)"
    matches = re.findall(pattern, s)
    
    if len(matches) == 2:
        latitude = float(matches[0])
        longitude = float(matches[1])
        return latitude, longitude
    return None


# WGS84 Ellipsoid parameters
a = 6378137.0         # Semi-major axis (meters)
f = 1 / 298.257223563   # Flattening
e_sq = f * (2 - f)    # Square of first eccentricity


def lla_to_ecef(lat, lon, alt):
    """Converts LLA (degrees, meters) to ECEF (meters)"""
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    N = a / np.sqrt(1 - e_sq * np.sin(lat_rad)**2)
    X = (N + alt) * np.cos(lat_rad) * np.cos(lon_rad)
    Y = (N + alt) * np.cos(lat_rad) * np.sin(lon_rad)
    Z = ((1 - e_sq) * N + alt) * np.sin(lat_rad)
    return np.array([X, Y, Z])


def get_az_alt(user_ecef, user_lat_rad, user_lon_rad, ac_ecef):
    """
    Calculates Az/Alt from ECEF vectors.
    Pre-calculating user_ecef and rotation matrix parts saves CPU time
    in the fast loop.
    """
    
    # Get the vector from user to aircraft in ECEF frame
    vec_ecef = ac_ecef - user_ecef
    
    # Rotate the vector into the user's local ENU (East, North, Up) frame
    sin_lon = np.sin(user_lon_rad)
    cos_lon = np.cos(user_lon_rad)
    sin_lat = np.sin(user_lat_rad)
    cos_lat = np.cos(user_lat_rad)
    
    e = -sin_lon * vec_ecef[0] + cos_lon * vec_ecef[1]
    n = -sin_lat * cos_lon * vec_ecef[0] - sin_lat * sin_lon * vec_ecef[1] + cos_lat * vec_ecef[2]
    u = cos_lat * cos_lon * vec_ecef[0] + cos_lat * sin_lon * vec_ecef[1] + sin_lat * vec_ecef[2]
    
    # Convert ENU coordinates to Azimuth and Altitude
    alt_rad = np.arcsin(u / np.linalg.norm([e, n, u]))
    az_rad = np.arctan2(e, n)
    
    alt_deg = np.degrees(alt_rad)
    az_deg = (np.degrees(az_rad) + 360) % 360  # Normalize to 0-360
    
    return az_deg, alt_deg


def main():
    # Load config
    config_path = 'data/config.txt'
    load_config(config_path)
    home = [home_lat, home_lon, home_alt]
    
    # Find serial port
    port = find_serial_port()
    if not port:
        print("No serial port found.")
        print("Set SERIAL_PORT env var or connect your device.")
        sys.exit(1)

    print(f"Using serial port: {port} at {BAUD_RATE_DEFAULT} baud")

    # Pre-calculate ECEF and lat/lon for home position
    homecef = lla_to_ecef(home[0], home[1], home[2])
    homelat = np.radians(home[0])
    homelon = np.radians(home[1])

    # Start GUI in a separate thread
    gui_thread = threading.Thread(target=create_gui, daemon=True)
    gui_thread.start()

    # ICAO code and Selenium setup
    icao = ""  # Replace with desired ICAO code
    url = f"https://globe.adsbexchange.com/?icao={icao}"
    
    driver = webdriver.Firefox()
    firefox_options = FirefoxOptions()

    try:
        driver.get(url)
        time.sleep(9)  # Wait for the page to load

        pos = driver.find_element(By.CLASS_NAME, 'infoData')
        for i in range(200000):
            position = pos.find_element(By.XPATH, '//*[@id="selected_position"]')  # lat lon
            height = pos.find_element(By.XPATH, '//*[@id="selected_altitude_geom1"]')  # feet
            track = pos.find_element(By.XPATH, '//*[@id="selected_track1"]')  # degrees
            gspd = pos.find_element(By.XPATH, '//*[@id="selected_speed1"]')  # knots
            vertspd = pos.find_element(By.XPATH, '//*[@id="selected_vert_rate"]')  # feet p min
            
            acp = string_to_float(position.text)
            ach = re.findall(r"(-?\d+\.?\d*)", height.text)
            act = float(re.findall(r"(-?\d+\.?\d*)", track.text)[0])
            acs = float(re.findall(r"(-?\d+\.?\d*)", gspd.text)[0])
            acv = float(re.findall(r"(-?\d+\.?\d*)", vertspd.text)[0])
            
            print(f'Lat: {acp[0]} Lon: {acp[1]} Height: {ach} ft Track: {act} deg Speed: {acs} kts VeRTSPD: {acv} fpm')
            
            if not ach:
                time.sleep(5)
                print("No height data, retrying...")
                continue
            
            ach = float(ach[0])
            achm = ach * 0.3048  # feet to meters
            
            # Get current prediction time from GUI slider (thread-safe)
            with prediction_lock:
                current_prediction_time = prediction_time
            
            # Calculate future position if prediction time > 0
            if current_prediction_time > 0:
                future_lat, future_lon, future_alt_m = get_future_position(
                    acp[0], acp[1], achm, act, acs, acv, current_prediction_time
                )
                print(f'Predicted +{current_prediction_time:.1f}s: Lat: {future_lat:.6f} Lon: {future_lon:.6f} Alt: {future_alt_m:.1f}m')
            else:
                future_lat, future_lon, future_alt_m = acp[0], acp[1], achm
            
            # Update plot data
            update_plot_data(acp[0], acp[1], future_lat, future_lon, current_prediction_time)

            accef = lla_to_ecef(future_lat, future_lon, future_alt_m)
            azalt = get_az_alt(homecef, homelat, homelon, accef)
            print(np.array(azalt))
            
            if azalt[1] < -30 or azalt[1] > 54:
                print("Beyond limits, skipping...")
            else:
                send_position(f"AZ:{azalt[0]:.5f} ALT:{azalt[1]:.5f}", port, BAUD_RATE_DEFAULT)
            
            time.sleep(0.3)
    
    except KeyboardInterrupt:
        print('\nInterrupted by user.')
    finally:
        cleanup()
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
