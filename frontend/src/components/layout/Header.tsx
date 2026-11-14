// Top header bar
import { useState, useEffect } from 'react';
import { Bell, BellOff, Wifi, WifiOff, Clock, FlaskConical, Cpu } from 'lucide-react';
import { useStore } from '../../store/useStore';
import { formatTimeAgo } from '../../utils';

export function Header() {
  const { wsConnected, simulationRunning, dataSource, lastUpdate, unacknowledgedCount, muted, setMuted } = useStore();
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="h-14 flex-shrink-0 flex items-center px-6 gap-4"
      style={{
        background: 'rgba(6, 15, 46, 0.95)',
        borderBottom: '1px solid rgba(13, 32, 112, 0.5)',
      }}>

      {/* Mode badge */}
      <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold border ${
        simulationRunning || dataSource === 'simulation'
          ? 'bg-cyan-400/10 border-cyan-400/30 text-cyan-400'
          : dataSource === 'hardware'
          ? 'bg-green-400/10 border-green-400/30 text-green-400'
          : 'bg-slate-500/10 border-slate-500/30 text-slate-400'
      }`}>
        {simulationRunning || dataSource === 'simulation' ? (
          <><FlaskConical className="w-3 h-3" /> SIMULATION</>
        ) : dataSource === 'hardware' ? (
          <><Cpu className="w-3 h-3" /> HARDWARE</>
        ) : (
          <><span className="w-2 h-2 rounded-full bg-slate-400" /> STANDBY</>
        )}
      </div>

      <div className="flex-1" />

      {/* Last update */}
      <div className="flex items-center gap-1.5 text-xs text-slate-400">
        <Clock className="w-3.5 h-3.5" />
        <span>{formatTimeAgo(lastUpdate)}</span>
      </div>

      {/* WS status */}
      <div className={`flex items-center gap-1.5 text-xs ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
        {wsConnected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
        <span>{wsConnected ? 'WS Live' : 'WS Offline'}</span>
      </div>

      {/* Warning bell */}
      <button
        onClick={() => setMuted(!muted)}
        className="relative p-2 rounded-lg hover:bg-white/5 transition-colors"
        title={muted ? 'Unmute alerts' : 'Mute alerts'}
      >
        {muted ? (
          <BellOff className="w-4 h-4 text-slate-400" />
        ) : (
          <Bell className={`w-4 h-4 ${unacknowledgedCount > 0 ? 'text-red-400 animate-pulse' : 'text-slate-400'}`} />
        )}
        {unacknowledgedCount > 0 && !muted && (
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
        )}
      </button>

      {/* Clock */}
      <div className="text-xs font-mono text-slate-300 tabular-nums">
        {time.toLocaleTimeString()}
      </div>
    </header>
  );
}
