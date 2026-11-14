#!/usr/bin/env python3
"""
FogGuard USB Serial Bridge CLI Tool.
Reads live distance telemetry from an Arduino connected via USB cable,
and pushes it to the FogGuard FastAPI backend (http://localhost:8000).

Supports:
1. JSON-line format: {"traffic":"GREEN","sensors":[{"id":"S1","zone":"front_left","dist":45.2},...]}
2. Line-by-line format from the Arduino code:
     Sensor 1: 45.20 cm
     Sensor 2: 120.30 cm
     Sensor 3: No Echo
     Sensor 4: 85.10 cm
     Sensor 5: 200.00 cm
     Sensor 6: 15.50 cm

The port is held while this script runs. Stop it (Ctrl+C) before flashing the board.

Usage:
    python tools/arduino_serial_bridge.py [--port COM5] [--baud 115200] [--url http://localhost:8000/api/v1/iot/telemetry]
"""

import sys
import json
import re
import argparse
from datetime import datetime, timezone

try:
    import serial
    import serial.tools.list_ports
    import requests
except ImportError:
    print("Please install requirements: pip install pyserial requests")
    sys.exit(1)

NUM_SENSORS = 6
DETECT_THRESHOLD_CM = 150.0

# Must match where S1-S6 are physically mounted.
ZONE_MAP_6 = {
    "S1": "front_left",
    "S2": "front_center_left",
    "S3": "front_center_right",
    "S4": "front_right",
    "S5": "left_side",
    "S6": "right_side",
}

SENSOR_RE = re.compile(
    r"Sensor\s+([1-6])\s*:\s*(?:([0-9.]+)\s*cm|No Echo)", re.IGNORECASE
)

sensor_buffer = {}


def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    if not ports:
        return None
    for p in ports:
        desc = (p.description or "").lower()
        if any(k in desc for k in ["arduino", "ch340", "cp210", "ftdi", "usb serial"]):
            return p.device
    return ports[0].device


def parse_line(line: str):
    global sensor_buffer
    line = line.strip()
    if not line:
        return None

    # Format 1: full JSON line
    if line.startswith("{") and line.endswith("}"):
        try:
            return json.loads(line)
        except Exception:
            pass

    # Format 2: 'Sensor <n>: <distance> cm' or 'Sensor <n>: No Echo'
    m = SENSOR_RE.match(line)
    if not m:
        return None

    idx = int(m.group(1))
    if idx == 1:
        sensor_buffer = {}  # a new sweep starts: drop any leftovers
    sensor_buffer[f"S{idx}"] = float(m.group(2)) if m.group(2) else None

    if idx != NUM_SENSORS:
        return None

    # Sensor 6 arrived: flush only if the whole sweep is present
    if len(sensor_buffer) < NUM_SENSORS:
        sensor_buffer = {}
        return None

    sensors = []
    for i in range(1, NUM_SENSORS + 1):
        sid = f"S{i}"
        dist = sensor_buffer[sid]
        sensors.append({
            "id": sid,
            "zone": ZONE_MAP_6[sid],
            "dist": dist,
            "det": (dist is not None and dist <= DETECT_THRESHOLD_CM),
        })
    sensor_buffer = {}
    # No "traffic" key: the bridge must not force the signal to GREEN.
    return {"sensors": sensors}


def main():
    parser = argparse.ArgumentParser(description="FogGuard USB Serial Bridge")
    parser.add_argument("--port", type=str, default=None, help="COM / tty port (default: auto-detect)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--url", type=str, default="http://localhost:8000/api/v1/iot/telemetry", help="Backend telemetry endpoint")
    args = parser.parse_args()

    port = args.port or find_arduino_port()
    if not port:
        print("[ERROR] No USB serial ports detected. Please plug in your Arduino and try again.")
        sys.exit(1)

    print(f"[FogGuard] Connecting to Arduino on {port} @ {args.baud} baud...")
    try:
        ser = serial.Serial(port, args.baud, timeout=1.0)
    except Exception as e:
        print(f"[ERROR] Could not open serial port {port}: {e}")
        sys.exit(1)

    print(f"[FogGuard] Connected! Streaming distance telemetry to {args.url}")
    print("[FogGuard] Watching for sensor readings (Sensor 1..6)...")
    print("[FogGuard] Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                raw_line = ser.readline()
            except serial.SerialException as e:
                print(f"[ERROR] Serial connection lost: {e}")
                break

            if not raw_line:
                continue

            text = raw_line.decode("utf-8", errors="ignore").strip()
            data = parse_line(text)
            if not data or "sensors" not in data:
                continue

            payload = {
                "device_id": "fogguard-arduino",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sensors": [
                    {
                        "sensor_id": s.get("id"),
                        "zone": s.get("zone", "front_center"),
                        "distance_cm": s.get("dist"),
                        "obstacle_detected": s.get("det", False),
                    }
                    for s in data["sensors"]
                ],
                "traffic_signal": {
                    "state": data.get("traffic", "GREEN"),
                    "duration_seconds": data.get("dur", 30),
                } if "traffic" in data else None,
            }

            try:
                resp = requests.post(args.url, json=payload, timeout=2.0)
                if resp.status_code == 200:
                    dists = [
                        f"{s['sensor_id']}={s['distance_cm']:.1f}cm"
                        for s in payload["sensors"]
                        if s["distance_cm"] is not None
                    ]
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 3D Cuboids Updated: {', '.join(dists) if dists else 'All Clear'}")
                else:
                    print(f"[WARN] Backend responded with HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"[WARN] Failed to post telemetry: {e}")

    except KeyboardInterrupt:
        print("\n[FogGuard] Bridge stopped.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()