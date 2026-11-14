// Reusable UI components
import React from 'react';
import { cn } from '../../utils';

// ── Card ──────────────────────────────────────────────────────────────────────
interface CardProps {
  children: React.ReactNode;
  className?: string;
  title?: string;
  titleIcon?: React.ReactNode;
  headerRight?: React.ReactNode;
}
export function Card({ children, className, title, titleIcon, headerRight }: CardProps) {
  return (
    <div
      className={cn('rounded-xl border overflow-hidden', className)}
      style={{ background: 'rgba(6, 15, 46, 0.7)', borderColor: 'rgba(13, 32, 112, 0.5)' }}
    >
      {title && (
        <div className="flex items-center justify-between px-4 py-3 border-b"
          style={{ borderColor: 'rgba(13, 32, 112, 0.5)' }}>
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            {titleIcon}
            {title}
          </div>
          {headerRight}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────
interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'critical' | 'warning' | 'caution' | 'safe' | 'info';
  className?: string;
}
const BADGE_STYLES: Record<string, string> = {
  default: 'bg-slate-500/20 border-slate-500/30 text-slate-300',
  critical: 'bg-red-500/20 border-red-500/30 text-red-400',
  warning: 'bg-orange-500/20 border-orange-500/30 text-orange-400',
  caution: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-400',
  safe: 'bg-green-500/20 border-green-500/30 text-green-400',
  info: 'bg-cyan-500/20 border-cyan-500/30 text-cyan-400',
};
export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span className={cn('px-2 py-0.5 text-xs font-medium border rounded-full', BADGE_STYLES[variant], className)}>
      {children}
    </span>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────────────
interface StatCardProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  color?: string;
  sub?: string;
}
export function StatCard({ label, value, icon, color = '#22d3ee', sub }: StatCardProps) {
  return (
    <div
      className="rounded-xl p-4 flex flex-col gap-2 border"
      style={{ background: 'rgba(6, 15, 46, 0.7)', borderColor: 'rgba(13, 32, 112, 0.5)' }}
    >
      <div className="flex items-center gap-2">
        {icon && <span style={{ color }}>{icon}</span>}
        <span className="text-xs text-slate-400 uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-bold font-mono" style={{ color }}>
        {value}
      </div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

// ── Status Dot ────────────────────────────────────────────────────────────────
interface StatusDotProps {
  status: string;
  label?: string;
}
const STATUS_COLORS: Record<string, string> = {
  CONNECTED: '#22c55e',
  SIMULATED: '#22d3ee',
  DISCONNECTED: '#ef4444',
  UNKNOWN: '#94a3b8',
  ERROR: '#ef4444',
};
export function StatusDot({ status, label }: StatusDotProps) {
  const color = STATUS_COLORS[status] ?? '#94a3b8';
  return (
    <div className="flex items-center gap-2">
      <span
        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
        style={{
          backgroundColor: color,
          boxShadow: `0 0 6px ${color}80`,
          animation: status === 'CONNECTED' || status === 'SIMULATED' ? 'pulse 2s infinite' : undefined,
        }}
      />
      {label && <span className="text-sm" style={{ color }}>{label || status}</span>}
    </div>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md';
}
const BTN_STYLES: Record<string, string> = {
  primary: 'bg-cyan-500 hover:bg-cyan-400 text-white border-transparent',
  secondary: 'bg-blue-600 hover:bg-blue-500 text-white border-transparent',
  danger: 'bg-red-600 hover:bg-red-500 text-white border-transparent',
  ghost: 'bg-transparent hover:bg-white/5 text-slate-300 border-slate-700',
};
export function Button({ children, variant = 'primary', size = 'md', className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'flex items-center gap-2 font-medium rounded-lg border transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed',
        BTN_STYLES[variant],
        size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

// ── Loading Spinner ───────────────────────────────────────────────────────────
export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <div
      className="border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin"
      style={{ width: size, height: size }}
    />
  );
}

// ── Sensor Row ────────────────────────────────────────────────────────────────
import type { SensorReading } from '../../types';
import { ZONE_DISPLAY } from '../../types';
import { formatDistance, warningLevelBg } from '../../utils';

export function SensorRow({ sensor }: { sensor: SensorReading }) {
  const zoneName = ZONE_DISPLAY[sensor.zone as keyof typeof ZONE_DISPLAY] ?? sensor.zone;
  const style = warningLevelBg(sensor.warning_level);

  return (
    <div className={cn('flex items-center justify-between p-2.5 rounded-lg border', style)}>
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold w-6">{sensor.sensor_id}</span>
        <span className="text-xs text-slate-400">{zoneName}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm">{formatDistance(sensor.distance_cm)}</span>
        <span className="text-xs font-semibold w-16 text-right">{sensor.warning_level}</span>
      </div>
    </div>
  );
}

// ── Warning Card ──────────────────────────────────────────────────────────────
import type { WarningEvent } from '../../types';
import { formatTimeAgo } from '../../utils';
import { Check } from 'lucide-react';

interface WarningCardProps {
  warning: WarningEvent;
  onAck?: (id: number) => void;
}
export function WarningCard({ warning, onAck }: WarningCardProps) {
  const style = warningLevelBg(warning.warning_level as any);
  return (
    <div className={cn('flex items-start gap-3 p-3 rounded-lg border', style,
      warning.acknowledged ? 'opacity-50' : '')}>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium leading-snug">{warning.warning_message}</p>
        <p className="text-xs text-slate-500 mt-1">{formatTimeAgo(warning.timestamp)}</p>
      </div>
      {!warning.acknowledged && onAck && (
        <button
          onClick={() => onAck(warning.id)}
          className="p-1 rounded hover:bg-white/10 transition-colors flex-shrink-0"
          title="Acknowledge"
        >
          <Check className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
