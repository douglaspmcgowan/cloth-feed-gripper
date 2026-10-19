# Moved from berkeley-ai-tutor

Source: `douglaspmcgowan/berkeley-ai-tutor` at `1d7cff460da4783e492abb3a937cc25168eebb48`.
The 1,294 moved files retain their source bytes except for these seven public-safety edits:

- `ecad/gripper/build.py`: derive the KiCad bin directory from LOCALAPPDATA.
- `ecad/gripper/kicad/gen/gen_sch.py`: derive the KiCad symbol directory from LOCALAPPDATA.
- `ecad/gripper/kicad/gen/inspect_sym.py`: derive the KiCad symbol directory from LOCALAPPDATA.
- `video/gripper/README.md`: use a portable virtual environment placeholder.
- `video/gripper/REVIEW.md`: name the extracted review frame without its temporary directory.
- `analysis/gripper/finger_beam.py`: record the parameter file as a repository-relative path while loading it from the destination root.
- `analysis/gripper/results/finger_beam.json`: replace the source machine's absolute parameter path with `cad/gripper/params.json`; computed results are unchanged.

Held back: `docs/gripper/process/program-loop.md` remains in the source repository as a private conductor process file in use.

`SYSTEMATICCHAOS` in `video/gripper/STORYBOARD.md` and `video/gripper/README.md` names the laptop used to time the renders. It is hardware provenance, not a network-reachable host, and remains in the moved record.

`docs/gripper/process/build_log_app.html` and `docs/gripper/process/build_timeline.html` remain in the move as project process records. Their links to the private source repository return 404 to public visitors; the links do not expose that repository's contents.
