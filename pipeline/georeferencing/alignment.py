"""Similarity-transform estimation and deterministic RANSAC outlier filtering."""

from __future__ import annotations

import itertools
import math

import numpy as np

from pipeline.georeferencing.errors import AlignmentError
from pipeline.georeferencing.models import AlignmentEstimate, SimilarityTransform


def _validate_points(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    source_array = np.asarray(source, dtype=float)
    target_array = np.asarray(target, dtype=float)
    if source_array.ndim != 2 or source_array.shape[1] != 3:
        raise AlignmentError("Source trajectory points must have shape (N, 3)")
    if source_array.shape != target_array.shape:
        raise AlignmentError("Source and target trajectories must have identical shape")
    if source_array.shape[0] < 3:
        raise AlignmentError(
            "At least three camera/GPS correspondences are required for 3D alignment"
        )
    if not np.all(np.isfinite(source_array)) or not np.all(np.isfinite(target_array)):
        raise AlignmentError("Alignment trajectories contain non-finite coordinates")
    return source_array, target_array


def _require_non_collinear(points: np.ndarray, label: str) -> None:
    centered = points - np.mean(points, axis=0)
    if np.linalg.matrix_rank(centered, tol=1e-9) < 2:
        raise AlignmentError(
            f"{label} trajectory is collinear or degenerate; it cannot constrain "
            "a full 3D scene orientation. Capture a trajectory with lateral motion."
        )


def estimate_similarity_transform(
    source: np.ndarray,
    target: np.ndarray,
    *,
    estimate_scale: bool = True,
) -> SimilarityTransform:
    """Estimate ``target = s R source + t`` using least-squares Umeyama SVD."""
    source_array, target_array = _validate_points(source, target)
    _require_non_collinear(source_array, "Reconstruction camera")
    _require_non_collinear(target_array, "GPS")

    source_mean = np.mean(source_array, axis=0)
    target_mean = np.mean(target_array, axis=0)
    source_centered = source_array - source_mean
    target_centered = target_array - target_mean
    source_variance = float(np.mean(np.sum(source_centered * source_centered, axis=1)))
    if source_variance <= np.finfo(float).eps:
        raise AlignmentError("Reconstruction camera centers have zero spatial variance")

    covariance = (target_centered.T @ source_centered) / source_array.shape[0]
    left, singular_values, right_transpose = np.linalg.svd(covariance)
    correction = np.eye(3)
    if np.linalg.det(left) * np.linalg.det(right_transpose) < 0:
        correction[-1, -1] = -1.0
    rotation = left @ correction @ right_transpose
    if estimate_scale:
        scale = float(np.sum(singular_values * np.diag(correction)) / source_variance)
        if not math.isfinite(scale) or scale <= 0:
            raise AlignmentError("Estimated a non-positive or non-finite similarity scale")
    else:
        scale = 1.0
    translation = target_mean - scale * (rotation @ source_mean)
    return SimilarityTransform(scale=scale, rotation=rotation, translation=translation)


def _residuals(
    transform: SimilarityTransform,
    source: np.ndarray,
    target: np.ndarray,
) -> np.ndarray:
    return np.linalg.norm(transform.apply(source) - target, axis=1)


def estimate_robust_similarity_transform(
    source: np.ndarray,
    target: np.ndarray,
    *,
    estimate_scale: bool,
    threshold_metres: float,
    max_iterations: int,
) -> AlignmentEstimate:
    """Use 3-point RANSAC, then refit a Sim(3) on its inlier trajectory pairs.

    The supplied threshold is an inlier-consistency tolerance in local ENU
    metres, not a claim about positional accuracy.
    """
    source_array, target_array = _validate_points(source, target)
    if threshold_metres <= 0:
        raise ValueError("threshold_metres must be > 0")
    _require_non_collinear(source_array, "Reconstruction camera")
    _require_non_collinear(target_array, "GPS")

    count = source_array.shape[0]
    all_combinations = math.comb(count, 3)
    if all_combinations <= max_iterations:
        samples = list(itertools.combinations(range(count), 3))
    else:
        generator = np.random.default_rng(0)
        samples = [
            tuple(sorted(generator.choice(count, size=3, replace=False).tolist()))
            for _ in range(max_iterations)
        ]

    best_mask: np.ndarray | None = None
    best_score: tuple[int, float] | None = None
    for sample in samples:
        indices = np.array(sample, dtype=int)
        try:
            candidate = estimate_similarity_transform(
                source_array[indices],
                target_array[indices],
                estimate_scale=estimate_scale,
            )
        except AlignmentError:
            continue
        candidate_residuals = _residuals(candidate, source_array, target_array)
        candidate_mask = candidate_residuals <= threshold_metres
        inlier_count = int(np.count_nonzero(candidate_mask))
        if inlier_count < 3:
            continue
        score = (inlier_count, -float(np.mean(candidate_residuals[candidate_mask])))
        if best_score is None or score > best_score:
            best_mask = candidate_mask
            best_score = score

    if best_mask is None:
        raise AlignmentError(
            "RANSAC found fewer than three mutually consistent camera/GPS pairs. "
            "Review timing, frame identifiers, GPS quality, or the inlier threshold."
        )

    transform = estimate_similarity_transform(
        source_array[best_mask], target_array[best_mask], estimate_scale=estimate_scale
    )
    residuals = _residuals(transform, source_array, target_array)
    inlier_mask = residuals <= threshold_metres
    if int(np.count_nonzero(inlier_mask)) < 3:
        raise AlignmentError("Refined transform has fewer than three inlier pairs")
    transform = estimate_similarity_transform(
        source_array[inlier_mask],
        target_array[inlier_mask],
        estimate_scale=estimate_scale,
    )
    residuals = _residuals(transform, source_array, target_array)
    inlier_mask = residuals <= threshold_metres
    return AlignmentEstimate(
        transform=transform,
        residuals_metres=residuals,
        inlier_mask=inlier_mask,
        method="RANSAC-refined Umeyama similarity transform (Sim(3))",
    )
