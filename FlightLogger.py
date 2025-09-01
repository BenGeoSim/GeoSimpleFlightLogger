# Required installations:
# pip install xplaneconnect simplekml

import tkinter as tk
from tkinter import filedialog
import threading
import time
from xpc import XPlaneConnect
import simplekml

class KMLLogger:
    def __init__(self, status_label, latest_label, description_text="Flight Path Log"):
        self.kml = simplekml.Kml()
        self.coords = []
        self.running = False
        self.client = XPlaneConnect()
        self.thread = None
        self.status_label = status_label
        self.latest_label = latest_label
        self.description_text = description_text
        self.last_gear_state = None  # Track last gear state

    def set_status(self, msg):
        self.status_label.config(text=f"Status: {msg}")

    def update_latest(self, lat, lon, alt):
        self.latest_label.config(text=f"Latest Position: {lat:.6f}, {lon:.6f}, {alt:.2f} m")

    def start_logging(self):
        if not self.running:
            self.running = True
            self.coords = []
            self.last_gear_state = None
            self.set_status("Logging started...")
            self.thread = threading.Thread(target=self.log_loop, daemon=True)
            self.thread.start()
        else:
            self.set_status("Already logging.")

    def stop_logging(self):
        if self.running:
            self.running = False
            if self.coords:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".kml",
                    filetypes=[("KML files", "*.kml")],
                    title="Save KML File"
                )
                if filename:
                    # Add main flight path
                    ls = self.kml.newlinestring(name="Flight Path", description=self.description_text)
                    ls.coords = self.coords
                    ls.altitudemode = simplekml.AltitudeMode.absolute
                    ls.extrude = 1
                    ls.style.linestyle.color = simplekml.Color.red
                    ls.style.linestyle.width = 3
                    # Save the file
                    self.kml.save(filename)
                    self.set_status(f"KML saved as {filename}")
                else:
                    self.set_status("Save cancelled. No file written.")
            else:
                self.set_status("No points logged. Nothing saved.")
        else:
            self.set_status("Not currently logging.")

    def log_loop(self):
        while self.running:
            try:
                # Position
                pos = self.client.getPOSI()
                lat, lon, alt = pos[0], pos[1], pos[2]
                self.coords.append((lon, lat, alt))
                self.update_latest(lat, lon, alt)

                # Gear state
                gear_state = self.client.getDREF("sim/aircraft/parts/acf_gear_deploy")[0]
                if gear_state is not None:
                    gear_state = int(round(gear_state))
                    if gear_state in (0, 1) and gear_state != self.last_gear_state:
                        self.last_gear_state = gear_state
                        label = "Gear Up" if gear_state == 0 else "Gear Down"
                        wp = self.kml.newpoint(name=label, coords=[(lon, lat, alt)])
                        wp.altitudemode = simplekml.AltitudeMode.absolute
                        wp.description = f"Waypoint: {label} at {lat:.6f}, {lon:.6f}, {alt:.2f} m"
                        print(f"Added waypoint: {label} at {lat:.6f}, {lon:.6f}, {alt:.2f}m")

            except Exception as e:
                self.set_status(f"Error: {e}")
            time.sleep(1)

def main():
    root = tk.Tk()
    root.title("KML Logger")

    # Fix window size (500px wide, 220px tall to fit labels)
    root.geometry("500x220")
    root.resizable(False, False)

    # Static description label
    tk.Label(root, text="Description: Flight Path Log").pack(pady=5)

    status_label = tk.Label(root, text="Status: Idle")
    status_label.pack(pady=5)

    latest_label = tk.Label(root, text="Latest Position: N/A")
    latest_label.pack(pady=5)

    logger = KMLLogger(status_label, latest_label, description_text="Flight Path Log")

    # Frame for side-by-side buttons
    button_frame = tk.Frame(root)
    button_frame.pack(pady=5)

    start_btn = tk.Button(button_frame, text="Start Logging", width=20, command=logger.start_logging)
    start_btn.pack(side="left", padx=10)

    stop_btn = tk.Button(button_frame, text="Stop Logging", width=20, command=logger.stop_logging)
    stop_btn.pack(side="left", padx=10)

    root.mainloop()

if __name__ == "__main__":
    main()
