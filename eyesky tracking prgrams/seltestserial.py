import time
import re
import numpy as np
import socket
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions


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
            time.sleep(0.1) # Keep the original delay
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

def string_to_float(s):
    # Pattern finds any number (with optional sign and decimal)
    pattern = r"(-?\d+\.?\d*)"

    # Finds all numbers in the string
    matches = re.findall(pattern, s)

    if len(matches) == 2:
        latitude = float(matches[0])
        longitude = float(matches[1])
        return latitude, longitude

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
    
    # 2. Get the vector from user to aircraft in ECEF frame
    vec_ecef = ac_ecef - user_ecef
    
    # 3. Rotate the vector into the user's local ENU (East, North, Up) frame
    # This is an optimized rotation matrix calculation
    sin_lon = np.sin(user_lon_rad)
    cos_lon = np.cos(user_lon_rad)
    sin_lat = np.sin(user_lat_rad)
    cos_lat = np.cos(user_lat_rad)
    
    e = -sin_lon * vec_ecef[0] + cos_lon * vec_ecef[1]
    n = -sin_lat * cos_lon * vec_ecef[0] - sin_lat * sin_lon * vec_ecef[1] + cos_lat * vec_ecef[2]
    u = cos_lat * cos_lon * vec_ecef[0] + cos_lat * sin_lon * vec_ecef[1] + sin_lat * vec_ecef[2]
    
    # 4. Convert ENU coordinates to Azimuth and Altitude
    alt_rad = np.arcsin(u / np.linalg.norm([e, n, u]))
    az_rad = np.arctan2(e, n)
    
    alt_deg = np.degrees(alt_rad)
    az_deg = (np.degrees(az_rad) + 360) % 360  # Normalize to 0-360
    
    return az_deg, alt_deg

homecef = lla_to_ecef(-27.988,153.323,67)  # Home position in ECEF
homelat = np.radians(-27.988)
homelon = np.radians(153.323)

icao=""  # Replace with desired ICAO code

url="https://globe.adsbexchange.com/?icao="+icao


driver = webdriver.Firefox()
firefox_options = FirefoxOptions()

driver.get(url)

time.sleep(10)  # Wait for the page to load

#sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#sock.connect((ESP32_IP, ESP32_PORT))


pos = driver.find_element(By.CLASS_NAME,'infoData')
for i in range(200000):
    position=pos.find_element(By.XPATH,'//*[@id="selected_position"]') #lat lon
    height=pos.find_element(By.XPATH,'//*[@id="selected_altitude_geom1"]') #feet
    track=pos.find_element(By.XPATH,'//*[@id="selected_track1"]') #degrees
    gspd=pos.find_element(By.XPATH,'//*[@id="selected_speed1"]') #knots
    vertspd=pos.find_element(By.XPATH,'//*[@id="selected_vert_rate"]') #feet p min
    #print(f'track: {track.text}')
    acp=string_to_float(position.text)
    ach=re.findall(r"(-?\d+\.?\d*)", height.text)
    act=float(re.findall(r"(-?\d+\.?\d*)", track.text)[0])
    acs=float(re.findall(r"(-?\d+\.?\d*)", gspd.text)[0])
    acv=float(re.findall(r"(-?\d+\.?\d*)", vertspd.text)[0])
    print(f'Lat: {acp[0]} Lon: {acp[1]} Height: {ach} ft Track: {act} deg Speed: {acs} kts VeRTSPD: {acv} fpm')
    if not ach:
        time.sleep(5)
        print("No height data, retrying...")
        continue
    ach=float(ach[0])
    achm=ach*0.3048  # feet to meters
    #future position prediction could be added here using track, speed, vertspd
    


    accef=lla_to_ecef(acp[0],acp[1],achm)
    azalt=get_az_alt(homecef,homelat,homelon,accef)
    print(np.array(azalt))
    if azalt[1]<-30 or azalt[1]>54:
        print("Beyond limits, skipping...")
    else:
        send_position(f"AZ:{azalt[0]:.3f} ALT:{azalt[1]:.3f}")
    time.sleep(0.5)



