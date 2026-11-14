"""Tests for the CPU / graphics-card choice (app/compute.py), no AI models needed."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # dist_utils

from app import compute


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """Use a temp user folder and fixed hardware facts."""
    import dist_utils
    monkeypatch.setattr(dist_utils, "get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(compute, "gpu_names", lambda: ["Test GPU"])
    monkeypatch.setattr(compute, "ort_version", lambda: "9.9.9")
    monkeypatch.setattr(compute, "_worker_count", lambda: 4)
    monkeypatch.delenv("COMPUTE_DEVICE", raising=False)


def test_setting_parsing(monkeypatch):
    assert compute.requested_device() == "auto"
    for value, expected in [("CPU", "cpu"), (" gpu ", "gpu"), ("turbo", "auto")]:
        monkeypatch.setenv("COMPUTE_DEVICE", value)
        assert compute.requested_device() == expected


def test_cpu_setting_never_uses_gpu(monkeypatch):
    monkeypatch.setenv("COMPUTE_DEVICE", "cpu")
    monkeypatch.setattr(compute, "dml_available", lambda: True)
    plan = compute.get_plan()
    assert plan.device == "cpu" and plan.providers == [compute.CPU]
    assert plan.intra_op_threads >= 1 and not plan.shared_analyzer


def test_gpu_setting_uses_directml_with_shared_analyzer(monkeypatch):
    monkeypatch.setenv("COMPUTE_DEVICE", "gpu")
    monkeypatch.setattr(compute, "dml_available", lambda: True)
    plan = compute.get_plan()
    assert plan.device == "gpu" and plan.providers[0] == compute.DML
    # Separate DirectML sessions per thread crashed the process in testing
    assert plan.shared_analyzer


def test_no_directml_means_cpu_even_if_gpu_requested(monkeypatch):
    monkeypatch.setenv("COMPUTE_DEVICE", "gpu")
    monkeypatch.setattr(compute, "dml_available", lambda: False)
    assert compute.get_plan().device == "cpu"


def test_auto_uses_cached_speed_test(monkeypatch):
    monkeypatch.setattr(compute, "dml_available", lambda: True)
    for device in ("gpu", "cpu"):
        compute.save_choice(compute.ComputeChoice(device=device, gpu_name="Test GPU", gpus=["Test GPU"],
                                                  ort_version="9.9.9", gpu_ms=200, cpu_ms=900))
        assert compute.get_plan().device == device


def test_cached_choice_is_redone_when_hardware_changes(monkeypatch):
    compute.save_choice(compute.ComputeChoice(device="gpu", gpu_name="Old GPU", gpus=["Old GPU"],
                                              ort_version="9.9.9"))
    assert not compute.choice_is_current(compute.load_choice())
    # Without permission to run the test, auto falls back to the processor
    monkeypatch.setattr(compute, "dml_available", lambda: True)
    assert compute.get_plan(run_test_if_needed=False).device == "cpu"


def test_failed_speed_test_falls_back_to_cpu(monkeypatch):
    import subprocess

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="bench", timeout=1)
    monkeypatch.setattr(compute.subprocess, "run", boom)
    choice = compute.benchmark_in_subprocess()
    assert choice.device == "cpu" and "timed out" in choice.note
    assert compute.choice_is_current(compute.load_choice())
