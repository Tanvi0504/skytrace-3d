"""SkyTrace Step 5: conservative 2D-object to 3D-scene association."""

from pipeline.scene_objects.api import associate_objects_with_3d_scene
from pipeline.scene_objects.models import (
    CameraIntrinsics,
    GeoreferenceTransform,
    ObjectObservation,
    SceneAssociationConfig,
    SceneAssociationResult,
    SceneObjectAssociation,
    TriangulationEstimate,
    WorldRay,
)

__all__ = [
    "CameraIntrinsics",
    "GeoreferenceTransform",
    "ObjectObservation",
    "SceneAssociationConfig",
    "SceneAssociationResult",
    "SceneObjectAssociation",
    "TriangulationEstimate",
    "WorldRay",
    "associate_objects_with_3d_scene",
]
