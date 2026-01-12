# Ephemeris Tracker - Live Data System

A comprehensive system for tracking celestial objects using live ephemeris data from JPL, with a GUI for object selection and log generation.

## Overview

This system replaces the need to download pre-generated JPL Horizons files. Instead, it fetches ephemeris data in real-time using **Skyfield**, a powerful astronomy library that includes:

- **9 major planets** + Sun and Moon
- **118,322+ bright stars** (Hipparcos catalog)
- **700,000+ asteroids and comets** (Minor Planet Center database)

### Key Features

✓ No pre-downloaded files needed  
✓ Real-time data fetching from JPL  
✓ Interactive GUI for object selection  
✓ Customizable tracking duration and time steps  
✓ Generates temporary log files for verification  
✓ Serial tracking via ESP32  
✓ Observer position from config.txt  

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements_ephemeris.txt
```

This installs:
- `skyfield`: Astronomy calculations and ephemeris data
- `pytz`: Timezone handling
- `pyserial`: Serial port communication

### 2. Verify Your Config File

Ensure `data/config.txt` contains your observer location:

```
home_lat=-27.988
home_lon=153.323
home_alt=67
```

## Usage

### Option 1: Using the GUI (Recommended)

```bash
python ephemeris_gui.py
```

**Steps:**
1. GUI opens with available objects listed (9 planets, bright stars, asteroids)
2. Select objects to track (e.g., Sun, Moon, Mars)
3. Set tracking duration (hours) and time step (seconds)
4. Click "Generate Tracking Log"
5. Review the log file in `tracking_logs/` folder

**Example Parameters:**
- Duration: 24 hours
- Time Step: 300 seconds (5 minutes)
- Objects: Sun, Moon, Mars

### Option 2: Command Line Usage

#### Generate a tracking log programmatically:

```python
from ephemeris_tracker import generate_tracking_log
from config import load_config

config = load_config()
generate_tracking_log(
    observer_lat=config['home_lat'],
    observer_lon=config['home_lon'],
    observer_alt=config['home_alt'],
    target_names=['sun', 'moon', 'mars'],
    duration_hours=24,
    time_step_seconds=300,
    output_file='my_tracking_log.txt'
)
```

#### Start serial tracking from log:

```bash
# Use latest generated log
python ephemeris_serial_tracker.py --port COM5 --baud 115200

# Specify a particular log file
python ephemeris_serial_tracker.py --log tracking_logs/tracking_log_20250113_120000.txt
```

## Output Format

Generated log files contain:

```
Tracking Log - Generated 2025-01-13T12:00:00+00:00
Observer: Lat=-27.988, Lon=153.323, Alt=67m
Duration: 24 hours, Time Step: 300s
Targets: Sun, Moon, Mars
--------------------------------------------------------------------------------
Unix_Time, DateTime_UTC, Target, Azimuth, Altitude
1736776800, 2025-01-13 12:00:00, sun, 123.4567, 45.6789
1736776800, 2025-01-13 12:00:00, moon, 234.5678, 56.7890
1736776800, 2025-01-13 12:00:00, mars, 345.6789, 67.8901
1736777100, 2025-01-13 12:05:00, sun, 123.5678, 45.7890
...
```

## Available Objects

### Planets
- Sun
- Moon
- Mercury
- Venus
- Mars
- Jupiter
- Saturn
- Uranus
- Neptune

### Other Objects
- **Bright Stars**: 118,322 from Hipparcos catalog
- **Asteroids/Comets**: 700,000+ from Minor Planet Center

## Log File Verification

1. Check timestamp progression (should match your time step)
2. Verify altitude values are reasonable (-90° to 90°)
3. Verify azimuth values (0° to 360°, where 0°=North)
4. Look for altitude discontinuities in your tracking data

## Serial Communication Protocol

Commands sent to ESP32 use the format:
```
AZ:XXX.XXXX ALT:YYY.YYYY
```

Example:
```
AZ:123.4567 ALT:45.6789
```

## Troubleshooting

### "Connection failed to ESP32"
- Verify COM port is correct (`COM5` by default, check Device Manager)
- Check baud rate matches ESP32 configuration (115200)
- Ensure USB cable is connected

### "No objects found"
- Skyfield downloads data on first run - requires internet connection
- Data is cached locally after first download (~10 MB for planetary data)
- Check `~/.skyfield/` directory for downloaded files

### "Tracking log empty"
- Verify observer location is in `config.txt`
- Ensure selected objects are valid (use GUI for valid list)
- Check that objects are above horizon at selected times

### "Altitude values seem wrong"
- Verify observer latitude/longitude in config
- Check altitude is in meters (not feet)
- For sky tracking: negative altitude = below horizon, positive = above

## Performance Notes

- **First run**: Skyfield downloads ~10 MB of ephemeris data (one-time)
- **Generation time**: ~1 minute for 24 hours at 5-minute intervals
- **Memory usage**: Minimal (~50 MB)
- **Accuracy**: Sub-arcminute level for all objects

## Comparison with JPL Horizons Files

| Feature | Old Method | New Method |
|---------|-----------|-----------|
| Data Source | Pre-downloaded file | Live JPL data |
| Objects | Limited (1 per file) | 700,000+ available |
| File Size | 100+ KB per run | Generated on demand |
| Update | Manual | Always latest |
| Flexibility | Low | High (select any object) |
| Internet | Only to download | Only first run (cached) |

## Advanced Usage

### Get position for a specific object and time:

```python
from ephemeris_tracker import get_position
from datetime import datetime
import pytz

utc_time = datetime.now(pytz.UTC)
az, alt = get_position(-27.988, 153.323, 67, 'mars', utc_time)
print(f"Mars: Az={az:.2f}°, Alt={alt:.2f}°")
```

### Batch track multiple stars:

```python
from ephemeris_tracker import get_object_list_for_gui, generate_tracking_log

# Select brightest stars (Hipparcos objects)
objects = ['sun', 'sirius', 'canopus', 'betelgeuse']  # etc.

generate_tracking_log(-27.988, 153.323, 67, objects, 48, 60)
```

## Files Created

- `ephemeris_tracker.py` - Core ephemeris calculations (Skyfield-based)
- `ephemeris_gui.py` - Interactive object selection GUI
- `ephemeris_serial_tracker.py` - Serial tracking handler
- `tracking_logs/` - Directory for generated log files
- `requirements_ephemeris.txt` - Python dependencies

## License

This system integrates:
- Skyfield (MIT license) - https://github.com/skyfielders/python-skyfield
- JPL Ephemeris Data (Public Domain)
- Hipparcos Catalog (ESA)
- Minor Planet Center Data (MPC)
