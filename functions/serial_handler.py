"""Serial port communication handler for ESP32."""

import serial
import time
import threading


class SerialHandler:
    """Manages serial communication with ESP32."""
    
    def __init__(self, port, baud_rate=115200, timeout=5):
        """
        Initialize serial handler.
        
        Args:
            port: COM port (e.g., 'COM5')
            baud_rate: Baud rate (default 115200)
            timeout: Read timeout in seconds
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser = None
        self.connected = False
        self.lock = threading.Lock()
    
    def connect(self):
        """
        Establish connection to ESP32.
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self.lock:
            if self.connected:
                return True
            
            try:
                # Close any existing connection
                if self.ser:
                    self.ser.close()
                    time.sleep(1)
                
                print(f"Connecting to {self.port} at {self.baud_rate} baud...")
                self.ser = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
                time.sleep(2)  # Wait for ESP32 to initialize
                self.connected = True
                print("Successfully connected to ESP32.")
                return True
                
            except (serial.SerialException, PermissionError, OSError) as e:
                print(f"Failed to connect: {e}")
                self.ser = None
                self.connected = False
                return False
    
    def send(self, data):
        """
        Send data to ESP32.
        
        Args:
            data: String data to send
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        print(f"---> {data}")
        
        # Try to connect if not already connected
        if not self.connected:
            if not self.connect():
                print("Not connected to ESP32, skipping send.")
                return False
        
        try:
            with self.lock:
                if self.connected and self.ser:
                    self.ser.write((data + "\n").encode())
                    time.sleep(0.1)
                    return True
        except (serial.SerialException, OSError) as e:
            print(f"Error sending data: {e}")
            self._disconnect()
            return False
        except Exception as e:
            print(f"Unexpected error during send: {e}")
            self._disconnect()
            return False
        
        return False
    
    def _disconnect(self):
        """Internal method to disconnect."""
        with self.lock:
            if self.ser:
                try:
                    self.ser.close()
                except:
                    pass
            self.ser = None
            self.connected = False
    
    def close(self):
        """Close the serial connection."""
        self._disconnect()
        print("Serial connection closed.")
    
    def is_connected(self):
        """Check if currently connected."""
        return self.connected
