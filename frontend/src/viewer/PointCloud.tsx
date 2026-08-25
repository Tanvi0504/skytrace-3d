import { useLoader } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { BufferGeometry, Float32BufferAttribute } from "three";
import { useEffect, useMemo } from "react";
import type { SceneAsset } from "../types/api";
import { apiUrl } from "../services/api";

type Props = {
  asset?: SceneAsset;
  evidenceMode: boolean;
};

const MAX_SOURCE_POINTS = 2_000_000;
const MAX_DISPLAY_POINTS = 250_000;

export function SceneGeometry({ asset, evidenceMode }: Props) {
  if (!asset) return <EmptyScene />;
  if (asset.format === "PLY" && (asset.point_count ?? 0) > MAX_SOURCE_POINTS) return <LargeCloudNotice pointCount={asset.point_count ?? 0} />;
  if (asset.format === "PLY") return <PlyCloud asset={asset} evidenceMode={evidenceMode} />;
  if (asset.format === "GLTF" || asset.format === "GLB") return <GltfMesh asset={asset} />;
  if (asset.format === "OBJ") return <ObjMesh asset={asset} />;
  return <EmptyScene />;
}

function PlyCloud({ asset, evidenceMode }: Required<Props>) {
  const source = useLoader(PLYLoader, apiUrl(asset.url));
  const geometry = useMemo(() => decimateForDisplay(source, MAX_DISPLAY_POINTS), [source]);
  useEffect(() => () => {
    if (geometry !== source) geometry.dispose();
  }, [geometry, source]);
  return (
    <points geometry={geometry}>
      <pointsMaterial attach="material" size={0.08} color={evidenceMode ? "#b9c4bf" : "#d8e5df"} />
    </points>
  );
}

function decimateForDisplay(source: BufferGeometry, maximum: number): BufferGeometry {
  const positions = source.getAttribute("position");
  if (!positions || positions.count <= maximum) return source;
  const step = Math.ceil(positions.count / maximum);
  const count = Math.ceil(positions.count / step);
  const target = new BufferGeometry();
  const output = new Float32Array(count * 3);
  const colors = source.getAttribute("color");
  const outputColors = colors ? new Float32Array(count * 3) : null;
  let destination = 0;
  for (let index = 0; index < positions.count; index += step) {
    output[destination * 3] = positions.getX(index);
    output[destination * 3 + 1] = positions.getY(index);
    output[destination * 3 + 2] = positions.getZ(index);
    if (colors && outputColors) {
      outputColors[destination * 3] = colors.getX(index);
      outputColors[destination * 3 + 1] = colors.getY(index);
      outputColors[destination * 3 + 2] = colors.getZ(index);
    }
    destination += 1;
  }
  target.setAttribute("position", new Float32BufferAttribute(output, 3));
  if (outputColors) target.setAttribute("color", new Float32BufferAttribute(outputColors, 3));
  target.computeBoundingSphere();
  return target;
}

function GltfMesh({ asset }: { asset: SceneAsset }) {
  const gltf = useLoader(GLTFLoader, apiUrl(asset.url));
  return <primitive object={gltf.scene} />;
}

function ObjMesh({ asset }: { asset: SceneAsset }) {
  const obj = useLoader(OBJLoader, apiUrl(asset.url));
  return <primitive object={obj} />;
}

function EmptyScene() {
  return (
    <Html center className="emptyScene">
      No browser-supported Step 2/3 reconstruction asset is available for this run.
    </Html>
  );
}

function LargeCloudNotice({ pointCount }: { pointCount: number }) {
  return (
    <Html center className="emptyScene">
      This point cloud has {pointCount.toLocaleString()} points and exceeds the browser safety limit. Download the original artifact from results or prepare a display-only decimated view; the scientific source file is unchanged.
    </Html>
  );
}
