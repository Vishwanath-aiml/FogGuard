// Traffic signal visual component
import { useEffect, useState } from 'react';
import type { TrafficSignalStatus } from '../../types';

interface TrafficSignalProps {
  signal: TrafficSignalStatus | null;
  size?: 'sm' | 'md' | 'lg';
}

export function TrafficSignal({ signal, size = 'md' }: TrafficSignalProps) {
  const [countdown, setCountdown] = useState<number | null>(null);
  const state = signal?.state ?? 'UNKNOWN';

  useEffect(() => {
    if (signal?.duration_seconds) {
      setCountdown(signal.duration_seconds);
      const timer = setInterval(() => {
        setCountdown(prev => {
          if (prev === null || prev <= 1) {
            clearInterval(timer);
            return null;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [signal?.state]);

  const sizes = {
    sm: { housing: 'w-12', light: 'w-7 h-7', text: 'text-xs' },
    md: { housing: 'w-20', light: 'w-12 h-12', text: 'text-sm' },
    lg: { housing: 'w-28', light: 'w-16 h-16', text: 'text-base' },
  };
  const s = sizes[size];

  const lights = [
    { color: 'RED', active: state === 'RED', bg: '#ef4444', inactive: '#3f1515' },
    { color: 'YELLOW', active: state === 'YELLOW', bg: '#eab308', inactive: '#3d3010' },
    { color: 'GREEN', active: state === 'GREEN', bg: '#22c55e', inactive: '#103b1a' },
  ];

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Housing */}
      <div
        className={`${s.housing} rounded-xl p-2 flex flex-col items-center gap-2`}
        style={{
          background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 100%)',
          border: '2px solid #334155',
          boxShadow: '0 4px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)',
        }}
      >
        {lights.map(({ color, active, bg, inactive }) => (
          <div
            key={color}
            className={`${s.light} rounded-full transition-all duration-500`}
            style={{
              backgroundColor: active ? bg : inactive,
              boxShadow: active
                ? `0 0 20px 6px ${bg}80, 0 0 40px 12px ${bg}30`
                : 'none',
              transform: active ? 'scale(1.05)' : 'scale(1)',
            }}
          />
        ))}
      </div>

      {/* State label */}
      <div className="text-center">
        <div
          className={`font-bold tracking-widest ${s.text}`}
          style={{
            color: state === 'RED' ? '#ef4444'
              : state === 'YELLOW' ? '#eab308'
              : state === 'GREEN' ? '#22c55e'
              : '#94a3b8'
          }}
        >
          {state}
        </div>
        {countdown !== null && (
          <div className="text-xs text-slate-400 font-mono mt-1">
            {countdown}s remaining
          </div>
        )}
      </div>
    </div>
  );
}
