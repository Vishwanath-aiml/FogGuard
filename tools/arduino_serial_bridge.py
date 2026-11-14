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

Usage:
    python tools/arduino_serial_bridge.py [--port COM3] [--baud 115200] [--url http://localhost:8000/api/v1/iot/telemetry]
"""

import sys
import time
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

ZONE_MAP_6 = {
    "S1": "front_left",
    "S2": "front_center_left",
    "S3": "front_center_right",
    "S4": "front_right",
    "S5": "left_side",
    "S6": "right_side",
}

ZONE_MAP_4 = {
    "S1": "front_left",
    "S2": "front_center",
    "S3": "front_right",
    "S4": "roof_center",
}

sensor_buffer = {}
max_sensor_seen = 4


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
    global sensor_buffer, max_sensor_seen
    line = line.strip()
    if not line:
        return None

    # Format 1: Full JSON line
    if line.startswith("{") and line.endswith("}"):
        try:
            return json.loads(line)
        except Exception:
            pass

    # Format 2: Line-by-line Arduino monitor format: 'Sensor <index>: <distance> cm' or 'Sensor <index>: No Echo'
    m = re.match(r"Sensor\s+([1-6])\s*:\s*(?:([0-9.]+)\s*cm|No Echo)", line, re.IGNORECASE)
    if m:
        idx = int(m.group(1))
        sensor_id = f"S{idx}"
        dist_val = float(m.group(2)) if m.group(2) else None
        sensor_buffer[sensor_id] = dist_val

        if idx > max_sensor_seen:
            max_sensor_seen = idx

        is_six_sensor_mode = max_sensor_seen >= 5
        target_flush = 6 if is_six_sensor_mode else 4

        if idx == target_flush or len(sensor_buffer) >= target_flush:
            active_map = ZONE_MAP_6 if is_six_sensor_mode else ZONE_MAP_4
            sensors = []
            for i in range(1, target_flush + 1):
                sid = f"S{i}"
                dist = sensor_buffer.get(sid)
                sensors.append({
                    "id": sid,
                    "zone": active_map[sid],
                    "dist": dist,
                    "det": (dist is not None and dist <= 150.0)
                })
            sensor_buffer = {}
            return {"traffic": "GREEN", "dur": 30, "sensors": sensors}

    return None


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
            raw_line = ser.readline()
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
                        "obstacle_detected": s.get("det", False)
                    }
                    for s in data["sensors"]
                ],
                "traffic_signal": {
                    "state": data.get("traffic", "GREEN"),
                    "duration_seconds": data.get("dur", 30)
                } if "traffic" in data else None
            }

            try:
                resp = requests.post(args.url, json=payload, timeout=2.0)
                if resp.status_code == 200:
                    dists = [f"{s['sensor_id']}={s['distance_cm']:.1f}cm" for s in payload["sensors"] if s['distance_cm'] is not None]
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 3D Cuboids Updated: {', '.join(dists) if dists else 'All Clear'}")
                else:
                    print(f"[WARN] Backend responded with HTTP {resp.status_code}")
            except Exception as e:
                print(f"[WARN] Failed to post telemetry: {e}")

    except KeyboardInterrupt:
        print("\n[FogGuard] Bridge stopped.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
