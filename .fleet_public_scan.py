"""Print any private path, email, or credential-shaped addition in the PR diff."""
import re
import subprocess
import sys

patterns = [
    (re.compile(r"C:[/\\]Users", re.I), ("C:", "c:")),
    (re.compile(r"/home/", re.I), ("/home/", "/Home/")),
    (re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I), ("@",)),
    (re.compile(r"(?:ghp_|github_pat_|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9]{20,})"),
     ("ghp_", "github_pat_", "AKIA", "sk-")),
]
result = subprocess.run(["git", "diff", "--unified=0", "origin/main...HEAD"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
if result.returncode:
    print(result.stderr, file=sys.stderr)
    raise SystemExit(result.returncode)
def suspicious(line):
    for pattern, needles in patterns:
        for needle in needles:
            start = 0
            while (at := line.find(needle, start)) >= 0:
                if pattern.search(line[max(0, at - 256):at + 512]):
                    return True
                start = at + len(needle)
    return False

hits = [line for line in result.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++") and suspicious(line)]
for hit in hits:
    print(hit)
raise SystemExit(bool(hits))
