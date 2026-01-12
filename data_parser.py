"""Data parsing and utility functions."""

import re
import numpy as np


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth.
    
    Args:
        lat1, lon1: First point (decimal degrees)
        lat2, lon2: Second point (decimal degrees)
        
    Returns:
        float: Distance in meters
    """
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    earth_radius_m = 6371000
    return c * earth_radius_m


def parse_position_string(position_str):
    """
    Extract latitude and longitude from a position string.
    
    Expects format like: "45.123456 -122.654321"
    
    Args:
        position_str: String containing position data
        
    Returns:
        tuple: (latitude, longitude) or None if parsing fails
    """
    pattern = r"(-?\d+\.?\d*)"
    matches = re.findall(pattern, position_str)
    
    if len(matches) >= 2:
        try:
            return float(matches[0]), float(matches[1])
        except ValueError:
            return None
    return None


def parse_float_value(text):
    """
    Extract first float value from text.
    
    Args:
        text: Text containing a numeric value
        
    Returns:
        float: Parsed value, or None if not found
    """
    matches = re.findall(r"(-?\d+\.?\d*)", text)
    if matches:
        try:
            return float(matches[0])
        except ValueError:
            return None
    return None


def feet_to_meters(feet):
    """Convert feet to meters."""
    return feet * 0.3048
