#!/usr/bin/env python3
"""Run a GPU hyperparameter sweep for the GDELT THP model.

The script intentionally uses only the current database summaries. It does not
fetch or add older years of data.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import random
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_int_list(value: str) -> List[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_float_list(value: str) -> List[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def parse_bool_list(value: str) -> List[bool]:
    mapping = {"1": True, "true": True, "yes": True, "0": False, "false": False, "no": False}
    result = []
    for item in value.split(","):
        key = item.strip().lower()
        if not key:
            continue
        if key not in mapping:
            raise argparse.ArgumentTypeError(f"Invalid boolean value in list: {item}")
        result.append(mapping[key])
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPU hyperparameter sweep for THP.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--final-output", default="models/thp_gdelt.pt")
    parser.add_argument("--deploy-best", action="store_true")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--early-stopping-patience", type=int, default=8)
    parser.add_argument("--max-trials", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--include-current-baseline", action="store_true", default=True)
    parser.add_argument("--no-current-baseline", action="store_false", dest="include_current_baseline")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cuda")
    parser.add_argument("--amp", action="store_true", default=True)
    parser.add_argument("--no-amp", action="store_false", dest="amp")
    parser.add_argument("--calibrate", action="store_true", default=True)
    parser.add_argument("--no-calibrate", action="store_false", dest="calibrate")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--selection-score", choices=("mae", "rmse", "mae_rmse"), default="mae_rmse")
    parser.add_argument("--rmse-weight", type=float, default=0.05)
    parser.add_argument("--seq-lens", default="14,21,30")
    parser.add_argument("--d-models", default="64,96")
    parser.add_argument("--layers", default="2,3")
    parser.add_argument("--heads", default="4")
    parser.add_argument("--lrs", default="0.001,0.0007")
    parser.add_argument("--batch-sizes", default="1024")
    parser.add_argument("--dropouts", default="0.05,0.1")
    parser.add_argument("--weight-decays", default="0.0001,0.0003")
    parser.add_argument("--target-stat-shrinkages", default="7,14,28")
    parser.add_argument("--top-countries", default="50")
    parser.add_argument("--top-actors", default="50")
    parser.add_argument("--top-country-pairs", default="30")
    parser.add_argument("--top-actor-pairs", default="30")
    parser.add_argument("--top-event-roots", default="20")
    parser.add_argument("--top-event-codes", default="50")
    parser.add_argument("--compile-options", type=parse_bool_list, default=parse_bool_list("false"))
    parser.add_argument("--min-series-events", type=int, default=10)
    parser.add_argument("--forecast-horizon", type=int, default=7)
    return parser.parse_args()


def resolve_path(path_value: str | None, default_name: str) -> Path:
    if path_value:
        path = Path(path_value)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = Path("models") / "thp_sweeps" / f"sweep_{stamp}_{default_name}"
    return path if path.is_absolute() else PROJECT_ROOT / path


def safe_token(value: Any) -> str:
    return str(value).replace(".", "p").replace("-", "m").replace("/", "_")


def build_trials(args: argparse.Namespace) -> List[Dict[str, Any]]:
    raw_grid = itertools.product(
        parse_int_list(args.seq_lens),
        parse_int_list(args.d_models),
        parse_int_list(args.layers),
        parse_int_list(args.heads),
        parse_float_list(args.lrs),
        parse_int_list(args.batch_sizes),
        parse_float_list(args.dropouts),
        parse_float_list(args.weight_decays),
        parse_float_list(args.target_stat_shrinkages),
        parse_int_list(args.top_countries),
        parse_int_list(args.top_actors),
        parse_int_list(args.top_country_pairs),
        parse_int_list(args.top_actor_pairs),
        parse_int_list(args.top_event_roots),
        parse_int_list(args.top_event_codes),
        args.compile_options,
    )
    trials = []
    for (
        seq_len,
        d_model,
        layers,
        heads,
        lr,
        batch_size,
        dropout,
        weight_decay,
        shrinkage,
        top_countries,
        top_actors,
        top_country_pairs,
        top_actor_pairs,
        top_event_roots,
        top_event_codes,
        compile_model,
    ) in raw_grid:
        if d_model % heads != 0:
            continue
        trials.append(
            {
                "seq_len": seq_len,
                "d_model": d_model,
                "layers": layers,
                "heads": heads,
                "lr": lr,
                "batch_size": batch_size,
                "dropout": dropout,
                "weight_decay": weight_decay,
                "target_stat_shrinkage": shrinkage,
                "top_countries": top_countries,
                "top_actors": top_actors,
                "top_country_pairs": top_country_pairs,
                "top_actor_pairs": top_actor_pairs,
                "top_event_roots": top_event_roots,
                "top_event_codes": top_event_codes,
                "compile": compile_model,
            }
        )
    baseline = {
        "seq_len": 14,
        "d_model": 64,
        "layers": 2,
        "heads": 4,
        "lr": 0.001,
        "batch_size": 1024,
        "dropout": 0.1,
        "weight_decay": 0.0001,
        "target_stat_shrinkage": 14.0,
        "top_countries": 50,
        "top_actors": 50,
        "top_country_pairs": 30,
        "top_actor_pairs": 30,
        "top_event_roots": 20,
        "top_event_codes": 50,
        "compile": False,
    }
    if args.include_current_baseline:
        remaining = [trial for trial in trials if trial != baseline]
        random.Random(args.seed).shuffle(remaining)
        trials = [baseline] + remaining
    else:
        random.Random(args.seed).shuffle(trials)
    if args.max_trials > 0:
        trials = trials[: args.max_trials]
    return trials


def run_command(command: List[str], cwd: Path, log_path: Path) -> int:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="")
        return process.wait()


def checkpoint_metrics(checkpoint_path: Path) -> Dict[str, Any]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    metadata = checkpoint.get("metadata", {})
    evaluation = metadata.get("evaluation", {})
    neural = evaluation.get("neural_thp", {})
    baseline = evaluation.get("baselines", {}).get("moving_avg_7", {})
    return {
        "model_version": metadata.get("model_version"),
        "best_epoch": metadata.get("best_epoch"),
        "completed_epochs": metadata.get("completed_epochs"),
        "mae": float(neural.get("mae", float("inf"))),
        "rmse": float(neural.get("rmse", float("inf"))),
        "mape": float(neural.get("mape", float("inf"))),
        "baseline_mae": float(baseline.get("mae", float("inf"))),
        "baseline_rmse": float(baseline.get("rmse", float("inf"))),
        "calibration_summary": metadata.get("calibration_summary"),
    }


def trial_score(record: Dict[str, Any], args: argparse.Namespace) -> float:
    if args.selection_score == "mae":
        return float(record["mae"])
    if args.selection_score == "rmse":
        return float(record["rmse"])
    return float(record["mae"]) + args.rmse_weight * float(record["rmse"])


def write_summaries(output_dir: Path, records: List[Dict[str, Any]], best: Dict[str, Any] | None) -> None:
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "2024_only_gpu_thp_hyperparameter_sweep",
        "best_trial": best,
        "trials": records,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if records:
        fieldnames = sorted({key for record in records for key in record.keys()})
        with (output_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

    lines = ["# THP GPU Sweep Leaderboard", ""]
    ok_records = [record for record in records if record.get("status") == "ok"]
    for record in sorted(ok_records, key=lambda item: item.get("score", float("inf"))):
        lines.append(
            "- trial {trial}: score={score:.3f}, mae={mae:.3f}, rmse={rmse:.3f}, "
            "seq={seq_len}, d={d_model}, layers={layers}, lr={lr}, dropout={dropout}".format(**record)
        )
    if not ok_records:
        lines.append("- No successful trials yet.")
    (output_dir / "leaderboard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def train_trial(args: argparse.Namespace, output_dir: Path, index: int, trial: Dict[str, Any]) -> Dict[str, Any]:
    trial_name = (
        f"trial_{index:02d}_seq{trial['seq_len']}_d{trial['d_model']}_"
        f"l{trial['layers']}_lr{safe_token(trial['lr'])}_do{safe_token(trial['dropout'])}"
    )
    checkpoint_path = output_dir / f"{trial_name}.pt"
    dataset_cache = output_dir / (
        f"dataset_seq{trial['seq_len']}_h{args.forecast_horizon}_"
        f"countries{trial['top_countries']}_actors{trial['top_actors']}_"
        f"cp{trial['top_country_pairs']}_ap{trial['top_actor_pairs']}_"
        f"roots{trial['top_event_roots']}_codes{trial['top_event_codes']}.npz"
    )
    training_log = output_dir / f"{trial_name}.jsonl"
    console_log = output_dir / f"{trial_name}.console.log"
    record: Dict[str, Any] = {"trial": index, "status": "running", **trial}
    if args.resume and checkpoint_path.exists():
        record.update({"status": "ok", "output_path": str(checkpoint_path), **checkpoint_metrics(checkpoint_path)})
        record["score"] = trial_score(record, args)
        return record

    train_cmd = [
        sys.executable,
        "db_scripts/train_thp_model.py",
        "--epochs",
        str(args.epochs),
        "--early-stopping-patience",
        str(args.early_stopping_patience),
        "--seq-len",
        str(trial["seq_len"]),
        "--forecast-horizon",
        str(args.forecast_horizon),
        "--d-model",
        str(trial["d_model"]),
        "--layers",
        str(trial["layers"]),
        "--heads",
        str(trial["heads"]),
        "--lr",
        str(trial["lr"]),
        "--batch-size",
        str(trial["batch_size"]),
        "--dropout",
        str(trial["dropout"]),
        "--weight-decay",
        str(trial["weight_decay"]),
        "--target-normalization",
        "series_event",
        "--target-stat-shrinkage",
        str(trial["target_stat_shrinkage"]),
        "--device",
        args.device,
        "--output",
        str(checkpoint_path),
        "--dataset-cache",
        str(dataset_cache),
        "--training-log",
        str(training_log),
        "--top-countries",
        str(trial["top_countries"]),
        "--top-actors",
        str(trial["top_actors"]),
        "--top-country-pairs",
        str(trial["top_country_pairs"]),
        "--top-actor-pairs",
        str(trial["top_actor_pairs"]),
        "--top-event-roots",
        str(trial["top_event_roots"]),
        "--top-event-codes",
        str(trial["top_event_codes"]),
        "--min-series-events",
        str(args.min_series_events),
    ]
    if args.amp:
        train_cmd.append("--amp")
    if trial["compile"]:
        train_cmd.append("--compile")

    exit_code = run_command(train_cmd, PROJECT_ROOT, console_log)
    if exit_code != 0:
        record.update({"status": "failed", "exit_code": exit_code, "log_path": str(console_log)})
        return record

    if args.calibrate:
        calibrate_cmd = [
            sys.executable,
            "db_scripts/calibrate_thp_checkpoint.py",
            "--checkpoint",
            str(checkpoint_path),
            "--dataset-cache",
            str(dataset_cache),
            "--batch-size",
            "2048",
            "--device",
            args.device,
        ]
        exit_code = run_command(calibrate_cmd, PROJECT_ROOT, console_log)
        if exit_code != 0:
            record.update({"status": "calibration_failed", "exit_code": exit_code, "log_path": str(console_log)})
            return record

    record.update({"status": "ok", "output_path": str(checkpoint_path), "log_path": str(console_log)})
    record.update(checkpoint_metrics(checkpoint_path))
    record["score"] = trial_score(record, args)
    return record


def deploy_best_checkpoint(best: Dict[str, Any], final_output: Path) -> Path:
    source = Path(str(best["output_path"]))
    final_output.parent.mkdir(parents=True, exist_ok=True)
    if final_output.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup = final_output.with_suffix(f".before_sweep_{stamp}.pt")
        shutil.copyfile(final_output, backup)
    shutil.copyfile(source, final_output)
    return final_output


def main() -> None:
    args = parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested, but torch.cuda.is_available() is false.")

    output_dir = resolve_path(args.output_dir, "2024_only")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_output = Path(args.final_output)
    if not final_output.is_absolute():
        final_output = PROJECT_ROOT / final_output

    trials = build_trials(args)
    if not trials:
        raise RuntimeError("No valid trials were generated.")

    config_path = output_dir / "sweep_config.json"
    config_path.write_text(
        json.dumps({"args": vars(args), "trials": trials}, indent=2),
        encoding="utf-8",
    )
    print(f"sweep_output_dir={output_dir}")
    print(f"trial_count={len(trials)}")
    print("data_scope=2024_current_database_only")

    if args.dry_run:
        for index, trial in enumerate(trials, start=1):
            print(f"trial_{index:02d}={json.dumps(trial, sort_keys=True)}")
        return

    records: List[Dict[str, Any]] = []
    best: Dict[str, Any] | None = None
    for index, trial in enumerate(trials, start=1):
        print(f"starting_trial={index}/{len(trials)} config={json.dumps(trial, sort_keys=True)}")
        record = train_trial(args, output_dir, index, trial)
        records.append(record)
        if record.get("status") == "ok" and (best is None or record["score"] < best["score"]):
            best = record
        write_summaries(output_dir, records, best)
        print(f"finished_trial={index} status={record.get('status')} score={record.get('score')}")

    if best and args.deploy_best:
        deployed_path = deploy_best_checkpoint(best, final_output)
        best["deployed_to"] = str(deployed_path)
        write_summaries(output_dir, records, best)
        print(f"deployed_best_checkpoint={deployed_path}")

    if best:
        print(
            "best_trial={trial} score={score:.3f} mae={mae:.3f} rmse={rmse:.3f} "
            "checkpoint={output_path}".format(**best)
        )
    else:
        print("best_trial=None")


if __name__ == "__main__":
    main()
