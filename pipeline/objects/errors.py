"""Domain-specific errors for Step 4 object intelligence."""


class ObjectPipelineError(Exception):
    """Base class for expected object-pipeline failures."""


class FramesInputError(ObjectPipelineError):
    """Raised when selected-frame input is absent or unusable."""


class DetectorInitializationError(ObjectPipelineError):
    """Raised when the configured pretrained detector cannot be loaded."""


class DetectorRuntimeError(ObjectPipelineError):
    """Raised when a detector cannot process an individual frame."""


class ObjectOutputError(ObjectPipelineError):
    """Raised when the Step 4 output workspace is unsafe or unwritable."""
