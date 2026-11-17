"""Append-only slot archives; copy before a temporary workspace is removed."""
import json
from pathlib import Path
import shutil

import health


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def preserve(workdir, destination, row):
    """Keep the entire workspace plus a content-verified file manifest.

    copytree must succeed before returning; failures propagate, so dispatch
    cannot continue and the caller must retain the original working directory.
    """
    workdir, destination = Path(workdir), Path(destination)
    shutil.copytree(workdir, destination, symlinks=True)
    files = {p.relative_to(destination).as_posix(): health.file_sha(p)
             for p in sorted(destination.rglob("*")) if p.is_file() and not p.is_symlink()}
    for rel, sha in files.items():
        if health.file_sha(workdir / rel) != sha:
            raise OSError("archive changed during copy: %s" % rel)
    candidate = destination / "candidate"
    # A broken/symlink workspace is still preserved, but cannot become a
    # verified frozen candidate.
    try:
        candidate_sha = health.tree_sha(candidate) if candidate.is_dir() else None
    except (OSError, ValueError):
        candidate_sha = None
    manifest = {"schema": "evobot.slot_archive/1", "files": files,
                "candidate_sha": candidate_sha, "record": row}
    write_json(destination / "archive.json", manifest)
    return {"path": str(destination), "manifest_sha256": health.file_sha(destination / "archive.json"),
            "candidate_sha": candidate_sha}


def verify(path):
    root = Path(path)
    manifest = json.loads((root / "archive.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "evobot.slot_archive/1":
        raise ValueError("unknown archive schema")
    listed = manifest["files"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and p.name != "archive.json"}
    if actual != set(listed):
        raise ValueError("archive inventory changed")
    for rel, sha in listed.items():
        target = root / rel
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()) \
                or health.file_sha(target) != sha:
            raise ValueError("archive file changed: %s" % rel)
    if manifest["candidate_sha"] is not None and health.tree_sha(root / "candidate") != manifest["candidate_sha"]:
        raise ValueError("candidate changed after archival")
    return manifest
