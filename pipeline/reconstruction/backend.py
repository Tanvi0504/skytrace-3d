"""Backend interface for replaceable SkyTrace reconstruction engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pipeline.reconstruction.models import ReconstructionConfig, ReconstructionResult


class ReconstructionBackend(ABC):
    """Contract implemented by reconstruction engines such as COLMAP.

    A future ``VGGTBackend`` can implement this contract without requiring
    callers to know its command-line/API details.
    """

    name: str

    @abstractmethod
    def preflight(self, config: ReconstructionConfig) -> None:
        """Validate dependencies required by this backend."""

    @abstractmethod
    def run(
        self,
        config: ReconstructionConfig,
        image_paths: list[Path],
    ) -> ReconstructionResult:
        """Run reconstruction after input and workspace validation."""

