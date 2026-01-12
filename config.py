"""Configuration loader for home position and other settings."""

def load_config(config_path='data/config.txt'):
    """
    Load configuration from file.
    
    Expected format:
        home_lat=<latitude>
        home_lon=<longitude>
        home_alt=<altitude>
    
    Returns:
        dict: Configuration dictionary with home_lat, home_lon, home_alt
        
    Raises:
        ValueError: If required configuration values are missing
    """
    config = {}
    
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Only parse home position values
                    if key in ['home_lat', 'home_lon', 'home_alt']:
                        try:
                            config[key] = float(value)
                        except ValueError:
                            raise ValueError(f"Invalid value for {key}: {value} (expected a number)")
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    except ValueError:
        raise
    
    # Validate required fields
    required = ['home_lat', 'home_lon', 'home_alt']
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    
    return config
