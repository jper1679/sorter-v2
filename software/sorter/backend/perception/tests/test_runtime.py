from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from perception.runtime import UniversalYoloRuntime
from vision.ml.base import Detection


def test_universal_runtime_detects_engine(tmp_path: Path):
    engine_file = tmp_path / "model.engine"
    engine_file.touch()

    with patch("vision.ml.factory.create_processor") as mock_create:
        mock_proc = MagicMock()
        mock_proc.model_path = engine_file
        mock_proc.imgsz = 320
        mock_proc.conf_threshold = 0.25
        mock_proc.iou_threshold = 0.45
        mock_proc.infer.return_value = [Detection(bbox=(10, 20, 30, 40), score=0.85)]
        mock_create.return_value = mock_proc

        runtime = UniversalYoloRuntime(
            model_path=engine_file,
            imgsz=320,
            conf_threshold=0.25,
        )

        assert runtime.runtime == "tensorrt"
        assert runtime.model_path == engine_file
        mock_create.assert_called_once_with(
            model_path=engine_file,
            model_family="yolo",
            runtime="tensorrt",
            imgsz=320,
            conf_threshold=0.25,
            iou_threshold=0.45,
            rknn_core_mask_name=None,
        )

        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        bboxes = runtime.infer(dummy_img)
        assert bboxes == [(10, 20, 30, 40)]

        scored = runtime.inferWithScores(dummy_img)
        assert scored == [((10, 20, 30, 40), 0.85)]


def test_universal_runtime_prefers_sibling_engine_with_tensorrt(tmp_path: Path):
    onnx_file = tmp_path / "best.onnx"
    onnx_file.touch()
    engine_file = tmp_path / "best.engine"
    engine_file.touch()

    with patch("server.hive_models._has_tensorrt", return_value=True), \
         patch("vision.ml.factory.create_processor") as mock_create:
        mock_proc = MagicMock()
        mock_proc.model_path = engine_file
        mock_proc.imgsz = 320
        mock_proc.conf_threshold = 0.25
        mock_proc.iou_threshold = 0.45
        mock_create.return_value = mock_proc

        runtime = UniversalYoloRuntime(
            model_path=onnx_file,
            imgsz=320,
            conf_threshold=0.25,
        )

        assert runtime.runtime == "tensorrt"
        assert runtime.model_path == engine_file
        mock_create.assert_called_once_with(
            model_path=engine_file,
            model_family="yolo",
            runtime="tensorrt",
            imgsz=320,
            conf_threshold=0.25,
            iou_threshold=0.45,
            rknn_core_mask_name=None,
        )
