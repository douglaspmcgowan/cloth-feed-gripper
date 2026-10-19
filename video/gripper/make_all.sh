#!/bin/sh
# Re-render the gripper hype video from source. Run from anywhere:
#   sh video/gripper/make_all.sh
# Needs: Python 3.13 with bpy==5.1.2, numpy, pillow (see README.md), and ffmpeg on PATH.
# PY selects the interpreter (default: python3). 3D renders on the GPU when Cycles finds one (OptiX, else
# CUDA); GRIPPER_DEVICE=cpu forces the CPU. Frame times and the whole-run time per machine: README.md.
set -e
PY=${PY:-python3}
V=$(cd "$(dirname "$0")" && pwd)
"$PY" "$V/audio/make_audio.py"
"$PY" "$V/graphics/make_graphics.py" all
PY="$PY" sh "$V/src/render_3d.sh"
"$PY" "$V/src/compose.py" --layout both --frames-out "$V/review/frames"
"$PY" "$V/src/deliver.py"
