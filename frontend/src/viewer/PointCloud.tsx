import { useLoader } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import type { SceneAsset } from "../types/api";

type Props = {
  asset?: SceneAsset;
  evidenceMode: boolean;
};

export function SceneGeometry({ asset, evidenceMode }: Props) {
  if (!asset) return <EmptyScene />;
  if (asset.format === "PLY") return <PlyCloud asset={asset} evidenceMode={evidenceMode} />;
  if (asset.format === "GLTF" || asset.format === "GLB") return <GltfMesh asset={asset} />;
  if (asset.format === "OBJ") return <ObjMesh asset={asset} />;
  return <EmptyScene />;
}

function PlyCloud({ asset, evidenceMode }: Required<Props>) {
  const geometry = useLoader(PLYLoader, asset.url);
  return (
    <points geometry={geometry}>
      <pointsMaterial attach="material" size={0.08} color={evidenceMode ? "#b9c4bf" : "#d8e5df"} />
    </points>
  );
}

function GltfMesh({ asset }: { asset: SceneAsset }) {
  const gltf = useLoader(GLTFLoader, asset.url);
  return <primitive object={gltf.scene} />;
}

function ObjMesh({ asset }: { asset: SceneAsset }) {
  const obj = useLoader(OBJLoader, asset.url);
  return <primitive object={obj} />;
}

function EmptyScene() {
  return (
    <Html center className="emptyScene">
      No browser-supported Step 2/3 reconstruction asset is available for this run.
    </Html>
  );
}
