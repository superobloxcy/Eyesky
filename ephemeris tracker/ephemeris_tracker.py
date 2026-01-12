"""
Ephemeris data fetcher using Skyfield library.
Supports hundreds of celestial objects and can generate tracking logs.
"""

import skyfield.api as skyapi
from skyfield.data import hipparcos, mpc
from datetime import datetime, timedelta
import pytz
import os
from pathlib import Path

# Download and cache ephemeris data
eph = skyapi.load('de421.bsp')  # Planetary ephemeris (very accurate, covers 1900-2050)
earth = eph['earth']
sun = eph['sun']

# Available object types
BUILTIN_OBJECTS = {
    'sun': ('sun', None),
    'moon': ('moon', None),
    'mercury': ('mercury', None),
    'venus': ('venus', None),
    'mars': ('mars', None),
    'jupiter': ('jupiter', None),
    'saturn': ('saturn', None),
    'uranus': ('uranus', None),
    'neptune': ('neptune', None),
}

def get_available_objects():
    """
    Returns a dictionary of available celestial objects.
    Includes planets, bright stars, asteroids, and comets.
    """
    objects = dict(BUILTIN_OBJECTS)
    
    # Load bright stars from Hipparcos catalog
    try:
        df = skyapi.load_dataframe(hipparcos.URL)
        star_count = len(df)
        objects['stars'] = ('hipparcos', df)
        objects['_star_count'] = star_count
    except Exception as e:
        print(f"Warning: Could not load Hipparcos stars: {e}")
    
    # Load asteroids and comets
    try:
        df_asteroids = skyapi.load_dataframe(mpc.URL)
        asteroid_count = len(df_asteroids)
        objects['asteroids'] = ('mpc', df_asteroids)
        objects['_asteroid_count'] = asteroid_count
    except Exception as e:
        print(f"Warning: Could not load MPC asteroids/comets: {e}")
    
    return objects

def get_object_list_for_gui():
    """
    Returns a list of object names suitable for GUI display.
    Groups similar objects together.
    """
    objects = get_available_objects()
    
    gui_list = []
    
    # Add planets
    planets = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune']
    for p in planets:
        gui_list.append(p.capitalize())
    
    # Add star count if available
    if '_star_count' in objects:
        gui_list.append(f"Bright Stars ({objects['_star_count']} available)")
    
    # Add asteroid/comet count
    if '_asteroid_count' in objects:
        gui_list.append(f"Asteroids/Comets ({objects['_asteroid_count']} available)")
    
    return gui_list

def get_position(observer_lat, observer_lon, observer_alt, target_name, observation_time_utc):
    """
    Calculate azimuth and altitude for a target object from observer location.
    Uses Skyfield with proper RA/Dec to Alt/Az conversion.
    
    Args:
        observer_lat: Latitude in degrees
        observer_lon: Longitude in degrees
        observer_alt: Altitude in meters
        target_name: Name of celestial object (or special identifiers like 'hipparcos_123')
        observation_time_utc: datetime object in UTC
    
    Returns:
        tuple: (azimuth_degrees, altitude_degrees) or (None, None) if error
    """
    try:
        import math
        from skyfield.toposlib import wgs84
        
        ts = skyapi.load.timescale()
        t = ts.from_datetime(observation_time_utc)
        
        # Create observer location (altitude in meters)
        observer_location = earth + wgs84.latlon(observer_lat, observer_lon, observer_alt)
        
        # Get target astrometric position
        if target_name.lower() in BUILTIN_OBJECTS:
            target = eph[target_name.lower()]
        elif target_name.startswith('hipparcos_'):
            # Star from Hipparcos catalog
            hip_num = int(target_name.split('_')[1])
            df = skyapi.load_dataframe(hipparcos.URL)
            star_data = df.loc[hip_num]
            target = skyapi.Star.from_dataframe(df.iloc[[hip_num]])
        else:
            return None, None
        
        # Get observer's position at this time
        observer_at_time = observer_location.at(t)
        
        # Calculate position of target relative to observer
        astrometric = observer_at_time.observe(target)
        apparent = astrometric.apparent()
        
        # Use Skyfield's built-in coordinate frame transformation to get alt/az
        # This is more accurate than manually calculating from RA/Dec
        from skyfield.toposlib import wgs84
        
        # Get altitude and azimuth directly in topocentric horizontal frame
        apparent_topocentric = observer_location.at(t).observe(target).apparent()
        alt, az, distance = apparent_topocentric.apparent_latitudinal()
        
        altitude = alt.degrees
        azimuth = az.degrees
        
        return azimuth, altitude
    
    except Exception as e:
        print(f"Error calculating position for {target_name}: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def generate_tracking_log(observer_lat, observer_lon, observer_alt, target_names, 
                         duration_hours, time_step_seconds, output_file=None):
    """
    Generate a tracking log with timestamps, azimuth, and altitude for target objects.
    
    Args:
        observer_lat: Latitude in degrees
        observer_lon: Longitude in degrees
        observer_alt: Altitude in meters
        target_names: List of target object names
        duration_hours: Duration to track in hours
        time_step_seconds: Time step between measurements in seconds
        output_file: Path to output file (if None, uses timestamp-based name)
    
    Returns:
        str: Path to generated log file
    """
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'tracking_log_{timestamp}.txt'
    
    start_time = datetime.now(pytz.UTC)
    end_time = start_time + timedelta(hours=duration_hours)
    current_time = start_time
    
    # Create log directory if it doesn't exist
    log_dir = Path('tracking_logs')
    log_dir.mkdir(exist_ok=True)
    output_path = log_dir / output_file
    
    with open(output_path, 'w') as f:
        f.write(f"Tracking Log - Generated {start_time.isoformat()}\n")
        f.write(f"Observer: Lat={observer_lat}, Lon={observer_lon}, Alt={observer_alt}m\n")
        f.write(f"Duration: {duration_hours} hours, Time Step: {time_step_seconds}s\n")
        f.write(f"Targets: {', '.join(target_names)}\n")
        f.write("-" * 80 + "\n")
        f.write("Unix_Time, DateTime_UTC, Target, Azimuth, Altitude\n")
        
        entries_count = 0
        while current_time <= end_time:
            unix_time = int(current_time.timestamp())
            datetime_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            
            for target_name in target_names:
                az, alt = get_position(observer_lat, observer_lon, observer_alt, 
                                      target_name, current_time)
                
                if az is not None and alt is not None:
                    f.write(f"{unix_time}, {datetime_str}, {target_name}, {az:.4f}, {alt:.4f}\n")
                    entries_count += 1
            
            current_time += timedelta(seconds=time_step_seconds)
    
    print(f"✓ Generated tracking log: {output_path}")
    print(f"  Total entries: {entries_count}")
    return str(output_path)

if __name__ == "__main__":
    # Test the module
    print("Available objects:", get_object_list_for_gui())
    
    # Test position calculation
    az, alt = get_position(-27.988, 153.323, 67, 'sun', datetime.now(pytz.UTC))
    print(f"Sun position: Az={az:.2f}°, Alt={alt:.2f}°")
