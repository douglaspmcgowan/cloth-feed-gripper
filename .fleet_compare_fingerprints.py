import json
from pathlib import Path

old = json.loads(Path('analysis/gripper/tolstack/tests/loop_fingerprints.json').read_text(encoding='utf-8'))
new = json.loads(Path('C:/Users/dougl/AppData/Local/Temp/pw/pt-dog-b40-2/fingerprints-new.json').read_text(encoding='utf-8'))
for revision, stacks in new.items():
    for stack, contributors in stacks.items():
        before = {row['name']: row for row in old.get(revision, {}).get(stack, [])}
        for row in contributors:
            previous = before.get(row['name'])
            if previous != row:
                print(f'{revision} {stack} {row["name"]}: {previous} -> {row}')
