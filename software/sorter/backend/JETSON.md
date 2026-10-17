# NVIDIA Jetson Support Roadmap & Architecture Notes

This document records the architectural decisions, platform specifics, and roadmap for running the LEGO Sorter software stack on NVIDIA Jetson hardware, specifically targeting the **NVIDIA Jetson Orin Nano Super**.

---

## 1. Target Hardware & Platform Baseline

- **Hardware:** NVIDIA Jetson Orin Nano Super
- **Compute Architecture:** NVIDIA Ampere architecture GPU with Tensor Cores (~40-45+ TOPS INT8), ARM Cortex-A78AE CPU
- **Operating System:** NVIDIA JetPack 7.2.1 with Jetson Linux (L4T) 39.2.1
- **Connectivity:** USB-C (power/data/flashing) & Ethernet (local network: e.g. `192.168.2.136`)
- **Peripherals:**
  - Microcontrollers: Raspberry Pi Pico (Feeder & Distribution boards) via USB CDC serial
  - Cameras: USB UVC / V4L2 webcams for feeder, classification channels, carousel

---

## 2. Strategic Decisions

### 2.1 OS & Deployment Strategy (Phase 1 vs Future)
- **Current Scope (Phase 1):** No custom SorterOS image build for now.
  Run the Sorter software directly on top of the official NVIDIA JetPack (Ubuntu) installation.
  - Backend (Python / FastAPI / asyncio)
  - Frontend (Svelte / SvelteKit dev/preview server or built static files)
- **Future Scope (Phase 2+):** A dedicated custom OS image / appliance (similar to SorterOS for Orange Pi with captive-portal firstboot Wi-Fi setup) may be considered later once hardware operation is validated.

### 2.2 Machine Learning & Vision Inference Strategy
- **Long-term Preferred Target:** **Native TensorRT engine (`.engine`) runtime**.
  - Direct execution via TensorRT Python API or C++ runtime bindings.
  - Maximum throughput and lowest latency leveraging Jetson Ampere Tensor Cores and FP16/INT8 precision.
- **Initial Pragmatic Step:** **Bring up the machine first with ONNX Runtime**.
  - Validate mechanical actions, serial communication with Picos, multi-camera capture, and UI state machines.
  - Run inference with ONNX models (`best.onnx`) via CPU or `CUDAExecutionProvider` / `TensorrtExecutionProvider` in `onnxruntime`.
  - Once end-to-end functionality is confirmed, introduce the dedicated TensorRT processor and engine exporter in `software/sorter/backend/vision/ml/` and `software/training/`.

---

## 3. Milestones & Checklist

- [x] **Step 1: Jetson Environment Preparation**
  - Verify Python environment (uv / Python 3.12+), Node.js, and pnpm on the Jetson.
  - Validate udev permissions for Raspberry Pi Pico boards (`99-sorter-pico.rules`).
  - Verify USB camera access (`v4l2-ctl --list-devices`).
  - Configure 8GB swapfile for Jetson 8GB unified memory.

- [x] **Step 2: Basic Backend & Frontend Bring-up**
  - Run `./install.sh --as-service` on the Jetson.
  - Clone/checkout branch `feat/jetson-orin-nano`.
  - Service `sorter-backend-dev.service` running under systemd on port 80 (UI) and port 8000 (API).
  - Web UI and REST API accessible from LAN (`http://192.168.2.136`).

- [x] **Step 3: Hardware Verification**
  - Connected Pico board identified on `/dev/ttyACM0` (`DISTRIBUTION MB` with firmware `v0.8.1`).
  - Connected USB cameras identified (1x Innomaker 4K `/dev/video0`, 2x Realtek `/dev/video2`, `/dev/video4`).
  - Live frame capture validated in OpenCV and perception service.

- [x] **Step 3.5: TensorRT Setup**
  - Installed `nvidia-tensorrt` 10.16.2.10 and `libnvinfer-bin` (`trtexec`).
  - Linked Python `tensorrt` 10.16.2.10 into backend virtual environment (`system-dist-packages.pth`).

- [x] **Step 5: Native TensorRT Integration (Target Performance)**
  - Added `TensorrtYoloProcessor` and `TensorrtNanodetProcessor` in `software/sorter/backend/vision/ml/tensorrt.py`.
  - Registered `"tensorrt"` runtime in `vision/detection_registry.py` and `server/hive_models.py`.
  - Implemented automatic runtime discovery: Jetson GPU detects `tensorrt` as #1 priority runtime.
  - Converted YOLO11s (320x320) model from `best.onnx` to `best.engine` with FP16 precision.
  - **Benchmark on Jetson Orin Nano Super:**
    - Throughput: **263.3 FPS** (qps)
    - GPU Latency: **3.79 ms** (mean total latency: 3.92 ms)
    - Unit tests: 57/57 tests passed (including live GPU engine inference).
