// 3D Obstacle Visualization using React Three Fiber
import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Grid } from '@react-three/drei';
import * as THREE from 'three';
import type { SensorReading } from '../../types';
import { warningLevelColor } from '../../utils';

// Sensor zone 3D positions (relative to vehicle center)
// Vehicle is ~4 units long, 2 units wide
const ZONE_POSITIONS: Record<string, [number, number, number]> = {
  front_left: [-1.0, 0, -3.5],
  front_center: [0, 0, -3.5],
  front_center_left: [-0.3, 0, -3.5],
  front_center_right: [0.3, 0, -3.5],
  front_right: [1.0, 0, -3.5],
  left_side: [-2.5, 0, 0],
  right_side: [2.5, 0, 0],
  roof_center: [0, 1.2, -0.3],
};

const ZONE_DIRECTIONS: Record<string, [number, number, number]> = {
  front_left: [-0.25, 0, -1],
  front_center: [0, 0, -1],
  front_center_left: [-0.08, 0, -1],
  front_center_right: [0.08, 0, -1],
  front_right: [0.25, 0, -1],
  left_side: [-1, 0, 0],
  right_side: [1, 0, 0],
  roof_center: [0, 0.1, -1],
};

const MAX_RANGE = 400;
const SCALE = 0.015; // cm to Three.js units

function Vehicle() {
  return (
    <group>
      {/* Car body */}
      <mesh position={[0, 0.3, 0]} castShadow>
        <boxGeometry args={[1.8, 0.5, 4]} />
        <meshStandardMaterial color="#1e40af" metalness={0.6} roughness={0.4} />
      </mesh>
      {/* Roof */}
      <mesh position={[0, 0.8, -0.3]} castShadow>
        <boxGeometry args={[1.5, 0.4, 2.2]} />
        <meshStandardMaterial color="#1d4ed8" metalness={0.5} roughness={0.5} />
      </mesh>
      {/* Wheels */}
      {[[-0.95, -0.05, -1.4], [0.95, -0.05, -1.4], [-0.95, -0.05, 1.4], [0.95, -0.05, 1.4]].map(([x, y, z], i) => (
        <mesh key={i} position={[x, y, z] as [number, number, number]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.35, 0.35, 0.25, 16]} />
          <meshStandardMaterial color="#0f172a" metalness={0.3} roughness={0.8} />
        </mesh>
      ))}
      {/* Headlights */}
      {[[-0.6, 0.3, -2.01], [0.6, 0.3, -2.01]].map(([x, y, z], i) => (
        <mesh key={i} position={[x, y, z] as [number, number, number]}>
          <boxGeometry args={[0.3, 0.15, 0.05]} />
          <meshStandardMaterial color="#fef08a" emissive="#fef08a" emissiveIntensity={0.5} />
        </mesh>
      ))}
      {/* Front indicator bar */}
      <mesh position={[0, 0.1, -2.01]}>
        <boxGeometry args={[1.8, 0.05, 0.05]} />
        <meshStandardMaterial color="#22d3ee" emissive="#22d3ee" emissiveIntensity={0.3} />
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
    startPos[0] + dir[0] * beamLength / 2,
    startPos[1],
    startPos[2] + dir[2] * beamLength / 2,
  ];

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const alpha = sensor.obstacle_detected
        ? 0.4 + 0.3 * Math.sin(clock.getElapsedTime() * 3)
        : 0.1;
      (meshRef.current.material as THREE.MeshStandardMaterial).opacity = alpha;
    }
  });

  const isVerticalBeam = Math.abs(dir[2]) < 0.1;
  const rotation: [number, number, number] = isVerticalBeam ? [0, 0, Math.PI / 2] : [Math.PI / 2, 0, 0];
  const scale: [number, number, number] = isVerticalBeam
    ? [beamLength, 0.04, 0.04]
    : [0.04, beamLength, 0.04];

  return (
    <mesh ref={meshRef} position={midPoint} rotation={rotation} scale={scale}>
      <cylinderGeometry args={[0.5, 0.5, 1, 6]} />
      <meshStandardMaterial color={color} transparent opacity={0.2} />
    </mesh>
  );
}

function ObstacleCuboid({ zone, sensor }: { zone: string; sensor: SensorReading }) {
  const meshRef = useRef<THREE.Mesh>(null);

  if (!sensor.obstacle_detected || sensor.distance_cm === null) return null;

  const startPos = ZONE_POSITIONS[zone] as [number, number, number];
  const dir = ZONE_DIRECTIONS[zone] as [number, number, number];
  const dist = Math.min(sensor.distance_cm, MAX_RANGE) * SCALE;

  const obstaclePos: [number, number, number] = [
    startPos[0] + dir[0] * dist,
    0.25,
    startPos[2] + dir[2] * dist,
  ];

  const color = warningLevelColor(sensor.warning_level);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const t = clock.getElapsedTime();
      meshRef.current.position.y = 0.25 + 0.03 * Math.sin(t * 2);
      (meshRef.current.material as THREE.MeshStandardMaterial).emissiveIntensity =
        0.3 + 0.2 * Math.sin(t * 3);
    }
  });

  const size: [number, number, number] = [0.5, 0.5, 0.5];

  return (
    <group position={obstaclePos}>
      <mesh ref={meshRef}>
        <boxGeometry args={size} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.3}
          transparent
          opacity={0.75}
          metalness={0.1}
          roughness={0.6}
        />
      </mesh>
      {/* Wireframe outline */}
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(...size)]} />
        <lineBasicMaterial color={color} />
      </lineSegments>
      {/* Distance label */}
      <Text
        position={[0, 0.5, 0]}
        fontSize={0.18}
        color={color}
        anchorX="center"
        anchorY="middle"
        font={undefined}
      >
        {`${Math.round(sensor.distance_cm)}cm`}
      </Text>
    </group>
  );
}

function SensorIndicator({ zone, sensor }: { zone: string; sensor: SensorReading }) {
  const pos = ZONE_POSITIONS[zone] as [number, number, number];
  const color = warningLevelColor(sensor.warning_level);
  const indicatorRef = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (indicatorRef.current && sensor.obstacle_detected) {
      const scale = 1 + 0.3 * Math.abs(Math.sin(clock.getElapsedTime() * 4));
      indicatorRef.current.scale.setScalar(scale);
    }
  });

  return (
    <group position={[pos[0], 0, pos[2]]}>
      <mesh ref={indicatorRef} position={[0, 0.08, 0]}>
        <sphereGeometry args={[0.08, 8, 8]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={sensor.obstacle_detected ? 0.8 : 0.2}
        />
      </mesh>
      <Text
        position={[0, -0.2, 0]}
        fontSize={0.12}
        color="#94a3b8"
        anchorX="center"
        anchorY="middle"
        font={undefined}
      >
        {sensor.sensor_id}
      </Text>
    </group>
  );
}

function Scene({ sensors }: { sensors: SensorReading[] }) {
  const sensorMap = useMemo(() => {
    const m: Record<string, SensorReading> = {};
    for (const s of sensors) {
      m[s.zone] = s;
    }
    return m;
  }, [sensors]);

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 10, 5]} intensity={0.8} castShadow />
      <pointLight position={[0, 5, 0]} intensity={0.5} color="#22d3ee" />

      {/* Grid floor */}
      <Grid
        args={[20, 20]}
        cellSize={1}
        cellThickness={0.5}
        cellColor="#0d2070"
        sectionSize={5}
        sectionThickness={1}
        sectionColor="#1d4ed8"
        fadeDistance={25}
        position={[0, -0.05, 0]}
      />

      {/* Vehicle */}
      <Vehicle />

      {/* Sensor beams, obstacles, and indicators */}
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

      {/* Controls */}
      <OrbitControls
        enablePan={true}
        enableZoom={true}
        minDistance={3}
        maxDistance={25}
        maxPolarAngle={Math.PI / 2.2}
        target={[0, 0, 0]}
      />
    </>
  );
}

interface ObstacleVisualizationProps {
  sensors: SensorReading[];
}

export function ObstacleVisualization({ sensors }: ObstacleVisualizationProps) {
  return (
    <div className="w-full h-full relative">
      <Canvas
        camera={{ position: [0, 10, 12], fov: 50 }}
        shadows
        style={{ background: 'transparent' }}
        gl={{ antialias: true, alpha: true }}
      >
        <Scene sensors={sensors} />
      </Canvas>

      {/* Legend overlay */}
      <div className="absolute bottom-3 right-3 flex flex-col gap-1 text-xs">
        {[
          { level: 'CRITICAL', color: '#ef4444', label: '< 50cm' },
          { level: 'WARNING', color: '#f97316', label: '50–100cm' },
          { level: 'CAUTION', color: '#eab308', label: '100–150cm' },
          { level: 'SAFE', color: '#22c55e', label: '> 150cm' },
        ].map(({ level, color, label }) => (
          <div key={level} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
            <span className="text-slate-400">{level}</span>
            <span className="text-slate-600">{label}</span>
          </div>
        ))}
      </div>

      {/* Sensor count */}
      <div className="absolute top-3 left-3 text-xs text-slate-400">
        <span className="font-mono text-cyan-400">{sensors.filter(s => s.obstacle_detected).length}</span>
        <span> / {sensors.length} sensors active</span>
      </div>
    </div>
  );
}
