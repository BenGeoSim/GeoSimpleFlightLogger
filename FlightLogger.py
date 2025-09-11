# Required installations:
# pip install xplaneconnect simplekml

import tkinter as tk
from tkinter import filedialog
import threading
import time
import os
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

        # Track last states
        self.last_gear_state = None
        self.last_flap_state = None
        self.last_stall_state = None
        self.last_engine_fire_states = {0: None, 1: None}

        # Define flap notches we care about
        self.flap_notches = {
            0.25: "Flaps 1/4",
            1/3:  "Flaps 1/3",
            0.50: "Flaps 1/2",
            2/3:  "Flaps 2/3",
            0.75: "Flaps 3/4",
        }

        # Path to local GPXSee icons folder
        self.icon_path = os.path.join(os.path.dirname(__file__), "icons")

        # GPXSee-style icons (replace filenames with the ones you actually have)
        self.icons = {
            "gear_up":   os.path.join(self.icon_path, "gear_up.png"),
            "gear_down": os.path.join(self.icon_path, "gear_down.png"),
            "flaps":     os.path.join(self.icon_path, "flaps.png"),
            "stall_on":  os.path.join(self.icon_path, "stall_on.png"),
            "stall_off": os.path.join(self.icon_path, "stall_off.png"),
            "fire_on":   os.path.join(self.icon_path, "fire_on.png"),
            "fire_off":  os.path.join(self.icon_path, "fire_off.png"),
        }

    def set_status(self, msg):
        self.status_label.config(text=f"Status: {msg}")

    def update_latest(self, lat, lon, alt):
        self.latest_label.config(text=f"Latest Position: {lat:.6f}, {lon:.6f}, {alt:.2f} m")

    def start_logging(self):
        if not self.running:
            self.running = True
            self.coords = []
            self.last_gear_state = None
            self.last_flap_state = None
            self.last_stall_state = None
            self.last_engine_fire_states = {0: None, 1: None}
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

    def add_waypoint(self, label, lat, lon, alt, icon_file):
        wp = self.kml.newpoint(name=label, coords=[(lon, lat, alt)])
        wp.altitudemode = simplekml.AltitudeMode.absolute
        wp.description = f"{label} at {lat:.6f}, {lon:.6f}, {alt:.2f} m"
        wp.style.iconstyle.icon.href = icon_file  # local path or URL
        wp.style.iconstyle.scale = 1.2
        print(f"Added waypoint: {label} at {lat:.6f}, {lon:.6f}, {alt:.2f}m")

    def log_loop(self):
        while self.running:
            try:
                # --- Position ---
                pos = self.client.getPOSI()
                lat, lon, alt = pos[0], pos[1], pos[2]
                self.coords.append((lon, lat, alt))
                self.update_latest(lat, lon, alt)

                # --- Gear state ---
                gear_state = self.client.getDREF("sim/aircraft/parts/acf_gear_deploy")[0]
                if gear_state is not None:
                    gear_state = int(round(gear_state))
                    if gear_state in (0, 1) and gear_state != self.last_gear_state:
                        self.last_gear_state = gear_state
                        if gear_state == 0:
                            self.add_waypoint("Gear Up", lat, lon, alt, self.icons["gear_up"])
                        else:
                            self.add_waypoint("Gear Down", lat, lon, alt, self.icons["gear_down"])

                # --- Flap state ---
                flap_value = self.client.getDREF("sim/flightmodel/controls/flaprat")[0]
                if flap_value is not None:
                    flap_value = round(flap_value, 2)
                    for notch, label in self.flap_notches.items():
                        if abs(flap_value - notch) < 0.01 and self.last_flap_state != notch:
                            self.last_flap_state = notch
                            self.add_waypoint(label, lat, lon, alt, self.icons["flaps"])

                # --- Stall warning state ---
                stall_state = self.client.getDREF("sim/cockpit2/annunciators/stall_warning")[0]
                if stall_state is not None:
                    stall_state = int(round(stall_state))
                    if stall_state in (0, 1) and stall_state != self.last_stall_state:
                        self.last_stall_state = stall_state
                        if stall_state == 1:
                            self.add_waypoint("Stall Warning ON", lat, lon, alt, self.icons["stall_on"])
                        else:
                            self.add_waypoint("Stall Warning OFF", lat, lon, alt, self.icons["stall_off"])

                # --- Engine fire annunciators (index 0 and 1) ---
                fire_states = self.client.getDREF("sim/cockpit2/annunciators/engine_fires")
                if fire_states is not None and len(fire_states) >= 2:
                    for i in [0, 1]:
                        state = int(round(fire_states[i]))
                        if state in (0, 1) and state != self.last_engine_fire_states[i]:
                            self.last_engine_fire_states[i] = state
                            if state == 1:
                                self.add_waypoint(f"Engine {i+1} Fire ON", lat, lon, alt, self.icons["fire_on"])
                            else:
                                self.add_waypoint(f"Engine {i+1} Fire OFF", lat, lon, alt, self.icons["fire_off"])

            except Exception as e:
                self.set_status(f"Error: {e}")
            time.sleep(1)

def main():
    root = tk.Tk()
    root.title("GeoSimpleFlightLogger")

    # Fix window size (500px wide, 260px tall to fit wrapped labels)
    root.geometry("500x260")
    root.resizable(False, False)

    # Static description label with wrapping
    tk.Label(
        root,
        text="This is a simple flight logger that uses a KML file to record flight paths. "
             "This file can be viewed in Google Earth, GPXSee or other KML-compatible software.",
        wraplength=480,
        justify="left"
    ).pack(pady=5)

    # Status label with wrapping
    status_label = tk.Label(root, text="Status: Idle", wraplength=480, justify="left")
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
