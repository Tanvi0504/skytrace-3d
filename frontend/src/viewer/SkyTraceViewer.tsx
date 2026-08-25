import { OrbitControls, Html, Bounds } from "@react-three/drei";
import { Canvas, ThreeEvent } from "@react-three/fiber";
import { RotateCcw } from "lucide-react";
import { Suspense, useRef } from "react";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { Object3D, SceneAsset } from "../types/api";
import { SceneGeometry } from "./PointCloud";

type Props = {
  asset?: SceneAsset;
  objects: Object3D[];
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

export function SkyTraceViewer({ asset, objects, evidenceMode, measuring, selectedPoints, onPoint, onObject }: Props) {
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
            </Bounds>
          </group>
        </Suspense>
        <OrbitControls ref={controls} makeDefault enableDamping />
      </Canvas>
    </div>
  );
}
