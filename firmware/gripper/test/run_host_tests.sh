#!/bin/sh
# Build and run the host FSM test with g++ (no Arduino core). Run from anywhere.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$DIR/.."
OUT="${TMPDIR:-/tmp}/gripper_test_fsm"
g++ -std=c++17 -O1 -Wall -Wextra -Werror -I"$SRC" -o "$OUT" \
  "$DIR/test_fsm.cpp" "$SRC/fsm.cpp" "$SRC/force_ctrl.cpp" "$SRC/motion.cpp" "$SRC/events.cpp" "$SRC/protocol.cpp" "$SRC/fsr_filter.cpp" -lm
"$OUT" "$@"
