"""Expected failure types for Step 5 scene-object association."""


class SceneAssociationError(Exception):
    """Base class for expected Step 5 failures."""


class ObjectInputError(SceneAssociationError):
    """Raised when Step 4 object metadata is missing or malformed."""


class ReconstructionInputError(SceneAssociationError):
    """Raised when required Step 2 camera-pose data is missing or malformed."""


class CameraCalibrationError(SceneAssociationError):
    """Raised for invalid or unavailable camera-intrinsic data."""


class GeometryError(SceneAssociationError):
    """Raised when a ray or triangulation problem is geometrically degenerate."""


class SceneOutputError(SceneAssociationError):
    """Raised when the output workspace is unsafe or cannot be written."""
