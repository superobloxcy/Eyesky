"""
GUI for selecting celestial objects to track and generating ephemeris logs.
Uses Skyfield to fetch live ephemeris data instead of pre-downloaded files.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from datetime import datetime, timedelta
import pytz
from pathlib import Path

from config import load_config
from ephemeris_tracker import (
    get_available_objects, 
    get_object_list_for_gui, 
    generate_tracking_log
)


class EphemerisTrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ephemeris Tracker - Object Selection")
        self.root.geometry("800x700")
        
        # Load observer position from config
        try:
            config = load_config()
            self.observer_lat = config['home_lat']
            self.observer_lon = config['home_lon']
            self.observer_alt = config['home_alt']
        except Exception as e:
            messagebox.showerror("Config Error", f"Failed to load config: {e}")
            self.observer_lat = -27.988
            self.observer_lon = 153.323
            self.observer_alt = 67
        
        self.selected_objects = []
        self.is_generating = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the GUI components."""
        
        # Title and info
        title_frame = ttk.Frame(self.root)
        title_frame.pack(padx=10, pady=10, fill=tk.X)
        
        ttk.Label(title_frame, text="Ephemeris Tracker", 
                 font=("Arial", 14, "bold")).pack()
        ttk.Label(title_frame, 
                 text=f"Observer: Lat={self.observer_lat}°, Lon={self.observer_lon}°, Alt={self.observer_alt}m",
                 font=("Arial", 9)).pack()
        
        # Object selection
        obj_frame = ttk.LabelFrame(self.root, text="Select Objects to Track", padding=10)
        obj_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # Listbox with scrollbar
        scrollbar = ttk.Scrollbar(obj_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.object_listbox = tk.Listbox(obj_frame, yscrollcommand=scrollbar.set,
                                        selectmode=tk.MULTIPLE, height=12)
        self.object_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.object_listbox.yview)
        
        # Populate listbox with available objects
        available_objects = get_object_list_for_gui()
        for obj in available_objects:
            self.object_listbox.insert(tk.END, obj)
        
        # Pre-select common objects
        for i, obj in enumerate(available_objects):
            if obj.lower() in ['sun', 'moon']:
                self.object_listbox.selection_set(i)
        
        # Parameters frame
        params_frame = ttk.LabelFrame(self.root, text="Tracking Parameters", padding=10)
        params_frame.pack(padx=10, pady=10, fill=tk.X)
        
        # Duration
        ttk.Label(params_frame, text="Duration (hours):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.duration_var = tk.DoubleVar(value=24)
        duration_spinbox = ttk.Spinbox(params_frame, from_=0.1, to=365*24, textvariable=self.duration_var,
                                       width=15)
        duration_spinbox.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Time step
        ttk.Label(params_frame, text="Time Step (seconds):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.timestep_var = tk.IntVar(value=300)  # 5 minutes default
        timestep_spinbox = ttk.Spinbox(params_frame, from_=1, to=3600, textvariable=self.timestep_var,
                                       width=15)
        timestep_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # Output file
        ttk.Label(params_frame, text="Output File (optional):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.output_var = tk.StringVar()
        output_entry = ttk.Entry(params_frame, textvariable=self.output_var, width=40)
        output_entry.grid(row=2, column=1, sticky=tk.EW, padx=5)
        ttk.Button(params_frame, text="Browse", command=self.browse_output).grid(row=2, column=2, padx=5)
        
        params_frame.columnconfigure(1, weight=1)
        
        # Status and buttons
        status_frame = ttk.Frame(self.root)
        status_frame.pack(padx=10, pady=10, fill=tk.X)
        
        self.status_label = ttk.Label(status_frame, text="Ready", foreground="blue")
        self.status_label.pack(side=tk.LEFT)
        
        # Generate button
        self.generate_btn = ttk.Button(status_frame, text="Generate Tracking Log", 
                                       command=self.generate_log)
        self.generate_btn.pack(side=tk.RIGHT, padx=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var,
                                           maximum=100, mode='determinate')
        self.progress_bar.pack(padx=10, pady=5, fill=tk.X)
        
        # Log output
        log_frame = ttk.LabelFrame(self.root, text="Generation Log", padding=5)
        log_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        scrollbar_log = ttk.Scrollbar(log_frame)
        scrollbar_log.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=6, yscrollcommand=scrollbar_log.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_log.config(command=self.log_text.yview)
    
    def browse_output(self):
        """Open file dialog for output file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir="tracking_logs"
        )
        if file_path:
            self.output_var.set(file_path)
    
    def generate_log(self):
        """Generate tracking log in a separate thread."""
        selected_indices = self.object_listbox.curselection()
        
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select at least one object to track.")
            return
        
        # Get selected object names
        all_objects = get_object_list_for_gui()
        selected_names = [all_objects[i] for i in selected_indices]
        
        # Disable button during generation
        self.generate_btn.config(state=tk.DISABLED)
        self.is_generating = True
        self.log_text.delete(1.0, tk.END)
        
        # Run generation in background thread
        thread = threading.Thread(
            target=self._generate_thread,
            args=(selected_names,),
            daemon=True
        )
        thread.start()
    
    def _generate_thread(self, target_names):
        """Background thread for log generation."""
        try:
            self.update_log(f"Starting ephemeris data generation...\n")
            self.update_log(f"Objects: {', '.join(target_names)}\n")
            self.update_log(f"Duration: {self.duration_var.get()} hours\n")
            self.update_log(f"Time Step: {self.timestep_var.get()} seconds\n\n")
            
            output_file = self.output_var.get() if self.output_var.get() else None
            if output_file:
                output_file = Path(output_file).name  # Extract filename only
            
            # Generate the log
            log_path = generate_tracking_log(
                self.observer_lat,
                self.observer_lon,
                self.observer_alt,
                target_names,
                self.duration_var.get(),
                self.timestep_var.get(),
                output_file
            )
            
            self.update_log(f"\n✓ Successfully generated: {log_path}\n")
            self.update_log(f"\nLog file is ready for verification!\n")
            self.update_log(f"You can now run the serial handler to track these objects.")
            
            # Show completion message
            self.root.after(0, lambda: messagebox.showinfo(
                "Success", 
                f"Tracking log generated successfully!\n\nFile: {log_path}"
            ))
        
        except Exception as e:
            self.update_log(f"\n✗ Error: {str(e)}\n")
            self.root.after(0, lambda: messagebox.showerror("Generation Failed", str(e)))
        
        finally:
            self.is_generating = False
            self.root.after(0, lambda: self.generate_btn.config(state=tk.NORMAL))
    
    def update_log(self, message):
        """Thread-safe log update."""
        self.root.after(0, lambda: self._update_log_main(message))
    
    def _update_log_main(self, message):
        """Main thread log update."""
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.root.update()


def main():
    root = tk.Tk()
    gui = EphemerisTrackerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
