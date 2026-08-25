"""Expected failure types for SkyTrace Step 6 analysis."""


class AnalysisError(Exception):
    """Base class for expected Step 6 failures."""


class SceneInputError(AnalysisError):
    """Raised when a Step 3 georeferenced scene is unavailable or invalid."""


class MeasurementInputError(AnalysisError):
    """Raised when a requested measurement or unit is invalid."""


class AnalysisOutputError(AnalysisError):
    """Raised when the Step 6 output location is unsafe or unwritable."""
