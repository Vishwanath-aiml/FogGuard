// Global state store using Zustand
import { create } from 'zustand';
import type { SensorReading, TrafficSignalStatus, WarningEvent, ThresholdConfig } from '../types';

export interface SystemState {
  // Connection
  wsConnected: boolean;
  backendConnected: boolean;
  simulationMode: boolean;
  simulationRunning: boolean;
  simulationScenario: string;
  dataSource: 'simulation' | 'hardware' | 'none';

  // Live data
  sensors: SensorReading[];
  trafficSignal: TrafficSignalStatus | null;
  lastUpdate: string | null;

  // Warnings
  activeWarnings: WarningEvent[];
  warningHistory: WarningEvent[];
  unacknowledgedCount: number;
  muted: boolean;

  // Settings
  thresholds: ThresholdConfig;

  // Actions
  setWsConnected: (v: boolean) => void;
  setBackendConnected: (v: boolean) => void;
  setSimulationRunning: (v: boolean) => void;
  setSimulationScenario: (v: string) => void;
  updateFromTelemetry: (msg: any) => void;
  acknowledgeWarning: (id: number) => void;
  acknowledgeAll: () => void;
  setMuted: (v: boolean) => void;
  setThresholds: (t: ThresholdConfig) => void;
  addWarnings: (warnings: WarningEvent[]) => void;
}

export const useStore = create<SystemState>((set, get) => ({
  wsConnected: false,
  backendConnected: false,
  simulationMode: true,
  simulationRunning: false,
  simulationScenario: 'normal',
  dataSource: 'none',

  sensors: [],
  trafficSignal: null,
  lastUpdate: null,

  activeWarnings: [],
  warningHistory: [],
  unacknowledgedCount: 0,
  muted: false,

  thresholds: {
    critical_cm: 50,
    warning_cm: 100,
    caution_cm: 150,
    max_range_cm: 400,
  },

  setWsConnected: (v) => set({ wsConnected: v }),
  setBackendConnected: (v) => set({ backendConnected: v }),
  setSimulationRunning: (v) => set({ simulationRunning: v }),
  setSimulationScenario: (v) => set({ simulationScenario: v }),

  updateFromTelemetry: (msg) => {
    if (msg.type !== 'telemetry') return;

    const newWarnings: WarningEvent[] = msg.new_warnings || [];
    const existing = get().activeWarnings;

    // Add new warnings to front, deduplicate by id
    const allWarnings = [
      ...newWarnings,
      ...existing.filter((w) => !newWarnings.find((n) => n.id === w.id)),
    ].slice(0, 100); // Keep last 100

    const unackCount = allWarnings.filter((w) => !w.acknowledged).length;

    set({
      sensors: msg.sensors || [],
      trafficSignal: msg.traffic_signal,
      lastUpdate: msg.timestamp,
      simulationMode: msg.simulation_mode,
      dataSource: msg.source,
      activeWarnings: allWarnings,
      unacknowledgedCount: unackCount,
    });
  },

  acknowledgeWarning: (id) => {
    set((state) => {
      const updated = state.activeWarnings.map((w) =>
        w.id === id ? { ...w, acknowledged: true } : w
      );
      return {
        activeWarnings: updated,
        unacknowledgedCount: updated.filter((w) => !w.acknowledged).length,
      };
    });
  },

  acknowledgeAll: () => {
    set((state) => ({
      activeWarnings: state.activeWarnings.map((w) => ({ ...w, acknowledged: true })),
      unacknowledgedCount: 0,
    }));
  },

  setMuted: (v) => set({ muted: v }),
  setThresholds: (t) => set({ thresholds: t }),

  addWarnings: (warnings) => {
    set((state) => {
      const existing = state.activeWarnings;
      const merged = [
        ...warnings,
        ...existing.filter((w) => !warnings.find((n) => n.id === w.id)),
      ].slice(0, 100);
      return {
        activeWarnings: merged,
        unacknowledgedCount: merged.filter((w) => !w.acknowledged).length,
      };
    });
  },
}));
