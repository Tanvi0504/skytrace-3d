"""Expected errors for SkyTrace Step 3 georeferencing."""

from __future__ import annotations


class GeoreferencingError(Exception):
    """Base class for expected Step 3 failures."""


class ReconstructionInputError(GeoreferencingError):
    """Raised when a Step 2 reconstruction artifact is missing or malformed."""


class GPSMetadataError(GeoreferencingError):
    """Raised when GPS metadata is missing, unsupported, or unusable."""


class CorrespondenceError(GeoreferencingError):
    """Raised when poses and GPS observations cannot be paired sufficiently."""


class AlignmentError(GeoreferencingError):
    """Raised when a stable trajectory transform cannot be estimated."""


class PointCloudError(GeoreferencingError):
    """Raised when a Step 2 PLY point cloud cannot be transformed safely."""


class GeoreferenceOutputError(GeoreferencingError):
    """Raised when the output workspace cannot safely be created."""
