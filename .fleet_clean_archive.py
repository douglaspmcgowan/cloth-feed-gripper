"""Export the committed PR tip into an isolated temporary verification directory."""
import os
import subprocess
import tarfile
import tempfile
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
revision = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
dest = Path(tempfile.mkdtemp(prefix=f"dog-b40-{revision[:7]}-", dir=Path(os.environ["TEMP"])))
archive = dest / "source.tar"
subprocess.run(["git", "archive", "--format=tar", "-o", str(archive), revision], cwd=root, check=True)
with tarfile.open(archive) as source:
    source.extractall(dest, filter="data")
print(dest)
