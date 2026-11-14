"""Data processing service — handles telemetry, DB writes, and WS broadcasts.

OPTIMIZATIONS applied:
- Phase 1: All functions are now async, using AsyncSession
- Phase 2: Individual commits removed — caller does ONE commit at the end
- Phase 4: classify_distance computed once per sensor, result carried through
- Phase 5: Batch-write support via a separate flush function
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, update
import json
import logging

from app.models.sensor import (
    SensorReading, ObstacleEvent, WarningEvent,
    TrafficSignalEvent, DeviceStatus, SystemConfig
)
from app.schemas.schemas import TelemetryPayload, ThresholdConfig
from app.services.warning_engine import warning_engine
from app.core.config import settings

logger = logging.getLogger(__name__)


def classify_distance(distance_cm: Optional[float]) -> str:
    """Classify a single distance reading. Pure function, no I/O."""
    return warning_engine.classify_distance(
        distance_cm,
        critical=settings.CRITICAL_THRESHOLD_CM,
        warning=settings.WARNING_THRESHOLD_CM,
        caution=settings.CAUTION_THRESHOLD_CM,
        max_range=settings.MAX_RANGE_CM,
    )


# ─── Phase 4: Pre-compute all classifications for a tick ─────────────────────

def precompute_classifications(
    payload: TelemetryPayload,
) -> List[Tuple[str, str]]:
    """
    Return [(warning_level, zone), ...] for each sensor in the payload.
    Called ONCE per tick; the result is reused for DB writes AND WS broadcast.
    """
    return [
        (classify_distance(s.distance_cm), s.zone)
        for s in payload.sensors
    ]


# ─── Phase 2: No-commit save helpers ─────────────────────────────────────────
# These add ORM objects to the session but do NOT commit.
# The caller (process_telemetry) issues a single commit at the end.


async def save_sensor_readings(
    db: AsyncSession,
    payload: TelemetryPayload,
    levels: List[Tuple[str, str]],
) -> List[SensorReading]:
    """Persist raw sensor readings.  Uses pre-computed warning levels."""
    readings = []
    ts = payload.timestamp or datetime.now(timezone.utc)
    for sensor, (level, _zone) in zip(payload.sensors, levels):
        reading = SensorReading(
            sensor_id=sensor.sensor_id,
            zone=sensor.zone,
            distance_cm=sensor.distance_cm,
            obstacle_detected=sensor.obstacle_detected,
            warning_level=level,
            timestamp=ts,
        )
        db.add(reading)
        readings.append(reading)

    # Save meaningful obstacle events (detected only)
    for sensor, (level, _zone) in zip(payload.sensors, levels):
        if sensor.obstacle_detected and sensor.distance_cm is not None:
            event = ObstacleEvent(
                sensor_id=sensor.sensor_id,
                zone=sensor.zone,
                distance_cm=sensor.distance_cm,
                severity=level,
                event_type="DETECTED",
                timestamp=ts,
            )
            db.add(event)

    # NO commit here — caller commits once
    return readings


async def save_warnings(
    db: AsyncSession,
    payload: TelemetryPayload,
    now: datetime,
) -> List[WarningEvent]:
    """Generate and persist deduplicated warnings."""
    warnings = []
    thresholds = {
        "critical_cm": settings.CRITICAL_THRESHOLD_CM,
        "warning_cm": settings.WARNING_THRESHOLD_CM,
        "caution_cm": settings.CAUTION_THRESHOLD_CM,
        "max_range_cm": settings.MAX_RANGE_CM,
    }
    for sensor in payload.sensors:
        w = warning_engine.process_sensor(
            sensor.sensor_id,
            sensor.zone,
            sensor.distance_cm,
            thresholds=thresholds,
            now=now,
        )
        if w:
            warning = WarningEvent(**w)
            db.add(warning)
            await db.flush()  # flush to generate .id for WS broadcast
            warnings.append(warning)
    # NO commit
    return warnings


async def save_traffic_event(
    db: AsyncSession, payload: TelemetryPayload
) -> Optional[TrafficSignalEvent]:
    """Persist a traffic-signal change (only when state actually changes)."""
    if not payload.traffic_signal:
        return None
    # Check last state
    result = await db.execute(
        select(TrafficSignalEvent)
        .order_by(TrafficSignalEvent.id.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if last and last.signal_state == payload.traffic_signal.state.value:
        return None
    event = TrafficSignalEvent(
        signal_state=payload.traffic_signal.state.value,
        duration_seconds=payload.traffic_signal.duration_seconds,
        timestamp=payload.timestamp or datetime.now(timezone.utc),
    )
    db.add(event)
    # NO commit
    return event


async def update_device_status(
    db: AsyncSession, device_id: str, status: str = "CONNECTED"
):
    """Create or update a device's connection status."""
    result = await db.execute(
        select(DeviceStatus).where(DeviceStatus.device_name == device_id)
    )
    device = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if device:
        device.connection_status = status
        device.last_seen = now
    else:
        device = DeviceStatus(
            device_name=device_id,
            device_type="ESP32",
            connection_status=status,
            last_seen=now,
        )
        db.add(device)
    # NO commit
    return device


# ─── Phase 5: Batch flush callback ───────────────────────────────────────────

async def flush_write_batch(batch: list):
    """
    Called by WriteQueue — receives a list of TelemetryPayload items
    and writes them all in a single transaction.
    """
    from app.database.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        for payload in batch:
            levels = precompute_classifications(payload)
            await save_sensor_readings(db, payload, levels)
            await save_warnings(db, payload, now)
            await save_traffic_event(db, payload)
            await update_device_status(db, payload.device_id)
        await db.commit()  # ONE commit for the entire batch


# ─── Startup helpers ─────────────────────────────────────────────────────────

async def init_devices(db: AsyncSession):
    """Initialize default device records."""
    defaults = [
        ("fogguard-arduino", "Arduino"),
        ("fogguard-esp32", "ESP32"),
        ("fogguard-sensor-s1", "Ultrasonic Sensor"),
        ("fogguard-sensor-s2", "Ultrasonic Sensor"),
        ("fogguard-sensor-s3", "Ultrasonic Sensor"),
        ("fogguard-sensor-s4", "Ultrasonic Sensor"),
        ("fogguard-sensor-s5", "Ultrasonic Sensor"),
        ("fogguard-sensor-s6", "Ultrasonic Sensor"),
        ("fogguard-traffic-signal", "Traffic Signal"),
    ]
    for name, dtype in defaults:
        result = await db.execute(
            select(DeviceStatus).where(DeviceStatus.device_name == name)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            db.add(DeviceStatus(
                device_name=name,
                device_type=dtype,
                connection_status="UNKNOWN",
                last_seen=None,
            ))
    await db.commit()


async def load_persistent_settings(db: AsyncSession):
    """Load persisted threshold configurations on startup."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "thresholds")
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        try:
            data = json.loads(cfg.value)
            settings.CRITICAL_THRESHOLD_CM = float(
                data.get("critical_cm", settings.CRITICAL_THRESHOLD_CM)
            )
            settings.WARNING_THRESHOLD_CM = float(
                data.get("warning_cm", settings.WARNING_THRESHOLD_CM)
            )
            settings.CAUTION_THRESHOLD_CM = float(
                data.get("caution_cm", settings.CAUTION_THRESHOLD_CM)
            )
            settings.MAX_RANGE_CM = float(
                data.get("max_range_cm", settings.MAX_RANGE_CM)
            )
            logger.info(f"Loaded persistent thresholds from DB: {data}")
        except Exception as e:
            logger.error(f"Failed to parse stored thresholds: {e}")


async def persist_thresholds(db: AsyncSession, config: ThresholdConfig):
    """Save updated threshold configurations to database."""
    data_str = json.dumps({
        "critical_cm": config.critical_cm,
        "warning_cm": config.warning_cm,
        "caution_cm": config.caution_cm,
        "max_range_cm": config.max_range_cm,
    })
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "thresholds")
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        cfg.value = data_str
    else:
        db.add(SystemConfig(key="thresholds", value=data_str))
    await db.commit()


async def cleanup_old_readings(db: AsyncSession, retention_days: int) -> int:
    """
    Remove high-frequency raw SensorReading records older than retention_days.
    Retains ObstacleEvent, WarningEvent, and TrafficSignalEvent indefinitely
    for long-term historical analysis and audit.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await db.execute(
        delete(SensorReading).where(SensorReading.timestamp < cutoff)
    )
    deleted = result.rowcount
    await db.commit()
    logger.info(
        f"Data retention cleanup: purged {deleted} raw readings "
        f"older than {retention_days} days."
    )
    return deleted
