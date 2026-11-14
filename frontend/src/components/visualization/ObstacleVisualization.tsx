// 3D Obstacle Visualization using React Three Fiber
// Renders the vehicle, sensor beams, and ADAS 3D bounding cuboids for detected vehicles in fog
import { Component, useRef, useMemo, useState, type ReactNode, type ErrorInfo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Grid } from '@react-three/drei';
import * as THREE from 'three';
import type { SensorReading } from '../../types';
import { warningLevelColor } from '../../utils';

// Sensor zone 3D positions (relative to vehicle center)
// Vehicle is ~4 units long, 2 units wide (front bumper at z = -2.0)
const ZONE_POSITIONS: Record<string, [number, number, number]> = {
  front_left: [-1.0, 0, -2.5],
  front_center: [0, 0, -2.5],
  front_center_left: [-0.35, 0, -2.5],
  front_center_right: [0.35, 0, -2.5],
  front_right: [1.0, 0, -2.5],
  left_side: [-2.2, 0, 0],
  right_side: [2.2, 0, 0],
  roof_center: [0, 1.2, -1.0],
};

const ZONE_DIRECTIONS: Record<string, [number, number, number]> = {
  front_left: [-0.25, 0, -1],
  front_center: [0, 0, -1],
  front_center_left: [-0.08, 0, -1],
  front_center_right: [0.08, 0, -1],
  front_right: [0.25, 0, -1],
  left_side: [-1, 0, 0],
  right_side: [1, 0, 0],
  roof_center: [0, 0.05, -1],
};

const MAX_RANGE = 400;
const SCALE = 0.025; // cm to Three.js units (400cm = 10 units in 3D world)

// ─── React Error Boundary for 3D WebGL Canvas ───────────────────────────────
interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class CanvasErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Canvas 3D Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center bg-slate-950/90 text-slate-300">
          <div className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center mb-3">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h3 className="font-semibold text-white mb-1">3D HUD Temporarily Unavailable</h3>
          <p className="text-xs text-slate-400 max-w-sm mb-4">
            {this.state.error?.message || 'WebGL context or rendering error encountered.'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-medium transition-colors"
          >
            Reload 3D HUD
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function Vehicle() {
  return (
    <group>
      {/* Car body */}
      <mesh position={[0, 0.35, 0]} castShadow>
        <boxGeometry args={[1.8, 0.5, 3.8]} />
        <meshStandardMaterial color="#1e40af" metalness={0.7} roughness={0.3} />
      </mesh>
      {/* Cabin / Roof */}
      <mesh position={[0, 0.85, -0.2]} castShadow>
        <boxGeometry args={[1.4, 0.5, 2.0]} />
        <meshStandardMaterial color="#1d4ed8" metalness={0.6} roughness={0.4} />
      </mesh>
      {/* Windshield glass */}
      <mesh position={[0, 0.85, -1.21]} rotation={[-Math.PI / 6, 0, 0]}>
        <planeGeometry args={[1.3, 0.55]} />
        <meshStandardMaterial color="#38bdf8" transparent opacity={0.6} roughness={0.1} />
      </mesh>
      {/* Wheels */}
      {[[-0.95, 0.15, -1.2], [0.95, 0.15, -1.2], [-0.95, 0.15, 1.2], [0.95, 0.15, 1.2]].map(([x, y, z], i) => (
        <mesh key={i} position={[x, y, z] as [number, number, number]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.32, 0.32, 0.25, 20]} />
          <meshStandardMaterial color="#0f172a" metalness={0.4} roughness={0.8} />
        </mesh>
      ))}
      {/* Headlights (glow in fog) */}
      {[[-0.65, 0.35, -1.91], [0.65, 0.35, -1.91]].map(([x, y, z], i) => (
        <mesh key={i} position={[x, y, z] as [number, number, number]}>
          <boxGeometry args={[0.3, 0.12, 0.05]} />
          <meshStandardMaterial color="#fef08a" emissive="#fef08a" emissiveIntensity={1.2} />
        </mesh>
      ))}
      {/* Front LIDAR / Ultrasonic Sensor Mount Bar */}
      <mesh position={[0, 0.18, -1.92]}>
        <boxGeometry args={[1.8, 0.08, 0.05]} />
        <meshStandardMaterial color="#06b6d4" emissive="#06b6d4" emissiveIntensity={0.6} />
      </mesh>
      {/* Roof Ultrasonic Sensor Mount */}
      <mesh position={[0, 1.15, -0.9]}>
        <boxGeometry args={[0.25, 0.12, 0.25]} />
        <meshStandardMaterial color="#06b6d4" emissive="#06b6d4" emissiveIntensity={0.8} />
      </mesh>
    </group>
  );
}

function SensorBeam({ zone, sensor }: { zone: string; sensor: SensorReading }) {
  const meshRef = useRef<THREE.Mesh>(null);

  const startPos = ZONE_POSITIONS[zone] as [number, number, number];
  const dir = ZONE_DIRECTIONS[zone] as [number, number, number];

  const dist = sensor.distance_cm ?? MAX_RANGE;
  const beamLength = Math.min(dist, MAX_RANGE) * SCALE;
  const color = warningLevelColor(sensor.warning_level);

  const midPoint: [number, number, number] = [
    startPos[0] + (dir[0] * beamLength) / 2,
    startPos[1],
    startPos[2] + (dir[2] * beamLength) / 2,
  ];

  useFrame(({ clock }) => {
    if (meshRef.current && meshRef.current.material) {
      const alpha = sensor.obstacle_detected
        ? 0.35 + 0.25 * Math.sin(clock.getElapsedTime() * 4)
        : 0.08;
      (meshRef.current.material as THREE.MeshStandardMaterial).opacity = alpha;
    }
  });

  const isSideBeam = Math.abs(dir[2]) < 0.1;
  const rotation: [number, number, number] = isSideBeam ? [0, 0, Math.PI / 2] : [Math.PI / 2, 0, 0];
  const scale: [number, number, number] = isSideBeam
    ? [beamLength, 0.04, 0.04]
    : [0.04, beamLength, 0.04];

  return (
    <mesh ref={meshRef} position={midPoint} rotation={rotation} scale={scale}>
      <cylinderGeometry args={[0.3, 0.3, 1, 6]} />
      <meshStandardMaterial color={color} transparent opacity={0.15} />
    </mesh>
  );
}

// ─── 3D Vehicle Bounding Cuboid Revealed in Fog ──────────────────────────────
function ObstacleCuboid({ zone, sensor }: { zone: string; sensor: SensorReading }) {
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);

  // Hook 1: Check obstacle condition (UNCONDITIONAL)
  const hasObstacle =
    sensor.distance_cm !== null &&
    sensor.distance_cm > 0 &&
    sensor.distance_cm <= MAX_RANGE;

  const startPos = ZONE_POSITIONS[zone] ?? [0, 0, -2.5];
  const dir = ZONE_DIRECTIONS[zone] ?? [0, 0, -1];
  const safeDistance = Math.min(sensor.distance_cm ?? MAX_RANGE, MAX_RANGE);
  const dist = safeDistance * SCALE;

  // Obstacle Dimensions (Vehicle size)
  const isRoofSensor = zone === 'roof_center';
  const size: [number, number, number] = isRoofSensor
    ? [1.8, 1.2, 2.4]  // Overhead / tall truck / bridge obstacle
    : [1.6, 1.1, 2.4]; // Standard vehicle cuboid ahead

  const centerY = isRoofSensor ? 1.4 : size[1] / 2;

  const obstaclePos: [number, number, number] = [
    startPos[0] + dir[0] * dist,
    centerY,
    startPos[2] + dir[2] * dist,
  ];

  const color = warningLevelColor(sensor.warning_level);
  const isCritical = sensor.warning_level === 'CRITICAL';
  const isWarning = sensor.warning_level === 'WARNING';

  // Hook 2: Memoize geometries to eliminate memory churn / buffer re-creations
  const edgesGeom = useMemo(() => {
    const box = new THREE.BoxGeometry(...size);
    const edges = new THREE.EdgesGeometry(box);
    box.dispose();
    return edges;
  }, [isRoofSensor]);

  // Hook 3: Frame loop (UNCONDITIONAL - never violated by early returns)
  useFrame(({ clock }) => {
    if (!hasObstacle) return;

    if (meshRef.current && meshRef.current.material) {
      const t = clock.getElapsedTime();
      const pulseSpeed = isCritical ? 8 : isWarning ? 5 : 2;
      const pulse = 0.5 + 0.5 * Math.sin(t * pulseSpeed);

      (meshRef.current.material as THREE.MeshStandardMaterial).emissiveIntensity =
        isCritical ? 0.6 + 0.4 * pulse : 0.3 + 0.2 * pulse;

      // Subtle hover/suspension motion
      if (groupRef.current) {
        groupRef.current.position.y = obstaclePos[1] + 0.02 * Math.sin(t * 3);
      }
    }
  });

  // Early return is now STRICTLY AFTER all React hooks are executed
  if (!hasObstacle) {
    return null;
  }

  return (
    <group ref={groupRef} position={obstaclePos}>
      {/* 1. Translucent Volumetric Vehicle Body */}
      <mesh ref={meshRef}>
        <boxGeometry args={size} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isCritical ? 0.8 : 0.4}
          transparent
          opacity={isCritical ? 0.55 : 0.35}
          metalness={0.2}
          roughness={0.4}
        />
      </mesh>

      {/* 2. High-Visibility Glowing Wireframe Cage */}
      <lineSegments geometry={edgesGeom}>
        <lineBasicMaterial color={color} linewidth={2} />
      </lineSegments>

      {/* 3. Corner Brackets (Targeting Reticles) */}
      <group>
        {/* Front-top corners */}
        <mesh position={[size[0] / 2, size[1] / 2, -size[2] / 2]}>
          <boxGeometry args={[0.15, 0.15, 0.15]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
        <mesh position={[-size[0] / 2, size[1] / 2, -size[2] / 2]}>
          <boxGeometry args={[0.15, 0.15, 0.15]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
        {/* Front-bottom corners */}
        <mesh position={[size[0] / 2, -size[1] / 2, -size[2] / 2]}>
          <boxGeometry args={[0.15, 0.15, 0.15]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
        <mesh position={[-size[0] / 2, -size[1] / 2, -size[2] / 2]}>
          <boxGeometry args={[0.15, 0.15, 0.15]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      </group>

      {/* 4. Ground Projection Radar Ring */}
      <mesh position={[0, -size[1] / 2 + 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.9, 1.05, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.6} side={THREE.DoubleSide} />
      </mesh>

      {/* 5. 3D Floating HUD Distance Badge */}
      <group position={[0, size[1] / 2 + 0.45, 0]}>
        <mesh>
          <planeGeometry args={[1.4, 0.35]} />
          <meshBasicMaterial color="#020818" transparent opacity={0.85} side={THREE.DoubleSide} />
        </mesh>
        <Text
          position={[0, 0, 0.02]}
          fontSize={0.16}
          color={color}
          anchorX="center"
          anchorY="middle"
        >
          {`${sensor.sensor_id}: ${Math.round(sensor.distance_cm ?? 0)} cm`}
        </Text>
      </group>
    </group>
  );
}

function SensorIndicator({ zone, sensor }: { zone: string; sensor: SensorReading }) {
  const pos = ZONE_POSITIONS[zone] ?? [0, 0, 0];
  const color = warningLevelColor(sensor.warning_level);
  const indicatorRef = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (indicatorRef.current && sensor.obstacle_detected) {
      const scale = 1 + 0.3 * Math.abs(Math.sin(clock.getElapsedTime() * 4));
      indicatorRef.current.scale.setScalar(scale);
    }
  });

  return (
    <group position={[pos[0], 0.05, pos[2]]}>
      <mesh ref={indicatorRef} position={[0, 0.08, 0]}>
        <sphereGeometry args={[0.08, 12, 12]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={sensor.obstacle_detected ? 0.9 : 0.2}
        />
      </mesh>
      <Text
        position={[0, -0.18, 0]}
        fontSize={0.13}
        color="#94a3b8"
        anchorX="center"
        anchorY="middle"
      >
        {sensor.sensor_id}
      </Text>
    </group>
  );
}

function Scene({ sensors, fogDensity }: { sensors: SensorReading[]; fogDensity: number }) {
  const sensorMap = useMemo(() => {
    const m: Record<string, SensorReading> = {};
    for (const s of sensors) {
      m[s.zone] = s;
    }
    return m;
  }, [sensors]);

  return (
    <>
      {/* Atmospheric Fog Effect — keeps vehicle and obstacles sharp while fading distant background */}
      {fogDensity > 0 && (
        <fog
          attach="fog"
          args={[
            '#020818',
            12, // Near: starts behind ego vehicle (vehicle is at dist ~12.8)
            Math.max(30, 60 / Math.max(0.2, fogDensity)), // Far: normal ~60, heavy ~33
          ]}
        />
      )}

      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 12, 5]} intensity={1.0} castShadow />
      <pointLight position={[0, 6, 0]} intensity={0.8} color="#38bdf8" />

      {/* Road Grid Floor */}
      <Grid
        args={[30, 30]}
        cellSize={1}
        cellThickness={0.5}
        cellColor="#0d2070"
        sectionSize={5}
        sectionThickness={1.2}
        sectionColor="#1d4ed8"
        fadeDistance={30}
        position={[0, -0.05, -5]}
      />

      {/* Ego Vehicle */}
      <Vehicle />

      {/* Sensor Beams, 3D Obstacle Cuboids, and Sensor Status Dots */}
      {Object.entries(ZONE_POSITIONS).map(([zone]) => {
        const sensor = sensorMap[zone];
        if (!sensor) return null;
        return (
          <group key={zone}>
            <SensorBeam zone={zone} sensor={sensor} />
            <ObstacleCuboid zone={zone} sensor={sensor} />
            <SensorIndicator zone={zone} sensor={sensor} />
          </group>
        );
      })}

      {/* Orbit Controls */}
      <OrbitControls
        enablePan={true}
        enableZoom={true}
        minDistance={3}
        maxDistance={30}
        maxPolarAngle={Math.PI / 2.15}
        target={[0, 0.5, -4]}
      />
    </>
  );
}

interface ObstacleVisualizationProps {
  sensors: SensorReading[];
}

export function ObstacleVisualization({ sensors }: ObstacleVisualizationProps) {
  const [fogDensity, setFogDensity] = useState(1.0); // 0 = clear, 1 = normal fog, 1.8 = heavy fog

  const activeObstacles = sensors.filter(
    s => s.distance_cm !== null && s.distance_cm > 0 && s.distance_cm <= MAX_RANGE
  );

  return (
    <div className="w-full h-full relative">
      <CanvasErrorBoundary>
        <Canvas
          camera={{ position: [0, 8, 10], fov: 48 }}
          shadows
          style={{ background: 'transparent' }}
          gl={{ antialias: true, alpha: true }}
        >
          <Scene sensors={sensors} fogDensity={fogDensity} />
        </Canvas>
      </CanvasErrorBoundary>

      {/* Fog Simulation Slider / Toggle in Top Bar */}
      <div className="absolute top-3 right-3 flex items-center gap-2 bg-slate-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700/60 text-xs text-slate-300 z-10">
        <span>Fog Density:</span>
        <button
          onClick={() => setFogDensity(0)}
          className={`px-2 py-0.5 rounded ${fogDensity === 0 ? 'bg-cyan-500 text-black font-semibold' : 'text-slate-400 hover:text-white'}`}
        >
          Clear
        </button>
        <button
          onClick={() => setFogDensity(1.0)}
          className={`px-2 py-0.5 rounded ${fogDensity === 1.0 ? 'bg-cyan-500 text-black font-semibold' : 'text-slate-400 hover:text-white'}`}
        >
          Normal
        </button>
        <button
          onClick={() => setFogDensity(1.8)}
          className={`px-2 py-0.5 rounded ${fogDensity === 1.8 ? 'bg-cyan-500 text-black font-semibold' : 'text-slate-400 hover:text-white'}`}
        >
          Heavy
        </button>
      </div>

      {/* Legend overlay */}
      <div className="absolute bottom-3 right-3 flex flex-col gap-1 text-xs bg-slate-900/80 backdrop-blur-md p-2.5 rounded-lg border border-slate-800 z-10">
        {[
          { level: 'CRITICAL', color: '#ef4444', label: '< 50cm' },
          { level: 'WARNING', color: '#f97316', label: '50–100cm' },
          { level: 'CAUTION', color: '#eab308', label: '100–150cm' },
          { level: 'SAFE', color: '#22c55e', label: '> 150cm' },
        ].map(({ level, color, label }) => (
          <div key={level} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm shadow-sm" style={{ backgroundColor: color }} />
            <span className="text-slate-300 font-medium">{level}</span>
            <span className="text-slate-500">{label}</span>
          </div>
        ))}
      </div>

      {/* Active 3D Cuboids Count & HUD Status */}
      <div className="absolute top-3 left-3 flex flex-col gap-1 z-10">
        <div className="flex items-center gap-2 bg-slate-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700/60 text-xs">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-slate-300">
            <strong className="text-cyan-400 font-mono text-sm">{activeObstacles.length}</strong> 3D Vehicle Cuboids Visible
          </span>
        </div>
      </div>
    </div>
  );
}
