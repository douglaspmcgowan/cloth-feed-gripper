#!/bin/sh
# Render every 3D shot at production settings into video/gripper/build/frames3d/<shot>/.
# Resumable: frames already written are skipped, so rerunning after an interruption continues.
# Native 1920 x 1080 (the vertical cut crops a 1080 square from it 1:1), plus S10_plate: S2 frame 149 at
# 3413 x 1920, the scale the vertical cut's blurred plate needs. Settings chosen by measurement: README.md.
#   GPU (default; OptiX, else CUDA, else CPU):  sh src/render_3d.sh
#   CPU only:                                    GRIPPER_DEVICE=cpu sh src/render_3d.sh
set -e
PY=${PY:-python}
HERE=$(dirname "$0")
SPP=${SPP:-64}
Q="--samples $SPP --denoise high --mblur --threshold 0.01"
for s in ${SHOTS:-S2 S1 S3 S4 S5 S6 S9 S11 S10_plate}; do
  if [ "$s" = S10_plate ]; then
    "$PY" "$HERE/shots3d.py" S2 --frame 149 --name S10_plate --w 3413 --h 1920 $Q "$@"
  else
    "$PY" "$HERE/shots3d.py" "$s" --w 1920 --h 1080 $Q "$@"
  fi
done
