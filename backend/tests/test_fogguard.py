"""Backend tests for FogGuard (updated for async DB)."""
import pytest
import asyncio
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database.db import Base, get_db
from app.services.warning_engine import WarningEngine
from app.simulation.engine import SimulationEngine, NormalScenario, CriticalFrontObstacleScenario


# ─── Test Database ────────────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_fogguard.db"
test_engine = create_async_engine(TEST_DATABASE_URL)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture()
async def db():
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture()
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ─── Warning Engine Tests ─────────────────────────────────────────────────────
class TestWarningEngine:
    def test_classify_critical(self):
        engine = WarningEngine()
        assert engine.classify_distance(25.0) == "CRITICAL"

    def test_classify_warning(self):
        engine = WarningEngine()
        assert engine.classify_distance(75.0) == "WARNING"

    def test_classify_caution(self):
        engine = WarningEngine()
        assert engine.classify_distance(125.0) == "CAUTION"

    def test_classify_safe(self):
        engine = WarningEngine()
        assert engine.classify_distance(200.0) == "SAFE"

    def test_classify_clear_none(self):
        engine = WarningEngine()
        assert engine.classify_distance(None) == "CLEAR"

    def test_classify_clear_out_of_range(self):
        engine = WarningEngine()
        assert engine.classify_distance(500.0) == "CLEAR"

    def test_warning_generated_first_time(self):
        engine = WarningEngine()
        result = engine.process_sensor("S1", "front_left", 30.0)
        assert result is not None
        assert result["warning_level"] == "CRITICAL"
        assert "S1" in result["warning_message"]

    def test_no_warning_for_safe(self):
        engine = WarningEngine()
        result = engine.process_sensor("S1", "front_left", 300.0)
        assert result is None

    def test_deduplication_same_level(self):
        engine = WarningEngine()
        engine.process_sensor("S1", "front_left", 30.0)  # First warning
        result = engine.process_sensor("S1", "front_left", 35.0)  # Same level, within cooldown
        assert result is None

    def test_new_warning_on_level_change(self):
        engine = WarningEngine()
        engine.process_sensor("S1", "front_left", 80.0)  # WARNING
        result = engine.process_sensor("S1", "front_left", 30.0)  # CRITICAL — level changed
        assert result is not None
        assert result["warning_level"] == "CRITICAL"

    def test_warning_message_content(self):
        engine = WarningEngine()
        result = engine.process_sensor("S2", "front_center_left", 45.0)
        assert result is not None
        assert "45" in result["warning_message"]
        assert "Front Center Left" in result["warning_message"]

    def test_reset_clears_state(self):
        engine = WarningEngine()
        engine.process_sensor("S1", "front_left", 30.0)
        engine.reset()
        result = engine.process_sensor("S1", "front_left", 30.0)
        assert result is not None  # Should generate warning again after reset


# ─── Simulation Engine Tests ──────────────────────────────────────────────────
class TestSimulationScenarios:
    def test_normal_scenario_produces_safe_readings(self):
        scenario = NormalScenario("normal")
        for _ in range(5):
            data = scenario.get_readings()
            for dist in data["distances"].values():
                assert dist > 100, "Normal scenario should mostly be safe"

    def test_critical_scenario_produces_close_readings(self):
        scenario = CriticalFrontObstacleScenario("critical_front")
        # Run enough ticks for it to progress
        for _ in range(100):
            data = scenario.get_readings()
        # After 100 ticks, distances should be close
        data = scenario.get_readings()
        front_dists = [data["distances"]["S1"], data["distances"]["S2"],
                       data["distances"]["S3"], data["distances"]["S4"]]
        assert any(d < 100 for d in front_dists)

    def test_traffic_state_cycles(self):
        scenario = NormalScenario("normal")
        states = set()
        for _ in range(100):
            data = scenario.get_readings()
            states.add(data["traffic_state"])
        assert len(states) > 1  # Should have seen multiple states

    @pytest.mark.asyncio
    async def test_simulation_engine_start_stop(self):
        sim = SimulationEngine()
        results = []

        async def callback(payload):
            results.append(payload)

        sim.set_data_callback(callback)
        await sim.start(scenario="normal", speed=10.0)
        await asyncio.sleep(0.3)
        await sim.stop()
        assert len(results) > 0
        assert sim.is_running is False

    @pytest.mark.asyncio
    async def test_simulation_generates_valid_payload(self):
        sim = SimulationEngine()
        results = []

        async def callback(payload):
            results.append(payload)

        sim.set_data_callback(callback)
        await sim.start(scenario="multiple_obstacles", speed=10.0)
        await asyncio.sleep(0.5)
        await sim.stop()

        assert len(results) > 0
        payload = results[0]
        assert len(payload.sensors) == 6
        for sensor in payload.sensors:
            assert sensor.sensor_id in ["S1", "S2", "S3", "S4", "S5", "S6"]
            assert sensor.zone is not None
        assert payload.traffic_signal is not None
        assert payload.traffic_signal.state.value in ["RED", "GREEN", "YELLOW"]


# ─── API Endpoint Tests ───────────────────────────────────────────────────────
class TestAPIEndpoints:
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_root(self, client):
        response = await client.get("/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_simulation_scenarios_list(self, client):
        response = await client.get("/api/v1/simulation/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert len(data["scenarios"]) == 7

    @pytest.mark.asyncio
    async def test_get_warnings_empty(self, client):
        response = await client.get("/api/v1/warnings")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_obstacles_empty(self, client):
        response = await client.get("/api/v1/obstacles")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_analytics_summary(self, client):
        response = await client.get("/api/v1/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_obstacle_detections" in data
        assert "total_warning_events" in data

    @pytest.mark.asyncio
    async def test_traffic_status(self, client):
        response = await client.get("/api/v1/traffic/status")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_device_status(self, client):
        response = await client.get("/api/v1/devices/status")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_post_telemetry(self, client):
        payload = {
            "device_id": "test-device",
            "timestamp": "2026-11-14T10:00:00Z",
            "sensors": [
                {"sensor_id": "S1", "zone": "front_left", "distance_cm": 45.0, "obstacle_detected": True},
                {"sensor_id": "S2", "zone": "front_center_left", "distance_cm": 120.0, "obstacle_detected": True},
                {"sensor_id": "S3", "zone": "front_center_right", "distance_cm": 200.0, "obstacle_detected": False},
                {"sensor_id": "S4", "zone": "front_right", "distance_cm": 250.0, "obstacle_detected": False},
                {"sensor_id": "S5", "zone": "left_side", "distance_cm": 80.0, "obstacle_detected": True},
                {"sensor_id": "S6", "zone": "right_side", "distance_cm": 180.0, "obstacle_detected": False},
            ],
            "traffic_signal": {"state": "GREEN", "duration_seconds": 30}
        }
        response = await client.post("/api/v1/iot/telemetry", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["processed_sensors"] == 6

    @pytest.mark.asyncio
    async def test_telemetry_invalid_sensor_id(self, client):
        payload = {
            "device_id": "test-device",
            "sensors": [
                {"sensor_id": "S9", "zone": "unknown", "distance_cm": 100.0, "obstacle_detected": False},
            ],
        }
        response = await client.post("/api/v1/iot/telemetry", json=payload)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_warning(self, client):
        response = await client.post("/api/v1/warnings/acknowledge", json={"warning_id": 99999})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_thresholds(self, client):
        response = await client.get("/api/v1/settings/thresholds")
        assert response.status_code == 200
        data = response.json()
        assert "critical_cm" in data

    @pytest.mark.asyncio
    async def test_update_thresholds(self, client):
        response = await client.post("/api/v1/settings/thresholds", json={
            "critical_cm": 40.0,
            "warning_cm": 90.0,
            "caution_cm": 140.0,
            "max_range_cm": 350.0,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["thresholds"]["critical_cm"] == 40.0

    @pytest.mark.asyncio
    async def test_update_thresholds_invalid_hierarchy(self, client):
        response = await client.post("/api/v1/settings/thresholds", json={
            "critical_cm": 100.0,
            "warning_cm": 50.0,  # invalid: warning < critical
            "caution_cm": 150.0,
            "max_range_cm": 400.0,
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_data_cleanup_endpoint(self, client):
        response = await client.post("/api/v1/settings/cleanup?retention_days=15")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleanup_completed"
        assert data["retention_days"] == 15
        assert isinstance(data["deleted_readings"], int)
