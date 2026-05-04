#!/usr/bin/env python3
"""Calibrate a trained THP checkpoint with held-out residual bias correction."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.thp_neural import NeuralTransformerHawkesModel, series_group_key  # noqa: E402
from db_scripts.train_thp_model import (  # noqa: E402
    EVENT_TYPES,
    build_training_arrays,
    encode_label_ids,
    evaluate_by_category,
    evaluate_by_category_event_type,
    baseline_improvement,
    predict_counts,
    regression_metrics,
    target_label_key,
    target_stat_arrays,
    time_based_split,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate THP checkpoint forecasts.")
    parser.add_argument("--checkpoint", default="models/thp_gdelt.pt")
    parser.add_argument("--output", default=None, help="Defaults to overwriting --checkpoint.")
    parser.add_argument("--dataset-cache", default=None)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--val-fraction", type=float, default=None)
    parser.add_argument("--min-scope-samples", type=int, default=80)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_device(name: str) -> torch.device:
    if name in ("auto", "cuda") and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def checkpoint_training_args(
    checkpoint: Dict[str, Any],
    dataset_cache: str | None,
    val_fraction: float | None,
) -> argparse.Namespace:
    config = checkpoint.get("config", {})
    metadata = checkpoint.get("metadata", {})
    dimensions = metadata.get("dimension_summary", {})
    cache = dataset_cache or (
        f"models/thp_calibration_dataset_seq{config.get('seq_len', 30)}_"
        f"h{metadata.get('forecast_horizon', 7)}.npz"
    )
    return argparse.Namespace(
        dataset_cache=cache,
        rebuild_dataset_cache=False,
        seq_len=int(config.get("seq_len", 30)),
        forecast_horizon=int(metadata.get("forecast_horizon", 7)),
        top_countries=max(1, len(dimensions.get("top_countries", [])) or 50),
        top_actors=max(1, len(dimensions.get("top_actors", [])) or 50),
        top_country_pairs=max(0, len(dimensions.get("top_country_pairs", [])) or 30),
        top_actor_pairs=max(0, len(dimensions.get("top_actor_pairs", [])) or 30),
        top_event_roots=max(0, len(dimensions.get("top_event_roots", [])) or 20),
        top_event_codes=max(0, len(dimensions.get("top_event_codes", [])) or 50),
        min_series_events=int(metadata.get("min_series_events", 10)),
        val_fraction=float(val_fraction or metadata.get("evaluation", {}).get("validation_fraction", 0.15)),
    )


def ids_from_checkpoint(
    labels: List[Tuple[str, str]],
    checkpoint: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    fallback_series, fallback_events, fallback_groups, *_ = encode_label_ids(labels)
    series_to_id = {str(k): int(v) for k, v in checkpoint.get("series_to_id", {}).items()}
    event_type_to_id = {str(k): int(v) for k, v in checkpoint.get("event_type_to_id", {}).items()}
    group_to_id = {str(k): int(v) for k, v in checkpoint.get("series_group_to_id", {}).items()}
    if not series_to_id or not event_type_to_id or not group_to_id:
        return fallback_series, fallback_events, fallback_groups

    default_series = series_to_id.get("global:ALL", 0)
    default_event = event_type_to_id.get("all", 0)
    default_group = group_to_id.get("global", 0)
    series_ids = []
    event_ids = []
    group_ids = []
    for series_id, event_type in labels:
        series_ids.append(series_to_id.get(series_id, default_series))
        event_ids.append(event_type_to_id.get(event_type, default_event))
        group_ids.append(group_to_id.get(series_group_key(series_id), default_group))
    return (
        np.asarray(series_ids, dtype=np.int64),
        np.asarray(event_ids, dtype=np.int64),
        np.asarray(group_ids, dtype=np.int64),
    )


def checkpoint_target_arrays(
    labels: List[Tuple[str, str]],
    checkpoint: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray]:
    target_stats = checkpoint.get("target_stats")
    if isinstance(target_stats, dict) and target_stats.get("__global__"):
        return target_stat_arrays(labels, target_stats)
    global_stats = {
        "__global__": {
            "mean": float(checkpoint.get("target_mean", 0.0)),
            "std": max(float(checkpoint.get("target_std", 1.0)), 1e-6),
            "samples": 0.0,
        }
    }
    return target_stat_arrays(labels, global_stats)


def scope_key(label: Tuple[str, str]) -> str:
    series_id, event_type = label
    return f"category:{series_group_key(series_id)}:{event_type}"


def candidate_biases(residuals: np.ndarray) -> List[np.ndarray]:
    mean = residuals.mean(axis=0)
    median = np.median(residuals, axis=0)
    return [
        np.zeros_like(mean),
        mean,
        median,
        0.5 * mean + 0.5 * median,
    ]


def fit_bias(residuals: np.ndarray) -> List[float]:
    best_bias = None
    best_score = float("inf")
    zero_true = np.zeros_like(residuals)
    for bias in candidate_biases(residuals):
        adjusted_errors = residuals - bias.reshape(1, -1)
        mae = float(np.mean(np.abs(adjusted_errors)))
        rmse = float(np.sqrt(np.mean(adjusted_errors ** 2)))
        score = mae + 0.15 * rmse
        if score < best_score:
            best_score = score
            best_bias = bias
    assert best_bias is not None
    return [float(value) for value in best_bias.tolist()]


def fit_calibration(
    labels: List[Tuple[str, str]],
    val_idx: np.ndarray,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    min_scope_samples: int,
) -> Dict[str, Any]:
    residuals = np.asarray(y_true, dtype=np.float32) - np.asarray(y_pred, dtype=np.float32)
    val_labels = [labels[int(idx)] for idx in val_idx.tolist()]
    scopes: Dict[str, Dict[str, Any]] = {}

    def add_scope(key: str, positions: List[int]) -> None:
        if len(positions) < min_scope_samples:
            return
        scopes[key] = {
            "bias": fit_bias(residuals[positions]),
            "samples": len(positions),
        }

    add_scope("global:all", list(range(len(val_labels))))
    for event_type in EVENT_TYPES:
        positions = [idx for idx, label in enumerate(val_labels) if label[1] == event_type]
        add_scope(f"global:{event_type}", positions)

    grouped: Dict[str, List[int]] = {}
    grouped_category_all: Dict[str, List[int]] = {}
    for idx, label in enumerate(val_labels):
        key = scope_key(label)
        grouped.setdefault(key, []).append(idx)
        category = f"category:{series_group_key(label[0])}:all"
        grouped_category_all.setdefault(category, []).append(idx)

    for key, positions in grouped.items():
        add_scope(key, positions)
    for key, positions in grouped_category_all.items():
        add_scope(key, positions)

    return {
        "method": "heldout_residual_bias_by_category_event_type",
        "min_scope_samples": int(min_scope_samples),
        "scopes": scopes,
    }


def apply_calibration(
    labels: List[Tuple[str, str]],
    val_idx: np.ndarray,
    y_pred: np.ndarray,
    calibration: Dict[str, Any],
) -> np.ndarray:
    scopes = calibration.get("scopes", {})
    adjusted = np.asarray(y_pred, dtype=np.float32).copy()
    for local_idx, global_idx in enumerate(val_idx.tolist()):
        series_id, event_type = labels[int(global_idx)]
        category = series_group_key(series_id)
        keys = [
            f"category:{category}:{event_type}",
            f"category:{category}:all",
            f"global:{event_type}",
            "global:all",
        ]
        for key in keys:
            scope = scopes.get(key)
            if not scope:
                continue
            bias = np.asarray(scope.get("bias", []), dtype=np.float32)
            if len(bias) >= adjusted.shape[1]:
                adjusted[local_idx] = np.maximum(0.0, adjusted[local_idx] + bias[: adjusted.shape[1]])
                break
    return adjusted


def main() -> None:
    args = parse_args()
    checkpoint_path = resolve_path(args.checkpoint)
    output_path = resolve_path(args.output or args.checkpoint)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    training_args = checkpoint_training_args(checkpoint, args.dataset_cache, args.val_fraction)

    (
        x,
        _y_log,
        y_count,
        labels,
        target_positions,
        baselines,
        total_days,
        _series,
        _dimension_summary,
    ) = build_training_arrays(training_args)
    train_idx, val_idx, split_position = time_based_split(
        target_positions,
        total_days,
        training_args.val_fraction,
    )

    config = checkpoint["config"]
    model = NeuralTransformerHawkesModel(**config)
    model.load_state_dict(checkpoint["model_state"], strict=False)
    device = resolve_device(args.device)
    model.to(device)

    feature_mean = np.asarray(checkpoint["feature_mean"], dtype=np.float32)
    feature_std = np.asarray(checkpoint["feature_std"], dtype=np.float32)
    x_norm = (x - feature_mean) / np.where(feature_std < 1e-6, 1.0, feature_std)
    series_ids, event_type_ids, series_group_ids = ids_from_checkpoint(labels, checkpoint)
    target_mean_values, target_std_values = checkpoint_target_arrays(labels, checkpoint)
    horizons = torch.arange(1, int(training_args.forecast_horizon) + 1, dtype=torch.float32, device=device)

    raw_pred = predict_counts(
        model=model,
        x_norm=x_norm[val_idx],
        series_ids=series_ids[val_idx],
        event_type_ids=event_type_ids[val_idx],
        series_group_ids=series_group_ids[val_idx],
        target_mean_values=target_mean_values[val_idx],
        target_std_values=target_std_values[val_idx],
        batch_size=args.batch_size,
        horizons=horizons,
        device=device,
    )
    calibration = fit_calibration(
        labels=labels,
        val_idx=val_idx,
        y_true=y_count[val_idx],
        y_pred=raw_pred,
        min_scope_samples=args.min_scope_samples,
    )
    calibrated_pred = apply_calibration(labels, val_idx, raw_pred, calibration)

    raw_metrics = regression_metrics(y_count[val_idx], raw_pred)
    calibrated_metrics = regression_metrics(y_count[val_idx], calibrated_pred)
    evaluation = copy.deepcopy(checkpoint.get("metadata", {}).get("evaluation", {}))
    evaluation["raw_neural_thp"] = raw_metrics
    evaluation["neural_thp"] = calibrated_metrics
    evaluation["calibrated_neural_thp"] = calibrated_metrics
    evaluation["baselines"] = {
        name: regression_metrics(y_count[val_idx], values[val_idx])
        for name, values in baselines.items()
    }
    evaluation["per_category"] = evaluate_by_category(
        labels=labels,
        val_idx=val_idx,
        y_true=y_count[val_idx],
        y_pred=calibrated_pred,
    )
    evaluation["per_category_event_type"] = evaluate_by_category_event_type(
        labels=labels,
        val_idx=val_idx,
        y_true=y_count[val_idx],
        y_pred=calibrated_pred,
    )
    evaluation["baseline_improvement"] = baseline_improvement(evaluation)
    evaluation["split_day_index"] = int(split_position)
    evaluation["validation_fraction"] = float(training_args.val_fraction)

    metadata = checkpoint.setdefault("metadata", {})
    metadata["evaluation"] = evaluation
    metadata["forecast_calibration"] = calibration
    metadata["model_version"] = f"{metadata.get('model_version', 'thp')}+calibrated"
    metadata["calibration_summary"] = {
        "raw_mae": raw_metrics["mae"],
        "raw_rmse": raw_metrics["rmse"],
        "calibrated_mae": calibrated_metrics["mae"],
        "calibrated_rmse": calibrated_metrics["rmse"],
        "scope_count": len(calibration.get("scopes", {})),
    }

    if output_path == checkpoint_path:
        backup_path = checkpoint_path.with_suffix(".before_calibration.pt")
        if not backup_path.exists():
            shutil.copyfile(checkpoint_path, backup_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, output_path)
    print(json.dumps(metadata["calibration_summary"], indent=2))
    print(f"saved_checkpoint={output_path}")


if __name__ == "__main__":
    main()
