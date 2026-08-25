import { useLoader } from "@react-three/fiber";
import { useMemo } from "react";
import { BufferGeometry, Color, Float32BufferAttribute, PointsMaterial } from "three";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { SceneAsset } from "../types/api";

type Props = {
  asset?: SceneAsset;
  evidenceMode: boolean;
};

function colorizeGeometry(geometry: BufferGeometry, evidenceMode: boolean) {
  const count = geometry.getAttribute("position")?.count ?? 0;
  if (!count || !evidenceMode) return geometry;
  const colors: number[] = [];
  for (let index = 0; index < count; index += 1) {
    const color = new Color(index % 5 === 0 ? "#d7a533" : index % 7 === 0 ? "#d85a47" : "#57b881");
    colors.push(color.r, color.g, color.b);
  }
  geometry.setAttribute("color", new Float32BufferAttribute(colors, 3));
  return geometry;
}

export function SceneGeometry({ asset, evidenceMode }: Props) {
  if (!asset) return <FallbackScene evidenceMode={evidenceMode} />;
  if (asset.format === "PLY") return <PlyCloud asset={asset} evidenceMode={evidenceMode} />;
  if (asset.format === "GLTF" || asset.format === "GLB") return <GltfMesh asset={asset} />;
  return <FallbackScene evidenceMode={evidenceMode} />;
}

function PlyCloud({ asset, evidenceMode }: Required<Props>) {
  const geometry = useLoader(PLYLoader, asset.url);
  const renderedGeometry = useMemo(() => colorizeGeometry(geometry.clone(), evidenceMode), [geometry, evidenceMode]);
  return (
    <points geometry={renderedGeometry}>
      <pointsMaterial attach="material" size={0.08} vertexColors={evidenceMode} color={evidenceMode ? undefined : "#d8e5df"} />
    </points>
  );
}

function GltfMesh({ asset }: { asset: SceneAsset }) {
  const gltf = useLoader(GLTFLoader, asset.url);
  return <primitive object={gltf.scene} />;
}

function FallbackScene({ evidenceMode }: { evidenceMode: boolean }) {
  const material = useMemo(
    () => new PointsMaterial({ size: 0.09, color: evidenceMode ? "#d7a533" : "#d8e5df" }),
    [evidenceMode]
  );
  const geometry = useMemo(() => {
    const g = new BufferGeometry();
    const points: number[] = [];
    for (let i = 0; i < 800; i += 1) {
      const x = (Math.random() - 0.5) * 18;
      const z = (Math.random() - 0.5) * 18;
      const y = Math.sin(x * 0.4) * 0.5 + Math.cos(z * 0.35) * 0.5;
      points.push(x, y, z);
    }
    g.setAttribute("position", new Float32BufferAttribute(points, 3));
    return g;
  }, []);
  return <points geometry={geometry} material={material} />;
}

