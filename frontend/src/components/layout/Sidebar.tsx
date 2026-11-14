// Sidebar navigation
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Radar, TrafficCone, BarChart3,
  History, Cpu, Settings, Wifi, WifiOff, Activity
} from 'lucide-react';
import { useStore } from '../../store/useStore';
import { cn } from '../../utils';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/obstacles', icon: Radar, label: 'Obstacle Detection' },
  { to: '/traffic', icon: TrafficCone, label: 'Traffic Management' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/history', icon: History, label: 'History' },
  { to: '/devices', icon: Cpu, label: 'Device Status' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar() {
  const { wsConnected, simulationRunning, unacknowledgedCount } = useStore();

  return (
    <aside className="w-64 h-screen flex-shrink-0 flex flex-col"
      style={{ background: 'rgba(6, 15, 46, 0.95)', borderRight: '1px solid rgba(13, 32, 112, 0.5)' }}>
      {/* Logo */}
      <div className="p-5 border-b" style={{ borderColor: 'rgba(13, 32, 112, 0.5)' }}>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #22d3ee, #3b82f6)' }}>
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-wide">FogGuard</h1>
            <p className="text-xs" style={{ color: '#94a3b8' }}>IoT Dashboard</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 overflow-y-auto">
        <div className="space-y-1">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'text-cyan-400 bg-cyan-400/10 border border-cyan-400/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                )
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{label}</span>
              {label === 'History' && unacknowledgedCount > 0 && (
                <span className="ml-auto px-1.5 py-0.5 text-xs bg-red-500 text-white rounded-full">
                  {unacknowledgedCount}
                </span>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Status footer */}
      <div className="p-4 border-t" style={{ borderColor: 'rgba(13, 32, 112, 0.5)' }}>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs">
            {wsConnected ? (
              <Wifi className="w-3.5 h-3.5 text-green-400" />
            ) : (
              <WifiOff className="w-3.5 h-3.5 text-red-400" />
            )}
            <span style={{ color: wsConnected ? '#4ade80' : '#f87171' }}>
              {wsConnected ? 'Live Connected' : 'Disconnected'}
            </span>
          </div>
          {simulationRunning && (
            <div className="flex items-center gap-2 text-xs">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span className="text-cyan-400">Simulation Active</span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
