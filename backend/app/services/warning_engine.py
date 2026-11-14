"""Warning engine — generates deduplicated, event-based warnings from sensor data.

OPTIMIZATION (Phase 4/5): accept a shared `now` timestamp so the caller
calls datetime.now() once per tick instead of once per sensor.
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

ZONE_DISPLAY = {
    "front_left": "Front Left",
    "front_center": "Front Center",
    "front_center_left": "Front Center Left",
    "front_center_right": "Front Center Right",
    "front_right": "Front Right",
    "left_side": "Left Side",
    "right_side": "Right Side",
    "roof_center": "Roof Center",
}


class WarningEngine:
    """
    Generates warnings based on sensor readings.
    Deduplicates: a new warning for the same sensor is only generated
    if the warning level changes or enough time has passed (cooldown).
    """

    COOLDOWN_SECONDS = 10  # min seconds between same-sensor same-level warnings

    def __init__(self):
        # last_warnings: sensor_id -> (level, timestamp)
        self._last_warnings: Dict[str, Tuple[str, datetime]] = {}

    def classify_distance(
        self,
        distance_cm: Optional[float],
        critical: float = 50.0,
        warning: float = 100.0,
        caution: float = 150.0,
        max_range: float = 400.0,
    ) -> str:
        if distance_cm is None or distance_cm <= 0 or distance_cm > max_range:
            return "CLEAR"
        if distance_cm <= critical:
            return "CRITICAL"
        if distance_cm <= warning:
            return "WARNING"
        if distance_cm <= caution:
            return "CAUTION"
        return "SAFE"

    def should_generate_warning(
        self, sensor_id: str, level: str, now: datetime
    ) -> bool:
        if level in ("SAFE", "CLEAR"):
            return False
        last = self._last_warnings.get(sensor_id)
        if last is None:
            return True
        last_level, last_time = last
        if last_level != level:
            return True
        # Ensure last_time is timezone aware for comparison
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        if (now - last_time).total_seconds() >= self.COOLDOWN_SECONDS:
            return True
        return False

    def build_warning_message(
        self,
        sensor_id: str,
        zone: str,
        distance_cm: Optional[float],
        level: str,
    ) -> str:
        zone_name = ZONE_DISPLAY.get(zone, zone)
        dist_str = f"{distance_cm:.0f}" if distance_cm is not None else "?"
        if level == "CRITICAL":
            return f"CRITICAL: Obstacle detected {dist_str} cm in {zone_name} zone [{sensor_id}]"
        if level == "WARNING":
            return f"WARNING: Obstacle detected {dist_str} cm in {zone_name} zone [{sensor_id}]"
        if level == "CAUTION":
            return f"CAUTION: Object approaching {zone_name} zone [{sensor_id}] at {dist_str} cm"
        return f"ALERT: Sensor {sensor_id} - {zone_name}"

    def process_sensor(
        self,
        sensor_id: str,
        zone: str,
        distance_cm: Optional[float],
        thresholds: Optional[dict] = None,
        now: Optional[datetime] = None,
    ) -> Optional[dict]:
        """
        Process a sensor reading and return a warning dict if one should be generated,
        or None if no warning is needed.
        
        OPTIMIZATION: accepts an optional `now` so the caller can pass a single
        timestamp for the whole tick instead of calling datetime.now() per sensor.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        th = thresholds or {}
        level = self.classify_distance(
            distance_cm,
            critical=th.get("critical_cm", 50.0),
            warning=th.get("warning_cm", 100.0),
            caution=th.get("caution_cm", 150.0),
            max_range=th.get("max_range_cm", 400.0),
        )

        if not self.should_generate_warning(sensor_id, level, now):
            return None

        self._last_warnings[sensor_id] = (level, now)
        message = self.build_warning_message(sensor_id, zone, distance_cm, level)
        return {
            "sensor_id": sensor_id,
            "zone": zone,
            "distance_cm": distance_cm,
            "warning_level": level,
            "warning_message": message,
            "acknowledged": False,
            "timestamp": now,
        }

    def reset(self):
        self._last_warnings.clear()


warning_engine = WarningEngine()
