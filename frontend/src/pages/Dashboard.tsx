// Main Dashboard Page
import { Activity, AlertTriangle, Maximize2, Radio, Shield } from 'lucide-react';
import { useStore } from '../store/useStore';
import { ObstacleVisualization } from '../components/visualization/ObstacleVisualization';
import { TrafficSignal } from '../components/visualization/TrafficSignal';
import { Card, StatCard, SensorRow, WarningCard, Button } from '../components/ui';
import { SimulationControl } from './Dashboard/SimulationControl';
import * as api from '../services/api';

export function Dashboard() {
  const { sensors, trafficSignal, activeWarnings, unacknowledgedCount, acknowledgeWarning, acknowledgeAll } = useStore();

  const obstacleCount = sensors.filter(s => s.obstacle_detected).length;
  const nearestDistance = sensors
    .filter(s => s.obstacle_detected && s.distance_cm !== null)
    .sort((a, b) => (a.distance_cm ?? 999) - (b.distance_cm ?? 999))[0];

  const dangerZone = sensors
    .filter(s => s.obstacle_detected)
    .sort((a, b) => {
      const order: Record<string, number> = { CRITICAL: 0, WARNING: 1, CAUTION: 2 };
      return (order[a.warning_level] ?? 3) - (order[b.warning_level] ?? 3);
    })[0];

  const handleAck = async (id: number) => {
    acknowledgeWarning(id);
    try { await api.acknowledgeWarning(id); } catch { /* silent */ }
  };
  const handleAckAll = async () => {
    acknowledgeAll();
    try { await api.acknowledgeAllWarnings(); } catch { /* silent */ }
  };

  const unackWarnings = activeWarnings.filter(w => !w.acknowledged).slice(0, 5);

  return (
    <div className="h-full flex flex-col gap-4 p-4 overflow-hidden">
      {/* Row 1: Stats */}
      <div className="grid grid-cols-4 gap-3 flex-shrink-0">
        <StatCard
          label="Active Obstacles"
          value={obstacleCount}
          icon={<Radio className="w-4 h-4" />}
          color={obstacleCount > 0 ? '#f97316' : '#22c55e'}
        />
        <StatCard
          label="Nearest Obstacle"
          value={nearestDistance ? `${Math.round(nearestDistance.distance_cm!)} cm` : 'CLEAR'}
          icon={<Maximize2 className="w-4 h-4" />}
          color={nearestDistance ? '#ef4444' : '#22c55e'}
          sub={nearestDistance ? `${nearestDistance.sensor_id} · ${nearestDistance.warning_level}` : 'All zones clear'}
        />
        <StatCard
          label="Active Warnings"
          value={unacknowledgedCount}
          icon={<AlertTriangle className="w-4 h-4" />}
          color={unacknowledgedCount > 0 ? '#ef4444' : '#22c55e'}
        />
        <StatCard
          label="Danger Zone"
          value={dangerZone ? dangerZone.sensor_id : 'NONE'}
          icon={<Shield className="w-4 h-4" />}
          color={dangerZone ? '#f97316' : '#22c55e'}
          sub={dangerZone ? dangerZone.zone.replace(/_/g, ' ').toUpperCase() : 'All safe'}
        />
      </div>

      {/* Row 2: Main visualization + side panels */}
      <div className="flex-1 grid grid-cols-12 gap-3 min-h-0">
        {/* 3D Visualization - takes most space */}
        <div
          className="col-span-7 rounded-xl border overflow-hidden relative"
          style={{ background: 'rgba(2, 8, 24, 0.9)', borderColor: 'rgba(13, 32, 112, 0.5)' }}
        >
          <div className="absolute top-3 left-3 z-10 flex items-center gap-2 text-xs text-cyan-400 font-semibold">
            <Activity className="w-3.5 h-3.5" />
            LIVE 3D OBSTACLE VIEW
          </div>
          <ObstacleVisualization sensors={sensors} />
        </div>

        {/* Right column: sensors + traffic + warnings */}
        <div className="col-span-5 flex flex-col gap-3 overflow-hidden">
          {/* Sensor panel */}
          <Card
            title="Sensor Status"
            titleIcon={<Radio className="w-3.5 h-3.5 text-cyan-400" />}
            className="flex-shrink-0"
          >
            <div className="space-y-1.5">
              {sensors.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-2">No sensor data</p>
              ) : (
                sensors.map(s => <SensorRow key={s.sensor_id} sensor={s} />)
              )}
            </div>
          </Card>

          {/* Traffic signal */}
          <Card
            title="Traffic Signal"
            titleIcon={<Activity className="w-3.5 h-3.5 text-cyan-400" />}
            className="flex-shrink-0"
          >
            <div className="flex items-center gap-6">
              <TrafficSignal signal={trafficSignal} size="sm" />
              <div className="flex-1">
                <div className="text-sm text-slate-400">Current State</div>
                <div className="text-xl font-bold font-mono"
                  style={{
                    color: trafficSignal?.state === 'RED' ? '#ef4444'
                      : trafficSignal?.state === 'GREEN' ? '#22c55e'
                      : trafficSignal?.state === 'YELLOW' ? '#eab308'
                      : '#94a3b8'
                  }}>
                  {trafficSignal?.state ?? 'UNKNOWN'}
                </div>
                {trafficSignal?.duration_seconds && (
                  <div className="text-xs text-slate-500">
                    Duration: {trafficSignal.duration_seconds}s
                  </div>
                )}
              </div>
            </div>
          </Card>

          {/* Active warnings */}
          <Card
            title={`Warnings (${unacknowledgedCount} unread)`}
            titleIcon={<AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
            headerRight={
              unacknowledgedCount > 0 ? (
                <Button variant="ghost" size="sm" onClick={handleAckAll}>
                  Ack All
                </Button>
              ) : undefined
            }
            className="flex-1 min-h-0"
          >
            <div className="space-y-1.5 overflow-y-auto max-h-40">
              {unackWarnings.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-2">No active warnings</p>
              ) : (
                unackWarnings.map(w => (
                  <WarningCard key={w.id} warning={w} onAck={handleAck} />
                ))
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Row 3: Simulation control */}
      <div className="flex-shrink-0">
        <SimulationControl />
      </div>
    </div>
  );
}
