#!/usr/bin/env python3
"""Refresh the review app, films and figures from this repository's pinned commit.

    python scripts/sync.py --ref HEAD

Reads blobs at <ref> with `git show` (never the clone's working tree, never writes to it) and writes:

    public/review/index.html     the review app inside a document wrapper
    public/media/*               the three films (moov first), posters, social image
    public/licenses/*            licence texts the credits point to
    public/facts.json            every figure the landing page shows, read out of the review app
    public/provenance.json       source repository name, pinned commit, sync date, and for each served
                                 file its public path, sha256 and byte count; nothing about the source layout
    .sync/state.json             git-ignored, never served: the full record (source paths, input hashes,
                                 recipes) that lets a second run skip unchanged work

Running it twice with the same ref changes nothing: files are written only when their bytes differ,
and a derived media file is rebuilt only when its input, its recipe or its recorded hash changed.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
SOURCE_SLUG = "douglaspmcgowan/cloth-feed-gripper"
SOURCE_URL = f"https://github.com/{SOURCE_SLUG}"

VIEWER = "cad/gripper/viewer.html"
VERTICAL = "video/gripper/renders/gripper_hype_vertical.mp4"
FILMS = {
    "video/gripper/renders/gripper_hype_1080p.mp4": "gripper_hype_1080p.mp4",
    VERTICAL: "gripper_hype_vertical.mp4",
    "video/gripper/renders/teaser_10s.mp4": "teaser_10s.mp4",
}
POSTER = "video/gripper/renders/poster.png"
LICENCES = {
    "docs/gripper/licenses/so101-apache-2.0.txt": "so101-apache-2.0.txt",
    "video/gripper/assets/fonts/OFL.txt": "archivo-ofl.txt",
}
# Read for checks and credits, never served.
READ_ONLY = [
    "docs/gripper/DESIGN-BASIS.md",
    "cad/gripper/viewer_src/so101_mesh.py",
    "video/gripper/CREDITS.md",
    "video/gripper/audio/README.md",
]
REQUIRED = [VIEWER, POSTER, *FILMS, *LICENCES, *READ_ONLY]

PUBLIC_REVIEW = PUBLIC / "review" / "index.html"
MEDIA = PUBLIC / "media"
SITE_CONFIG = ROOT / "site.config.json"
# The full record of what was read and how it was built. Outside public/ and git-ignored: it names
# source-side paths, which the served provenance.json must not.
STATE = ROOT / ".sync" / "state.json"


def source_inputs() -> list[str]:
    """Every source-repository path this script reads; check_public.py searches served files for them."""
    return [VIEWER, VERTICAL, *FILMS, POSTER, *LICENCES, *READ_ONLY]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, check=check)


def git(clone: Path, *args: str) -> bytes:
    return run(["git", "-C", str(clone), *args]).stdout


def write_if_changed(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


# ---------------------------------------------------------------------------- source


def acquire(source: str | None) -> tuple[Path, Path | None]:
    """Return the local repository, or an explicitly supplied clone."""
    if source:
        clone = Path(source).resolve()
        if not (clone / ".git").exists() and not (clone / "HEAD").exists():
            sys.exit(f"--source {clone} is not a git clone")
        return clone, None
    return ROOT, None


def resolve(clone: Path, ref: str) -> tuple[str, str]:
    done = run(["git", "-C", str(clone), "rev-parse", "--verify", f"{ref}^{{commit}}"], check=False)
    if done.returncode != 0:
        sys.exit(f"ref {ref} not found in {clone}")
    full = done.stdout.decode().strip()
    date = git(clone, "show", "-s", "--format=%cI", full).decode().strip()
    return full, date


def check_inputs(clone: Path, full: str) -> None:
    missing = [p for p in REQUIRED if run(["git", "-C", str(clone), "cat-file", "-e", f"{full}:{p}"], check=False).returncode != 0]
    if missing:
        sys.exit("missing at the pinned commit:\n  " + "\n  ".join(missing))


def blob(clone: Path, full: str, path: str) -> bytes:
    return git(clone, "show", f"{full}:{path}")


# ---------------------------------------------------------------------------- review app


def site_url() -> str:
    return json.loads(SITE_CONFIG.read_text(encoding="utf-8"))["siteUrl"].rstrip("/")


# The review app was written for the Artifact viewer, which supplies a small host reset. The app's own
# stylesheet already carries the [hidden] rule of that reset, so it is not repeated here.
WRAPPER_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Interactive design review of the cloth-feed gripper: 3D model, fit checks, assembly, analysis and the decisions still open. An unbuilt design for the SO-101 arm.">
<link rel="canonical" href="{url}/review/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Cloth-feed gripper">
<meta property="og:title" content="Cloth-feed gripper design review">
<meta property="og:description" content="Orbit the 3D model, check the fits, follow the assembly and read what is still open. An unbuilt design.">
<meta property="og:url" content="{url}/review/">
<meta property="og:image" content="{url}/media/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Cloth-feed gripper design review">
<meta name="twitter:description" content="Orbit the 3D model, check the fits, follow the assembly and read what is still open. An unbuilt design.">
<meta name="twitter:image" content="{url}/media/og.jpg">
<meta name="theme-color" content="#edf0f3" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0d1217" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
:root{{color-scheme:light;padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)}}
body{{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}}
img{{max-width:100%}}
#rail .homelink{{flex:none;display:inline-flex;align-items:center;min-height:var(--tap);padding:0 var(--s3);border-radius:var(--r1);font-size:var(--fs-s);font-weight:600;color:var(--accent);text-decoration:none}}
#rail .homelink:hover{{background:var(--accent-soft)}}
</style>
"""

# Runs after the app's own scripts so the rail exists. It adds one link and touches nothing else.
HOME_LINK = """<script>
(function () {
  var top = document.querySelector("#rail .rail-top");
  if (!top || top.querySelector(".homelink")) return;
  var a = document.createElement("a");
  a.className = "homelink";
  a.href = "/";
  a.textContent = "Home";
  a.setAttribute("aria-label", "Project home page");
  var brand = top.querySelector(".brand");
  top.insertBefore(a, brand ? brand.nextSibling : top.firstChild);
})();
</script>
</html>
"""


def wrap_viewer(viewer: bytes, url: str) -> bytes:
    text = viewer.decode("utf-8")
    source_metadata = '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
    if text.startswith(source_metadata + "<title>"):
        text = text[len(source_metadata) :]
    elif not text.startswith("<title>"):
        sys.exit("review app has an unsupported start structure; the wrapper needs updating")
    if not text.endswith("\n"):
        text += "\n"
    return (WRAPPER_HEAD.format(url=url) + text + HOME_LINK).encode("utf-8")


# ---------------------------------------------------------------------------- media


def moov_first(data: bytes) -> bool:
    """True when the moov box comes before mdat among the top-level MP4 boxes."""
    pos, seen_mdat = 0, False
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        if kind == b"moov":
            return not seen_mdat
        if kind == b"mdat":
            seen_mdat = True
        if size == 1:
            size = int.from_bytes(data[pos + 8 : pos + 16], "big")
        elif size == 0:
            break
        pos += size
    return False


def ffmpeg(*args: str) -> None:
    exe = shutil.which("ffmpeg")
    if not exe:
        sys.exit("ffmpeg is required to prepare the media and was not found on PATH")
    done = run([exe, "-hide_banner", "-loglevel", "error", "-y", *args], check=False)
    if done.returncode != 0:
        sys.exit("ffmpeg failed: " + done.stderr.decode(errors="replace").strip())


def previous(prov: dict | None, out_rel: str) -> dict | None:
    for f in (prov or {}).get("files", []):
        if f.get("output") == out_rel:
            return f
    return None


def derive(out: Path, recipe: str, in_sha: str, prov: dict | None, build) -> tuple[bool, str]:
    """Build `out` with build(tmp_path) unless the recorded input, recipe and output hash all match."""
    rel = out.relative_to(ROOT).as_posix()
    prev = previous(prov, rel)
    if prev and out.exists() and prev.get("recipe") == recipe and prev.get("sha256") == in_sha and sha256(out.read_bytes()) == prev.get("output_sha256"):
        return False, prev["output_sha256"]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name("tmp-" + out.name)
    try:
        build(tmp)
        data = tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)
    changed = write_if_changed(out, data)
    return changed, sha256(data)


def encode_search(dst: Path, qualities: tuple[int, ...], limit: int, make) -> None:
    """Run make(quality) until the file at dst is under `limit` bytes."""
    for q in qualities:
        make(q)
        if dst.stat().st_size < limit:
            return
    sys.exit(f"could not get {dst.name} under {limit} bytes")


# ---------------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", help="commit in this repository to read (default: HEAD)")
    ap.add_argument("--source", help="path to an existing clone; defaults to this repository")
    args = ap.parse_args()

    prov_path = PUBLIC / "provenance.json"
    served_prev = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.exists() else None
    prov = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None
    ref = args.ref or "HEAD"

    clone, tmp = acquire(args.source)
    try:
        full, committed = resolve(clone, ref)
        check_inputs(clone, full)
        url = site_url()
        changed: list[str] = []
        files: list[dict] = []

        def note(path: Path, did: bool) -> None:
            if did:
                changed.append(path.relative_to(ROOT).as_posix())

        def record(src: str, src_bytes: bytes, out: Path, out_sha: str, recipe: str) -> None:
            files.append(
                {"path": src, "role": "served", "sha256": sha256(src_bytes), "bytes": len(src_bytes), "output": out.relative_to(ROOT).as_posix(),
                 "output_sha256": out_sha, "output_bytes": out.stat().st_size, "recipe": recipe}
            )

        # review app
        viewer = blob(clone, full, VIEWER)
        wrapped = wrap_viewer(viewer, url)
        note(PUBLIC_REVIEW, write_if_changed(PUBLIC_REVIEW, wrapped))
        record(VIEWER, viewer, PUBLIC_REVIEW, sha256(wrapped), "document wrapper and one home link; viewer content unchanged")

        # figures, read out of the review app by its own code
        scratch = Path(tempfile.mkdtemp(prefix="gripper-viewer-"))
        try:
            (scratch / "viewer.html").write_bytes(viewer)
            done = run(["node", str(ROOT / "scripts" / "extract_facts.mjs"), str(scratch / "viewer.html")], check=False)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        if done.returncode != 0:
            sys.exit("extract_facts.mjs failed: " + done.stderr.decode(errors="replace").strip())
        facts = json.loads(done.stdout)
        basis = blob(clone, full, "docs/gripper/DESIGN-BASIS.md").decode("utf-8")
        n_basis = len(re.findall(r"^\| R\d+ \|", basis, flags=re.M))
        if n_basis != facts["requirements"]["total"]:
            sys.exit(f"DESIGN-BASIS.md lists {n_basis} requirements but the review app tracks {facts['requirements']['total']}; the viewer is stale against the basis")
        facts["requirements"]["design_basis_total"] = n_basis
        facts["source"] = {"repository": SOURCE_URL, "commit": full, "committed": committed}
        note(PUBLIC / "facts.json", write_if_changed(PUBLIC / "facts.json", (json.dumps(facts, indent=2, ensure_ascii=False) + "\n").encode("utf-8")))

        # design tokens: the review app's own :root blocks, so the landing page cannot drift from them
        text = viewer.decode("utf-8")
        t0, t1 = text.find(":root{"), text.find("*{box-sizing")
        if t0 < 0 or t1 < t0:
            sys.exit("review app token block (:root{ .. *{box-sizing) not found; extraction needs updating")
        tokens = "/* Generated by scripts/sync.py from the review app's :root blocks. Do not edit. */\n" + text[t0:t1].rstrip() + "\n"
        note(PUBLIC / "tokens.css", write_if_changed(PUBLIC / "tokens.css", tokens.encode("utf-8")))
        files.append({"path": VIEWER, "role": "served", "sha256": sha256(viewer), "bytes": len(viewer), "output": "public/tokens.css",
                      "output_sha256": sha256(tokens.encode("utf-8")), "output_bytes": len(tokens.encode("utf-8")), "recipe": "the :root token blocks of the review app, verbatim"})

        # licence texts
        for src, name in LICENCES.items():
            data = blob(clone, full, src)
            out = PUBLIC / "licenses" / name
            note(out, write_if_changed(out, data))
            record(src, data, out, sha256(data), "copied")

        # films: stream copy with the moov atom first; copied as-is when it already is
        for src, name in FILMS.items():
            data = blob(clone, full, src)
            out = MEDIA / name
            first = moov_first(data)
            recipe = "copied (moov already first)" if first else "ffmpeg -c copy -movflags +faststart"

            def build(dst: Path, data=data, first=first) -> None:
                if first:
                    dst.write_bytes(data)
                    return
                srcp = dst.with_suffix(".src.mp4")
                srcp.write_bytes(data)
                try:
                    ffmpeg("-i", str(srcp), "-c", "copy", "-map_metadata", "0", "-movflags", "+faststart", "-fflags", "+bitexact", str(dst))
                finally:
                    srcp.unlink(missing_ok=True)

            did, out_sha = derive(out, recipe, sha256(data), prov, build)
            note(out, did)
            if not moov_first(out.read_bytes()):
                sys.exit(f"{out} still has its moov atom after the mdat")
            record(src, data, out, out_sha, recipe)

        # posters and social image
        poster = blob(clone, full, POSTER)
        vertical = blob(clone, full, VERTICAL)

        def poster_build(dst: Path) -> None:
            png = dst.with_suffix(".src.png")
            png.write_bytes(poster)
            try:
                encode_search(dst, (82, 74, 66, 58, 50), 240_000, lambda q: ffmpeg("-i", str(png), "-vf", "scale=1280:-2:flags=lanczos", "-c:v", "libwebp", "-quality", str(q), "-frames:v", "1", "-f", "webp", str(dst)))
            finally:
                png.unlink(missing_ok=True)

        def og_build(dst: Path) -> None:
            png = dst.with_suffix(".src.png")
            png.write_bytes(poster)
            try:
                encode_search(dst, (3, 5, 7, 9), 240_000, lambda q: ffmpeg("-i", str(png), "-vf", "scale=1200:630:force_original_aspect_ratio=increase:flags=lanczos,crop=1200:630", "-q:v", str(q), "-frames:v", "1", "-c:v", "mjpeg", "-f", "image2", str(dst)))
            finally:
                png.unlink(missing_ok=True)

        def vposter_build(dst: Path) -> None:
            mp4 = dst.with_suffix(".src.mp4")
            mp4.write_bytes(vertical)
            try:
                encode_search(dst, (80, 70, 60, 50), 240_000, lambda q: ffmpeg("-ss", "8.5", "-i", str(mp4), "-vf", "scale=720:-2:flags=lanczos", "-c:v", "libwebp", "-quality", str(q), "-frames:v", "1", "-f", "webp", str(dst)))
            finally:
                mp4.unlink(missing_ok=True)

        for out, src_bytes, src_path, recipe, build in (
            (MEDIA / "poster.webp", poster, POSTER, "ffmpeg scale 1280 wide, libwebp quality search under 240 KB", poster_build),
            (MEDIA / "og.jpg", poster, POSTER, "ffmpeg cover-crop 1200x630, mjpeg quality search under 240 KB", og_build),
            (MEDIA / "poster_vertical.webp", vertical, VERTICAL, "ffmpeg frame at 8.5 s, 720 wide, libwebp quality search under 240 KB", vposter_build),
        ):
            did, out_sha = derive(out, recipe, sha256(src_bytes), prov, build)
            note(out, did)
            record(src_path, src_bytes, out, out_sha, recipe)

        # read-only inputs
        for src in READ_ONLY:
            data = blob(clone, full, src)
            files.append({"path": src, "role": "read, not served", "sha256": sha256(data), "bytes": len(data)})

        files.sort(key=lambda f: (f["role"] != "served", f["path"], f.get("output", "")))
        state = {"source": {"repository": SOURCE_URL, "commit": full, "committed": committed}, "files": files}
        write_if_changed(STATE, (json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

        # Served record: public path, hash and size of each served file, plus the repository name,
        # the pinned commit and the sync date. The date is kept while nothing else changed.
        served = sorted(
            ({"path": Path(f["output"]).relative_to("public").as_posix(), "sha256": f["output_sha256"], "bytes": f["output_bytes"]} for f in files if f["role"] == "served"),
            key=lambda f: f["path"],
        )
        same = served_prev and served_prev.get("source", {}).get("commit") == full and served_prev.get("files") == served
        synced = served_prev["source"]["synced"] if same and "synced" in served_prev["source"] else datetime.date.today().isoformat()
        provenance = {"source": {"repository": SOURCE_URL, "commit": full, "synced": synced}, "files": served}
        note(prov_path, write_if_changed(prov_path, (json.dumps(provenance, indent=2, ensure_ascii=False) + "\n").encode("utf-8")))

        print(f"source {SOURCE_URL} @ {full} ({committed})")
        print(f"requirements {facts['requirements']['counts']} of {facts['requirements']['total']}; decisions {facts['decisions']['total']}; bench checks {facts['bench_checks']['total']}")
        print("changed: " + (", ".join(changed) if changed else "nothing"))
        return 0
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
