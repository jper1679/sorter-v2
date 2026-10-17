"""Tests for TensorRT processor integration."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from server.hive_models import compatible_runtimes_for_this_machine
from vision.ml.factory import create_processor, resolve_variant_artifact


def test_tensorrt_in_compatible_runtimes(monkeypatch):
    monkeypatch.setattr("server.hive_models._has_tensorrt", lambda: True)
    monkeypatch.setattr("server.hive_models._has_hailo", lambda: False)
    monkeypatch.setattr("server.hive_models._has_rknn_npu", lambda: False)
    runtimes = compatible_runtimes_for_this_machine()
    assert runtimes[0] == "tensorrt"


def test_tensorrt_not_in_runtimes_when_absent(monkeypatch):
    monkeypatch.setattr("server.hive_models._has_tensorrt", lambda: False)
    monkeypatch.setattr("server.hive_models._has_hailo", lambda: False)
    monkeypatch.setattr("server.hive_models._has_rknn_npu", lambda: False)
    runtimes = compatible_runtimes_for_this_machine()
    assert "tensorrt" not in runtimes


def test_tensorrt_live_inference_if_engine_exists():
    engine_path = Path("/tmp/test_yolo11s.engine")
    if not engine_path.exists():
        pytest.skip("Test engine /tmp/test_yolo11s.engine does not exist")

    from vision.ml.tensorrt import TensorrtYoloProcessor

    processor = TensorrtYoloProcessor(
        model_path=engine_path,
        imgsz=320,
        conf_threshold=0.25,
        iou_threshold=0.45,
    )
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = processor.infer(fake_frame)
    assert isinstance(detections, list)
