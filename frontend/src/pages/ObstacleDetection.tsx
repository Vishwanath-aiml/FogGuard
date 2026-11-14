// Obstacle Detection Page — full sensor detail view
import { Radio, AlertTriangle, Shield, Maximize2 } from 'lucide-react';
import { useStore } from '../store/useStore';
import { ObstacleVisualization } from '../components/visualization/ObstacleVisualization';
import { Card, StatCard, SensorRow, WarningCard, Button } from '../components/ui';
import { ZONE_DISPLAY } from '../types';
import { formatDistance, warningLevelColor } from '../utils';
import * as api from '../services/api';

export function ObstacleDetection() {
  const { sensors, activeWarnings, unacknowledgedCount, acknowledgeWarning, acknowledgeAll } = useStore();

  const obstacleCount = sensors.filter(s => s.obstacle_detected).length;
  const nearestSensor = sensors
    .filter(s => s.obstacle_detected && s.distance_cm !== null)
    .sort((a, b) => (a.distance_cm ?? 999) - (b.distance_cm ?? 999))[0];

  const criticalCount = sensors.filter(s => s.warning_level === 'CRITICAL').length;

  const handleAck = async (id: number) => {
    acknowledgeWarning(id);
    try { await api.acknowledgeWarning(id); } catch { /* silent */ }
  };

  return (
    <div className="h-full flex flex-col gap-4 p-4 overflow-hidden">
      <div className="flex items-center gap-3 flex-shrink-0">
        <Radio className="w-5 h-5 text-cyan-400" />
        <h2 className="text-lg font-bold text-white">Obstacle Detection</h2>
        <span className="text-sm text-slate-400">— Real-time 6-sensor monitoring</span>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3 flex-shrink-0">
        <StatCard label="Detected Obstacles" value={obstacleCount}
          icon={<Radio className="w-4 h-4" />} color={obstacleCount > 0 ? '#f97316' : '#22c55e'} />
        <StatCard label="Nearest" value={nearestSensor ? formatDistance(nearestSensor.distance_cm) : 'CLEAR'}
          icon={<Maximize2 className="w-4 h-4" />} color={nearestSensor ? warningLevelColor(nearestSensor.warning_level) : '#22c55e'}
          sub={nearestSensor?.sensor_id} />
        <StatCard label="Critical Zones" value={criticalCount}
          icon={<AlertTriangle className="w-4 h-4" />} color={criticalCount > 0 ? '#ef4444' : '#22c55e'} />
        <StatCard label="Unread Warnings" value={unacknowledgedCount}
          icon={<Shield className="w-4 h-4" />} color={unacknowledgedCount > 0 ? '#ef4444' : '#22c55e'} />
      </div>

      {/* Main content */}
      <div className="flex-1 grid grid-cols-5 gap-3 min-h-0">
        {/* 3D visualization */}
        <div
          className="col-span-3 rounded-xl border overflow-hidden"
          style={{ background: 'rgba(2, 8, 24, 0.9)', borderColor: 'rgba(13, 32, 112, 0.5)' }}
        >
          <ObstacleVisualization sensors={sensors} />
        </div>

        {/* Right panel */}
        <div className="col-span-2 flex flex-col gap-3 overflow-hidden">
          {/* Individual sensor detail */}
          <Card
            title="Sensor Readings"
            titleIcon={<Radio className="w-3.5 h-3.5 text-cyan-400" />}
          >
            <div className="space-y-1.5">
              {sensors.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-4">Waiting for sensor data...</p>
              ) : (
                sensors.map(s => <SensorRow key={s.sensor_id} sensor={s} />)
              )}
            </div>
          </Card>

          {/* Zone map */}
          <Card title="Zone Map" titleIcon={<Shield className="w-3.5 h-3.5 text-cyan-400" />}>
            <div className="grid grid-cols-2 gap-1.5">
              {sensors.map(s => {
                const zoneName = ZONE_DISPLAY[s.zone as keyof typeof ZONE_DISPLAY] || s.zone;
                const color = warningLevelColor(s.warning_level);
                return (
                  <div
                    key={s.sensor_id}
                    className="rounded-lg p-2 border text-center"
                    style={{ borderColor: `${color}40`, background: `${color}10` }}
                  >
                    <div className="text-xs font-mono font-bold" style={{ color }}>{s.sensor_id}</div>
                    <div className="text-xs text-slate-400 leading-tight">{zoneName}</div>
                    <div className="text-sm font-mono font-semibold" style={{ color }}>
                      {s.distance_cm !== null ? `${Math.round(s.distance_cm)}cm` : '—'}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Warnings */}
          <Card
            title={`Active Warnings (${unacknowledgedCount})`}
            titleIcon={<AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
            headerRight={
              unacknowledgedCount > 0 ? (
                <Button variant="ghost" size="sm" onClick={() => { acknowledgeAll(); api.acknowledgeAllWarnings().catch(() => {}); }}>
                  Ack All
                </Button>
              ) : undefined
            }
            className="flex-1"
          >
            <div className="space-y-1.5 overflow-y-auto max-h-48">
              {activeWarnings.filter(w => !w.acknowledged).slice(0, 10).map(w => (
                <WarningCard key={w.id} warning={w} onAck={handleAck} />
              ))}
              {unacknowledgedCount === 0 && (
                <p className="text-sm text-slate-500 text-center py-4">No active warnings</p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
