"""Coordinate transformation utilities for LLA to ECEF and azimuth/altitude calculations."""

import numpy as np

# WGS84 Ellipsoid parameters
WGS84_A = 6378137.0                    # Semi-major axis (meters)
WGS84_F = 1 / 298.257223563            # Flattening
WGS84_E_SQ = WGS84_F * (2 - WGS84_F)   # Square of first eccentricity


def lla_to_ecef(lat, lon, alt):
    """
    Convert LLA (Latitude, Longitude, Altitude) to ECEF (Earth-Centered, Earth-Fixed) coordinates.
    
    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees
        alt: Altitude in meters above ellipsoid
        
    Returns:
        np.ndarray: ECEF coordinates [X, Y, Z] in meters
    """
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    
    N = WGS84_A / np.sqrt(1 - WGS84_E_SQ * np.sin(lat_rad)**2)
    
    X = (N + alt) * np.cos(lat_rad) * np.cos(lon_rad)
    Y = (N + alt) * np.cos(lat_rad) * np.sin(lon_rad)
    Z = ((1 - WGS84_E_SQ) * N + alt) * np.sin(lat_rad)
    
    return np.array([X, Y, Z])


def get_az_alt(user_ecef, user_lat_rad, user_lon_rad, ac_ecef):
    """
    Calculate azimuth and altitude from observer position to aircraft.
    
    This function uses pre-calculated ECEF coordinates and trigonometric values
    to efficiently compute the target's position in the observer's local ENU frame.
    
    Args:
        user_ecef: Observer position in ECEF coordinates (np.ndarray)
        user_lat_rad: Observer latitude in radians
        user_lon_rad: Observer longitude in radians
        ac_ecef: Aircraft position in ECEF coordinates (np.ndarray)
        
    Returns:
        tuple: (azimuth_deg, altitude_deg) where:
               - azimuth is in degrees [0, 360) with 0=North, clockwise
               - altitude is in degrees [-90, 90] with 0=horizon, +90=zenith
    """
    # Get vector from observer to aircraft in ECEF frame
    vec_ecef = ac_ecef - user_ecef
    
    # Rotate into observer's local ENU (East, North, Up) frame
    sin_lon = np.sin(user_lon_rad)
    cos_lon = np.cos(user_lon_rad)
    sin_lat = np.sin(user_lat_rad)
    cos_lat = np.cos(user_lat_rad)
    
    east = -sin_lon * vec_ecef[0] + cos_lon * vec_ecef[1]
    north = -sin_lat * cos_lon * vec_ecef[0] - sin_lat * sin_lon * vec_ecef[1] + cos_lat * vec_ecef[2]
    up = cos_lat * cos_lon * vec_ecef[0] + cos_lat * sin_lon * vec_ecef[1] + sin_lat * vec_ecef[2]
    
    # Convert ENU to azimuth and altitude
    altitude_rad = np.arcsin(up / np.linalg.norm([east, north, up]))
    azimuth_rad = np.arctan2(east, north)
    
    altitude_deg = np.degrees(altitude_rad)
    azimuth_deg = (np.degrees(azimuth_rad) + 360) % 360  # Normalize to [0, 360)
    
    return azimuth_deg, altitude_deg


def get_future_position(lat, lon, alt_m, track_deg, speed_kts, vert_rate_fpm, dt_seconds):
    """
    Predict future position of aircraft based on current state.
    
    Args:
        lat: Current latitude (degrees)
        lon: Current longitude (degrees)
        alt_m: Current altitude (meters)
        track_deg: Track/heading (degrees, 0=North, clockwise)
        speed_kts: Ground speed (knots)
        vert_rate_fpm: Vertical rate (feet per minute)
        dt_seconds: Time delta for prediction (seconds)
        
    Returns:
        tuple: (future_lat, future_lon, future_alt_m) predicted position
    """
    if dt_seconds <= 0:
        return lat, lon, alt_m
    
    # Convert units
    speed_mps = speed_kts * 0.514444  # knots to m/s
    vert_rate_mps = vert_rate_fpm * 0.3048 / 60.0  # fpm to m/s
    
    # Calculate distance traveled
    distance_m = speed_mps * dt_seconds
    
    # Convert track to radians
    track_rad = np.radians(track_deg)
    
    # Displacement in North/East directions
    delta_north = distance_m * np.cos(track_rad)
    delta_east = distance_m * np.sin(track_rad)
    
    # Convert to lat/lon change
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * np.cos(np.radians(lat))
    
    future_lat = lat + (delta_north / meters_per_deg_lat)
    future_lon = lon + (delta_east / meters_per_deg_lon)
    future_alt_m = alt_m + (vert_rate_mps * dt_seconds)
    
    return future_lat, future_lon, future_alt_m
