import numpy as np
import time
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from usb4a import usb
from usbserial4a import serial4a
from threading import Thread

class TrackingApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ser = None
        self.connected = False
        self.tracking = False
        self.current_iteration = 0
        
    def build(self):
        layout = BoxLayout(orientation='vertical')
        
        self.status_label = Label(
            text='Starting tracking...\nStatus: Initializing',
            size_hint_y=0.3
        )
        layout.add_widget(self.status_label)
        
        self.info_label = Label(
            text='',
            size_hint_y=0.7
        )
        layout.add_widget(self.info_label)
        
        return layout
    
    def on_start(self):
        """Start the tracking loop in a background thread"""
        self.tracking = True
        thread = Thread(target=self.run_tracking)
        thread.daemon = True
        thread.start()
    
    def send_position(self, cmd):
        """Send command to ESP32"""
        print(f"---> {cmd}")
        
        if not self.connected:
            self._connect()
        
        if self.connected:
            try:
                self.ser.write((cmd + "\n").encode())
                time.sleep(0.05)
            except Exception as e:
                print(f"Error sending data: {e}")
                self.connected = False
    
    def _connect(self):
        """Connect to ESP32"""
        try:
            if self.ser:
                self.ser.close()
            
            # Get USB device using VID/PID (1A86:7523)
            device = usb.get_usb_device(0x1A86, 0x7523)
            if device is None:
                raise Exception("USB device with VID:1A86 PID:7523 not found")
            
            self.ser = serial4a.Serial(device)
            self.ser.setBaudrate(115200)
            time.sleep(2)
            self.connected = True
            print("Connected to ESP32")
            self.status_label.text = 'Status: Connected to ESP32'
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected = False
            self.status_label.text = f'Status: Connection failed - {e}'
    
    def run_tracking(self):
        """Main tracking loop"""
        A = 45
        try:
            for i in range(1081):
                if not self.tracking:
                    break
                
                ALT = A * np.cos(np.deg2rad(i/2))
                AZ = 45 * np.sin(np.deg2rad(i/2))
                cmd = f'AZ:{AZ:.5f} ALT:{ALT:.5f}'
                
                self.send_position(cmd)
                
                # Update UI
                Clock.schedule_once(lambda dt: self._update_ui(i, AZ, ALT), 0)
                
                time.sleep(0.025)
                
        except Exception as e:
            print(f"Tracking error: {e}")
        finally:
            self._cleanup()
    
    def _update_ui(self, iteration, az, alt):
        """Update UI with current values"""
        self.current_iteration = iteration
        self.info_label.text = f'Iteration: {iteration}/1080\nAZ: {az:.5f}°\nALT: {alt:.5f}°'
        self.status_label.text = f'Status: Tracking ({iteration}/1080)'
    
    def _cleanup(self):
        """Clean up on exit"""
        if self.ser:
            self.ser.close()
        self.connected = False
        Clock.schedule_once(lambda dt: self._update_ui(self.current_iteration, 0, 0), 0)
        self.status_label.text = 'Status: Tracking complete'
    
    def on_stop(self):
        """Stop tracking on app close"""
        self.tracking = False
        if self.ser:
            self.ser.close()
        return True

if __name__ == '__main__':
    TrackingApp().run()
