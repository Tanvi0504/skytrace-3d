"""Replaceable pretrained object-detector interface and Ultralytics YOLO backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np

from pipeline.objects.errors import DetectorInitializationError, DetectorRuntimeError
from pipeline.objects.models import DetectorInfo, RawDetection


class ObjectDetector(ABC):
    """A pretrained detector with optional tracker-provided IDs.

    Implementations must not perform their own motion classification. The
    returned ``track_id`` is optional because a detector can be used without a
    tracker or because an existing tracker can temporarily lose an object.
    """

    @abstractmethod
    def initialize(self) -> DetectorInfo:
        """Load model resources and return the exact model label set."""

    @abstractmethod
    def detect(
        self,
        image: np.ndarray,
        *,
        confidence_threshold: float,
        iou_threshold: float,
        classes: Optional[tuple[str, ...]],
        tracking: bool,
        tracker_config: str,
    ) -> list[RawDetection]:
        """Return detections for a single BGR image in processing order."""


class UltralyticsYOLODetector(ObjectDetector):
    """Lazy Ultralytics YOLO wrapper using its supported ByteTrack integration.

    ``ultralytics`` and model weights are intentionally loaded only when the
    pipeline executes. This keeps importing Step 4 and running its unit tests
    independent of a model download or GPU runtime.
    """

    def __init__(self, model_name: str, device: str) -> None:
        self.model_name = model_name
        self.device = device
        self._model = None
        self._class_names: dict[int, str] = {}

    def initialize(self) -> DetectorInfo:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise DetectorInitializationError(
                "Ultralytics YOLO is unavailable. Install the project's declared "
                "'ultralytics' dependency before running Step 4."
            ) from exc
        try:
            self._model = YOLO(self.model_name)
            raw_names = self._model.names
            if isinstance(raw_names, dict):
                self._class_names = {
                    int(class_id): str(name).lower()
                    for class_id, name in raw_names.items()
                }
            else:
                self._class_names = {
                    index: str(name).lower() for index, name in enumerate(raw_names)
                }
        except Exception as exc:  # External model loading has library-specific errors.
            raise DetectorInitializationError(
                f"Could not load pretrained YOLO model {self.model_name!r}: {exc}"
            ) from exc
        return DetectorInfo(
            backend="ultralytics-yolo",
            model_name=self.model_name,
            supported_classes=tuple(
                self._class_names[index] for index in sorted(self._class_names)
            ),
            device=self.device,
            tracker_name="ByteTrack" if self._model is not None else None,
        )

    def detect(
        self,
        image: np.ndarray,
        *,
        confidence_threshold: float,
        iou_threshold: float,
        classes: Optional[tuple[str, ...]],
        tracking: bool,
        tracker_config: str,
    ) -> list[RawDetection]:
        if self._model is None:
            raise DetectorRuntimeError("Detector was used before initialize()")
        class_ids = None
        if classes is not None:
            requested = set(classes)
            class_ids = [
                class_id
                for class_id, name in self._class_names.items()
                if name in requested
            ]
        try:
            common_options = {
                "source": image,
                "conf": confidence_threshold,
                "iou": iou_threshold,
                "classes": class_ids,
                "device": self.device,
                "verbose": False,
            }
            if tracking:
                results = self._model.track(
                    **common_options,
                    persist=True,
                    tracker=tracker_config,
                )
            else:
                results = self._model.predict(**common_options)
        except Exception as exc:  # External model execution has library-specific errors.
            raise DetectorRuntimeError(f"YOLO inference failed: {exc}") from exc

        if not results or results[0].boxes is None:
            return []
        boxes = results[0].boxes
        coordinates = boxes.xyxy.cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        class_ids = boxes.cls.cpu().tolist()
        track_ids = boxes.id.cpu().tolist() if boxes.id is not None else [None] * len(coordinates)
        return [
            RawDetection(
                class_name=self._class_names.get(int(class_id), str(int(class_id))),
                confidence=float(confidence),
                bbox_xyxy=tuple(float(value) for value in box),
                track_id=int(track_id) if track_id is not None else None,
            )
            for box, confidence, class_id, track_id in zip(
                coordinates, confidences, class_ids, track_ids
            )
        ]
