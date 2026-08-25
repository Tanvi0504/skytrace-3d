import { OrbitControls, Html, Bounds } from "@react-three/drei";
import { Canvas, ThreeEvent } from "@react-three/fiber";
import { RotateCcw } from "lucide-react";
import { Suspense, useMemo, useRef } from "react";
import { BufferGeometry, Line as ThreeLine, LineBasicMaterial, Vector3 } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { EvidenceInfo, Object3D, SceneAsset } from "../types/api";
import { SceneGeometry } from "./PointCloud";

type Props = {
  asset?: SceneAsset;
  objects: Object3D[];
  evidence?: EvidenceInfo | null;
  evidenceMode: boolean;
  measuring: boolean;
  selectedPoints: number[][];
  onPoint: (point: number[]) => void;
  onObject: (object: Object3D) => void;
};

const objectColor = (object: Object3D) => {
  if (object.position_status === "unavailable") return "#8d97a5";
  if (object.is_dynamic_candidate) return "#f5b04c";
  return "#5fb3ff";
};

const EVIDENCE_COLORS: Record<string, string> = {
  HIGH: "#57b881",
  MEDIUM: "#d7a533",
  LOW: "#f36f5f",
  INSUFFICIENT: "#8d97a5"
};

export function SkyTraceViewer({ asset, objects, evidence, evidenceMode, measuring, selectedPoints, onPoint, onObject }: Props) {
  const controls = useRef<OrbitControlsImpl | null>(null);
  const selectableObjects = objects.filter((object) => object.position && object.position.length === 3);

  function handleSceneClick(event: ThreeEvent<MouseEvent>) {
    if (!measuring) return;
    event.stopPropagation();
    onPoint([event.point.x, event.point.y, event.point.z]);
  }

  return (
    <div className="viewerShell">
      <button className="iconButton resetButton" title="Reset camera" onClick={() => controls.current?.reset()}>
        <RotateCcw size={18} />
      </button>
      <Canvas camera={{ position: [12, 10, 14], fov: 48 }}>
        <color attach="background" args={["#101419"]} />
        <ambientLight intensity={0.65} />
        <directionalLight position={[4, 9, 5]} intensity={1.5} />
        <gridHelper args={[40, 40, "#3a4653", "#26313b"]} />
        <Suspense fallback={<Html center>Loading scene</Html>}>
          <group onPointerDown={handleSceneClick}>
            <Bounds fit clip observe margin={1.2}>
              <SceneGeometry asset={asset} evidenceMode={evidenceMode} />
              {evidenceMode && <EvidenceOverlay evidence={evidence} />}
              {selectableObjects.map((object) => {
                const position = object.position as number[];
                return (
                  <mesh
                    key={object.object_id}
                    position={[position[0], position[1], position[2]]}
                    onPointerDown={(event) => {
                      event.stopPropagation();
                      onObject(object);
                    }}
                  >
                    <sphereGeometry args={[0.35, 24, 24]} />
                    <meshStandardMaterial color={objectColor(object)} emissive={objectColor(object)} emissiveIntensity={0.25} />
                    <Html distanceFactor={12} position={[0, 0.65, 0]} center className="markerLabel">
                      {object.class_name} #{object.track_id ?? object.object_id}
                    </Html>
                  </mesh>
                );
              })}
              {selectedPoints.map((point, index) => (
                <mesh key={`${point.join(",")}-${index}`} position={[point[0], point[1], point[2]]}>
                  <sphereGeometry args={[0.22, 16, 16]} />
                  <meshBasicMaterial color={index === 0 ? "#4cd6b4" : "#f36f5f"} />
                </mesh>
              ))}
              {selectedPoints.length === 2 && <MeasurementLine points={selectedPoints} />}
            </Bounds>
          </group>
        </Suspense>
        <OrbitControls ref={controls} makeDefault enableDamping />
      </Canvas>
    </div>
  );
}

function MeasurementLine({ points }: { points: number[][] }) {
  const line = useMemo(() => {
    const vertices = points.map((point) => new Vector3(point[0], point[1], point[2]));
    const geometry = new BufferGeometry().setFromPoints(vertices);
    return new ThreeLine(geometry, new LineBasicMaterial({ color: "#4cd6b4", linewidth: 2 }));
  }, [points]);
  return <primitive object={line} />;
}

function EvidenceOverlay({ evidence }: { evidence?: EvidenceInfo | null }) {
  const regions = evidence?.quality_regions ?? [];
  return (
    <>
      {regions.map((region, index) => {
        const centre = Array.isArray(region.centre) ? region.centre.map(Number) : null;
        const level = String(region.evidence_level ?? "INSUFFICIENT").toUpperCase();
        const size = Number(region.cell_size_metres ?? 1);
        if (!centre || centre.length !== 3 || centre.some((value) => Number.isNaN(value))) return null;
        return (
          <mesh key={`${centre.join(",")}-${index}`} position={[centre[0], centre[1], centre[2]]}>
            <boxGeometry args={[size, size, size]} />
            <meshBasicMaterial color={EVIDENCE_COLORS[level] ?? EVIDENCE_COLORS.INSUFFICIENT} transparent opacity={0.22} depthWrite={false} />
            <Html distanceFactor={18} center className="evidenceLabel">
              {level}
            </Html>
          </mesh>
        );
      })}
    </>
  );
}
