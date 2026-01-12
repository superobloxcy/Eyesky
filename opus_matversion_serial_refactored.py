"""
ADS-B Delay Compensation & Tracking System

Main script that orchestrates aircraft tracking, prediction, and visualization.
Fetches live aircraft data from web, applies delay compensation, predicts future position,
and sends corrected azimuth/altitude to ESP32 tracker.
"""

import time
import threading
import numpy as np
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By

# Import modules
from config import load_config
from coordinates import lla_to_ecef, get_az_alt, get_future_position
from data_parser import parse_position_string, parse_float_value, feet_to_meters
from serial_handler import SerialHandler
from gui import create_gui, update_plot_data, get_prediction_time


def main():
    """Main execution function."""
    
    # Load configuration
    try:
        config = load_config('data/config.txt')
        home_lat = config['home_lat']
        home_lon = config['home_lon']
        home_alt = config['home_alt']
        print(f"Home position: {home_lat:.6f}, {home_lon:.6f}, {home_alt:.1f}m")
    except (FileNotFoundError, ValueError) as e:
        print(f"Configuration error: {e}")
        return
    
    # Pre-calculate home position in ECEF (constant, used for all calculations)
    home_ecef = lla_to_ecef(home_lat, home_lon, home_alt)
    home_lat_rad = np.radians(home_lat)
    home_lon_rad = np.radians(home_lon)
    
    # Initialize serial handler
    serial_handler = SerialHandler(port="COM5", baud_rate=115200)
    
    # Start GUI in separate thread
    gui_thread = threading.Thread(target=create_gui, daemon=True)
    gui_thread.start()
    
    # Initialize web driver
    firefox_options = FirefoxOptions()
    # firefox_options.add_argument("--headless")  # Uncomment to run headless
    
    icao = ""  # Replace with desired ICAO code
    url = f"https://globe.adsbexchange.com/?icao={icao}"
    
    driver = webdriver.Firefox(options=firefox_options)
    
    try:
        driver.get(url)
        time.sleep(1)  # Wait for page to load
        
        pos = driver.find_element(By.CLASS_NAME, 'infoData')
        
        # Main tracking loop
        for iteration in range(200000):
            try:
                # Fetch aircraft data from webpage
                position_elem = pos.find_element(By.XPATH, '//*[@id="selected_position"]')
                height_elem = pos.find_element(By.XPATH, '//*[@id="selected_altitude_geom1"]')
                track_elem = pos.find_element(By.XPATH, '//*[@id="selected_track1"]')
                gspd_elem = pos.find_element(By.XPATH, '//*[@id="selected_speed1"]')
                vertspd_elem = pos.find_element(By.XPATH, '//*[@id="selected_vert_rate"]')
                
                # Parse aircraft position and state
                ac_position = parse_position_string(position_elem.text)
                ac_height_ft = parse_float_value(height_elem.text)
                ac_track = parse_float_value(track_elem.text)
                ac_speed = parse_float_value(gspd_elem.text)
                ac_vert_rate = parse_float_value(vertspd_elem.text)
                
                # Validate data
                if not ac_position or ac_height_ft is None:
                    print(f"Iteration {iteration}: Missing data, retrying...")
                    time.sleep(5)
                    continue
                
                ac_lat, ac_lon = ac_position
                ac_alt_m = feet_to_meters(ac_height_ft)
                
                print(f'Lat: {ac_lat:.6f} Lon: {ac_lon:.6f} Height: {ac_height_ft:.1f} ft '
                      f'Track: {ac_track:.1f}° Speed: {ac_speed:.1f} kts VRate: {ac_vert_rate:.1f} fpm')
                
                # Get prediction time from GUI
                pred_time = get_prediction_time()
                
                # Calculate predicted future position
                if pred_time > 0:
                    future_lat, future_lon, future_alt_m = get_future_position(
                        ac_lat, ac_lon, ac_alt_m, ac_track, ac_speed, ac_vert_rate, pred_time
                    )
                    print(f'Predicted +{pred_time:.1f}s: Lat: {future_lat:.6f} Lon: {future_lon:.6f} '
                          f'Alt: {future_alt_m:.1f}m')
                else:
                    future_lat, future_lon, future_alt_m = ac_lat, ac_lon, ac_alt_m
                
                # Update visualization
                update_plot_data(ac_lat, ac_lon, future_lat, future_lon, pred_time)
                
                # Calculate azimuth and altitude from home to predicted position
                ac_ecef = lla_to_ecef(future_lat, future_lon, future_alt_m)
                azimuth, altitude = get_az_alt(home_ecef, home_lat_rad, home_lon_rad, ac_ecef)
                
                print(f'Azimuth: {azimuth:.5f}° Altitude: {altitude:.5f}°')
                
                # Send to tracker if within limits
                if altitude < -30 or altitude > 54:
                    print("Beyond altitude limits, skipping...")
                else:
                    serial_handler.send(f"AZ:{azimuth:.5f} ALT:{altitude:.5f}")
                
                time.sleep(0.3)
                
            except Exception as e:
                print(f"Error in iteration {iteration}: {e}")
                time.sleep(5)
    
    finally:
        driver.quit()
        serial_handler.close()
        print("Program terminated.")


if __name__ == "__main__":
    main()
