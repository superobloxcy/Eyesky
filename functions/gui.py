"""GUI for tracking and prediction visualization."""

import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from collections import deque
import threading

from .data_parser import haversine_distance


# Constants
MAX_POINTS = 100
BUFFER_MAX_AGE = 30  # seconds

# Thread-safe data structures
plot_data_lock = threading.Lock()
prediction_lock = threading.Lock()

# Data storage
actual_positions = deque(maxlen=MAX_POINTS)
predicted_positions = deque(maxlen=MAX_POINTS)
prediction_errors = deque(maxlen=MAX_POINTS)
error_timestamps = deque(maxlen=MAX_POINTS)
timestamps = deque(maxlen=MAX_POINTS)
prediction_buffer = {}

# Global state
prediction_time = 0.0
start_time = None
current_error = 0.0
current_actual = (0.0, 0.0)
current_predicted = (0.0, 0.0)
avg_error = 0.0


def update_plot_data(actual_lat, actual_lon, predicted_lat, predicted_lon, pred_time_used):
    """
    Thread-safe update of plot data with prediction error tracking.
    
    Args:
        actual_lat, actual_lon: Current actual position
        predicted_lat, predicted_lon: Predicted position
        pred_time_used: Prediction time offset in seconds
    """
    global start_time, current_error, current_actual, current_predicted, avg_error, prediction_buffer
    
    with plot_data_lock:
        if start_time is None:
            start_time = __import__('time').time()
        
        current_time = __import__('time').time() - start_time
        absolute_time = __import__('time').time()
        
        # Store positions
        actual_positions.append((actual_lat, actual_lon, current_time))
        predicted_positions.append((predicted_lat, predicted_lon, current_time))
        timestamps.append(current_time)
        
        current_actual = (actual_lat, actual_lon)
        current_predicted = (predicted_lat, predicted_lon)
        
        # Store prediction for future comparison
        if pred_time_used > 0:
            prediction_buffer[absolute_time] = (predicted_lat, predicted_lon, pred_time_used)
        
        # Check past predictions against current actual position
        predictions_to_remove = []
        
        for pred_timestamp, (pred_lat, pred_lon, pred_dt) in prediction_buffer.items():
            age = absolute_time - pred_timestamp
            time_diff = abs(age - pred_dt)
            
            if time_diff < 0.75:  # Within tolerance window
                error = haversine_distance(pred_lat, pred_lon, actual_lat, actual_lon)
                prediction_errors.append(error)
                error_timestamps.append(current_time)
                current_error = error
                predictions_to_remove.append(pred_timestamp)
            elif age > pred_dt + 2:
                predictions_to_remove.append(pred_timestamp)
            elif age > BUFFER_MAX_AGE:
                predictions_to_remove.append(pred_timestamp)
        
        for ts in predictions_to_remove:
            del prediction_buffer[ts]
        
        if len(prediction_errors) > 0:
            avg_error = sum(prediction_errors) / len(prediction_errors)


class PlotGUI:
    """Tkinter GUI for visualization."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ADS-B Delay Compensation & Tracking (Serial)")
        self.root.geometry("1000x750")
        
        self._setup_controls()
        self._setup_info_panel()
        self._setup_plots()
        
        self.update_plot()
    
    def _setup_controls(self):
        """Setup control panel."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
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
        
        self.main_frame = main_frame
    
    def _setup_info_panel(self):
        """Setup information display panel."""
        info_frame = ttk.LabelFrame(self.main_frame, text="Current Status", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X)
        
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
        
        pos_frame = ttk.Frame(info_grid)
        pos_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pos_frame, text="Actual:", font=("Arial", 10)).pack(side=tk.LEFT)
        self.actual_label = ttk.Label(pos_frame, text="Lat: ---, Lon: ---", font=("Arial", 10))
        self.actual_label.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(pos_frame, text="Predicted:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(30, 0))
        self.predicted_label = ttk.Label(pos_frame, text="Lat: ---, Lon: ---", font=("Arial", 10))
        self.predicted_label.pack(side=tk.LEFT, padx=10)
    
    def _setup_plots(self):
        """Setup matplotlib plots."""
        self.fig = Figure(figsize=(10, 5), dpi=100)
        
        # Position plot
        self.ax_pos = self.fig.add_subplot(121)
        self.ax_pos.set_title("Position Tracking")
        self.ax_pos.set_xlabel("Longitude")
        self.ax_pos.set_ylabel("Latitude")
        self.ax_pos.grid(True, alpha=0.3)
        
        self.actual_line, = self.ax_pos.plot([], [], 'b-', label='Actual', linewidth=1.5, alpha=0.7)
        self.predicted_line, = self.ax_pos.plot([], [], 'r--', label='Predicted', linewidth=1.5, alpha=0.7)
        self.actual_point, = self.ax_pos.plot([], [], 'bo', markersize=8)
        self.predicted_point, = self.ax_pos.plot([], [], 'r^', markersize=8)
        self.ax_pos.legend(loc='upper left')
        
        # Error plot
        self.ax_err = self.fig.add_subplot(122)
        self.ax_err.set_title("Prediction Error Over Time")
        self.ax_err.set_xlabel("Time (s)")
        self.ax_err.set_ylabel("Error (m)")
        self.ax_err.grid(True, alpha=0.3)
        
        self.err_line, = self.ax_err.plot([], [], 'r-', linewidth=2, label='Error')
        self.avg_line, = self.ax_err.plot([], [], 'g--', linewidth=2, alpha=0.7, label='Average')
        self.ax_err.legend(loc='upper right')
        self.ax_err.set_ylim(0, 100)
        
        self.fig.tight_layout()
        
        # Embed in tkinter
        canvas_frame = ttk.Frame(self.main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        explain_label = ttk.Label(
            self.main_frame, 
            text="Error = distance between predicted and actual aircraft position",
            font=("Arial", 9, "italic"),
            foreground="gray"
        )
        explain_label.pack(pady=5)
    
    def on_slider_change(self, val):
        """Handle prediction time slider change."""
        global prediction_time
        with prediction_lock:
            prediction_time = float(val)
        self.value_label.config(text=f"{float(val):.1f} s")
    
    def update_plot(self):
        """Update plots with latest data."""
        with plot_data_lock:
            if len(actual_positions) > 0:
                actual_lats = [p[0] for p in actual_positions]
                actual_lons = [p[1] for p in actual_positions]
                pred_lats = [p[0] for p in predicted_positions]
                pred_lons = [p[1] for p in predicted_positions]
                
                self.actual_line.set_data(actual_lons, actual_lats)
                self.predicted_line.set_data(pred_lons, pred_lats)
                
                if len(actual_positions) > 0:
                    self.actual_point.set_data([actual_lons[-1]], [actual_lats[-1]])
                    self.predicted_point.set_data([pred_lons[-1]], [pred_lats[-1]])
                
                if len(actual_lons) > 0:
                    all_lons = actual_lons + pred_lons
                    all_lats = actual_lats + pred_lats
                    
                    lon_margin = max(0.001, (max(all_lons) - min(all_lons)) * 0.1)
                    lat_margin = max(0.001, (max(all_lats) - min(all_lats)) * 0.1)
                    
                    self.ax_pos.set_xlim(min(all_lons) - lon_margin, max(all_lons) + lon_margin)
                    self.ax_pos.set_ylim(min(all_lats) - lat_margin, max(all_lats) + lat_margin)
                
                if len(prediction_errors) > 0:
                    times_list = list(error_timestamps)
                    err_list = list(prediction_errors)
                    
                    self.err_line.set_data(times_list, err_list)
                    
                    if len(times_list) > 1:
                        self.avg_line.set_data(
                            [times_list[0], times_list[-1]], 
                            [avg_error, avg_error]
                        )
                    
                    if len(times_list) > 0:
                        self.ax_err.set_xlim(max(0, times_list[-1] - 60), times_list[-1] + 5)
                        max_err = max(err_list) if err_list else 100
                        self.ax_err.set_ylim(0, max(50, max_err * 1.2))
                
                self._update_labels()
                self.canvas.draw_idle()
        
        self.root.after(200, self.update_plot)
    
    def _update_labels(self):
        """Update info labels."""
        if current_error > 0:
            self.error_label.config(text=f"Prediction Error: {current_error:.1f} m")
        else:
            self.error_label.config(text="Prediction Error: waiting...")
        
        self.avg_error_label.config(text=f"Avg Error: {avg_error:.1f} m")
        self.buffer_label.config(text=f"Pending: {len(prediction_buffer)}")
        self.actual_label.config(text=f"Lat: {current_actual[0]:.6f}, Lon: {current_actual[1]:.6f}")
        self.predicted_label.config(text=f"Lat: {current_predicted[0]:.6f}, Lon: {current_predicted[1]:.6f}")
    
    def run(self):
        """Run the GUI."""
        self.root.mainloop()


def create_gui():
    """Create and run the GUI in the current thread."""
    gui = PlotGUI()
    gui.run()


def get_prediction_time():
    """Get current prediction time (thread-safe)."""
    with prediction_lock:
        return prediction_time
