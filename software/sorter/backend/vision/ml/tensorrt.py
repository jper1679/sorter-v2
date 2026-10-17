"""NVIDIA TensorRT detection processors (Jetson Orin / CUDA).

Loads TensorRT .engine serialized plans, runs inference on the GPU via
TensorRT 10.x execution contexts, and decodes YOLO and NanoDet outputs.
If an ONNX file is passed and no .engine exists yet, it can automatically
compile it via `trtexec` with FP16 precision.
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from .base import (
    BaseProcessor,
    Detection,
    decode_nanodet,
    decode_yolo,
    preprocess_nanodet,
    preprocess_yolo,
)

log = logging.getLogger(__name__)

# Load CUDA runtime via ctypes once
_CUDART: Any = None


def _get_cudart() -> Any:
    global _CUDART
    if _CUDART is None:
        try:
            _CUDART = ctypes.CDLL("libcudart.so")
        except OSError:
            for p in ("/usr/local/cuda/lib64/libcudart.so", "libcudart.so.12", "libcudart.so.11"):
                try:
                    _CUDART = ctypes.CDLL(p)
                    break
                except OSError:
                    pass
        if _CUDART is None:
            raise RuntimeError("libcudart.so not found. Install cuda-cudart or configure LD_LIBRARY_PATH.")
    return _CUDART


def compile_onnx_to_engine(onnx_path: Path, engine_path: Path, *, fp16: bool = True) -> Path:
    """Compile an ONNX model to a TensorRT engine using trtexec."""
    log.info("Compiling %s to TensorRT engine at %s (fp16=%s)...", onnx_path, engine_path, fp16)
    cmd = [
        "trtexec",
        f"--onnx={onnx_path}",
        f"--saveEngine={engine_path}",
    ]
    if fp16:
        cmd.append("--fp16")
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 or not engine_path.exists():
        log.error("trtexec failed (exit code %d):\n%s\n%s", res.returncode, res.stdout[-1000:], res.stderr[-1000:])
        raise RuntimeError(f"Failed to compile {onnx_path} to TensorRT engine")
    log.info("Successfully compiled TensorRT engine: %s", engine_path)
    return engine_path


class _TensorrtEngine:
    """Manages a loaded TensorRT engine and GPU memory buffers."""

    def __init__(self, engine_path: Path) -> None:
        import tensorrt as trt

        self.engine_path = Path(engine_path)
        self.cudart = _get_cudart()
        self.logger = trt.Logger(trt.Logger.WARNING)

        with open(self.engine_path, "rb") as f:
            self.runtime = trt.Runtime(self.logger)
            self.engine = self.runtime.deserialize_cuda_engine(f.read())
        if self.engine is None:
            raise RuntimeError(f"Failed to deserialize TensorRT engine from {self.engine_path}")

        self.context = self.engine.create_execution_context()
        if self.context is None:
            raise RuntimeError("Failed to create TensorRT execution context")

        # Discover I/O tensors
        self.input_name = None
        self.output_name = None
        self.input_shape = None
        self.output_shape = None

        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            mode = self.engine.get_tensor_mode(name)
            shape = tuple(self.engine.get_tensor_shape(name))
            if mode == trt.TensorIOMode.INPUT and self.input_name is None:
                self.input_name = name
                self.input_shape = shape
            elif mode == trt.TensorIOMode.OUTPUT and self.output_name is None:
                self.output_name = name
                self.output_shape = shape

        if not self.input_name or not self.output_name:
            raise RuntimeError(f"Could not resolve input/output tensors for {self.engine_path}")

        self.input_bytes = int(np.prod(self.input_shape) * 4)
        self.output_bytes = int(np.prod(self.output_shape) * 4)

        # Allocate device memory
        self.d_input = ctypes.c_void_p()
        self.d_output = ctypes.c_void_p()
        ret_in = self.cudart.cudaMalloc(ctypes.byref(self.d_input), self.input_bytes)
        ret_out = self.cudart.cudaMalloc(ctypes.byref(self.d_output), self.output_bytes)
        if ret_in != 0 or ret_out != 0:
            raise RuntimeError("Failed to allocate CUDA memory for TensorRT buffers")

        # Create CUDA stream
        self.stream = ctypes.c_void_p()
        self.cudart.cudaStreamCreate(ctypes.byref(self.stream))

        # Set addresses
        self.context.set_tensor_address(self.input_name, self.d_input.value)
        self.context.set_tensor_address(self.output_name, self.d_output.value)

        # Output host buffer pre-allocated
        self.h_output = np.empty(self.output_shape, dtype=np.float32)

    def infer(self, input_blob: np.ndarray) -> np.ndarray:
        """Synchronous inference: copies H2D, executes GPU kernel, copies D2H."""
        if not input_blob.flags["C_CONTIGUOUS"]:
            input_blob = np.ascontiguousarray(input_blob, dtype=np.float32)
        elif input_blob.dtype != np.float32:
            input_blob = input_blob.astype(np.float32)

        # cudaMemcpyHostToDevice = 1
        self.cudart.cudaMemcpyAsync(self.d_input, input_blob.ctypes.data, self.input_bytes, 1, self.stream)
        self.context.execute_async_v3(self.stream.value)
        # cudaMemcpyDeviceToHost = 2
        self.cudart.cudaMemcpyAsync(self.h_output.ctypes.data, self.d_output, self.output_bytes, 2, self.stream)
        self.cudart.cudaStreamSynchronize(self.stream)
        return self.h_output

    def close(self) -> None:
        if getattr(self, "stream", None) and self.stream.value:
            self.cudart.cudaStreamDestroy(self.stream)
            self.stream = ctypes.c_void_p()
        if getattr(self, "d_input", None) and self.d_input.value:
            self.cudart.cudaFree(self.d_input)
            self.d_input = ctypes.c_void_p()
        if getattr(self, "d_output", None) and self.d_output.value:
            self.cudart.cudaFree(self.d_output)
            self.d_output = ctypes.c_void_p()

    def __del__(self) -> None:
        self.close()


class _TensorrtMixin:
    model_path: Path
    _lock: Any
    _engine: _TensorrtEngine | None = None
    _load_failed: bool = False

    def _ensure_engine(self) -> _TensorrtEngine:
        with self._lock:
            if self._load_failed:
                raise RuntimeError(f"TensorRT model load permanently failed: {self.model_path}")
            if self._engine is None:
                target_engine = self.model_path
                if self.model_path.suffix.lower() == ".onnx":
                    target_engine = self.model_path.with_suffix(".engine")
                    if not target_engine.exists():
                        compile_onnx_to_engine(self.model_path, target_engine, fp16=True)
                log.info("Loading TensorRT engine from %s", target_engine)
                try:
                    self._engine = _TensorrtEngine(target_engine)
                except Exception:
                    self._load_failed = True
                    raise
            return self._engine


class TensorrtYoloProcessor(_TensorrtMixin, BaseProcessor):
    family = "yolo"
    runtime = "tensorrt"

    def infer(
        self,
        image_bgr: np.ndarray,
        *,
        conf_threshold: float | None = None,
    ) -> list[Detection]:
        engine = self._ensure_engine()
        blob, pre = preprocess_yolo(image_bgr, self.imgsz)
        output = engine.infer(blob)
        return decode_yolo(
            output[0],
            pre=pre,
            conf_threshold=(
                float(conf_threshold)
                if conf_threshold is not None
                else self.conf_threshold
            ),
            iou_threshold=self.iou_threshold,
        )


class TensorrtNanodetProcessor(_TensorrtMixin, BaseProcessor):
    family = "nanodet"
    runtime = "tensorrt"

    def __init__(
        self,
        model_path: Path,
        *,
        imgsz: int,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        reg_max: int = 7,
        strides: tuple[int, ...] = (8, 16, 32, 64),
    ) -> None:
        super().__init__(
            model_path,
            imgsz=imgsz,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
        )
        self.reg_max = int(reg_max)
        self.strides = tuple(int(s) for s in strides)

    def infer(
        self,
        image_bgr: np.ndarray,
        *,
        conf_threshold: float | None = None,
    ) -> list[Detection]:
        engine = self._ensure_engine()
        blob, pre = preprocess_nanodet(image_bgr, self.imgsz)
        output = engine.infer(blob)
        return decode_nanodet(
            output[0],
            pre=pre,
            conf_threshold=(
                float(conf_threshold)
                if conf_threshold is not None
                else self.conf_threshold
            ),
            iou_threshold=self.iou_threshold,
            reg_max=self.reg_max,
            strides=self.strides,
        )
