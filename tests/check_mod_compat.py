#!/usr/bin/env python3
"""Check that this mod's patches still apply on top of another TCV mod.

Contains no game content of any kind. It needs a vanilla decompile you already
have (get one with `python ../install_mod.py --decompile-only`), and it fetches
the other mod's *patches* fresh from its own public repo -- nothing from either
mod's source is stored here, only this check itself.

    python check_mod_compat.py --vanilla C:\\path\\to\\decompiled\\vanilla

By default it checks against the online multiplayer mod
(https://github.com/TypeOneAppolo/tcv-multiplayer-mod). Point --other-mod at a
local clone, or another mod's git URL, to check a different one.

What it does, per patch-set folder found in the other mod's mod/patches/:
  1. copy your vanilla project to a scratch dir
  2. apply that mod's own patches to it (common/ + that folder), with the same
     applier this mod's installer uses
  3. apply *this* mod's own patches on top
  4. report which patch-set folders that succeeded and failed against

A failure here is exactly the error a player would hit combining the two mods
-- this just finds it before they do.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import install_mod as m  # noqa: E402  (needs sys.path set up first)

DEFAULT_OTHER_MOD = "https://github.com/TypeOneAppolo/tcv-multiplayer-mod"

def fetch_other_mod(spec: str, cache: Path) -> Path:
    """A local path is used as-is. Anything else is treated as a git URL and
    shallow-cloned into the cache (re-used on a later run)."""
    local = Path(spec)
    if local.is_dir():
        return local
    dest = cache / "other_mod"
    if (dest / ".git").is_dir():
        print(f"[cache] reusing clone in {dest}, pulling latest")
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"],
                       capture_output=True, text=True)
        return dest
    print(f"[get] cloning {spec}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["git", "clone", "--depth", "1", spec, str(dest)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise m.Failed(f"could not clone {spec}\n{proc.stderr}")
    return dest


def our_patches() -> list[Path]:
    root = HERE.parent / "mod" / "patches"
    patches: list[Path] = []
    for d in sorted(root.iterdir()):
        if d.is_dir():
            patches += sorted(d.glob("*.patch"))
    # de-duplicate by target file: a later folder (a newer version) wins,
    # same "try the newest first" idea as patch_variants_for().
    by_target: dict[str, Path] = {}
    for p in patches:
        by_target[p.name] = p
    return list(by_target.values())


def other_mod_patch_sets(other_mod: Path) -> list[Path]:
    """Version folders only -- "common" is shared context applied alongside
    whichever version folder is chosen, never a set on its own."""
    root = other_mod / "mod" / "patches"
    if not root.is_dir():
        raise m.Failed(f"{other_mod} has no mod/patches/ -- not built like this mod expects")
    return sorted(d for d in root.iterdir() if d.is_dir() and d.name != "common")


def apply_set(work: Path, patches: list[Path], label: str) -> None:
    for patch in patches:
        rel = patch.name[: -len(".patch")].replace("__", "/")
        target = work / rel
        if not target.is_file():
            raise m.Failed(f"{label}: expects {rel}, which isn't in your vanilla copy "
                           "-- wrong game version?")
        # Mirror the installer: a patch that lays down the shared Mods page is skipped
        # when it is already there. Without this the second mod stacks a duplicate and
        # the check reports a clean pass on a project the installer would build right.
        sentinel = m.SHARED_PATCH_SENTINELS.get(patch.name)
        if sentinel and sentinel in m.read_text(target):
            continue
        m.apply_patch(target, m.read_text(patch), label)


NOT_APPLICABLE = "not applicable"
CONFLICT = "conflict"
OK = "ok"


def check_one(vanilla: Path, other_set: Path, scratch: Path) -> tuple[str, str]:
    """NOT_APPLICABLE means this vanilla copy isn't the version that patch-set
    targets -- expected and not a real result either way. CONFLICT means the
    other mod's own patches DID apply (so this genuinely is a shared baseline)
    but this mod's patches then failed on top of it -- that one is real."""
    work = scratch / other_set.name
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(vanilla, work)

    other_root = other_set.parent
    common = sorted((other_root / "common").glob("*.patch")) if (other_root / "common").is_dir() else []
    try:
        apply_set(work, common + sorted(other_set.glob("*.patch")), f"other mod ({other_set.name})")
    except m.Failed:
        return NOT_APPLICABLE, (f"the other mod's own {other_set.name} patches don't apply to "
                                 "your vanilla copy either -- this isn't the matching version, "
                                 "not a real conflict")

    try:
        apply_set(work, our_patches(), "this mod")
    except m.HunkMismatch as exc:
        return CONFLICT, f"{exc}\n{exc.report}"
    except m.Failed as exc:
        return CONFLICT, str(exc)
    return OK, ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vanilla", required=True, metavar="DIR",
                    help="a decompiled vanilla copy of the game (yours, not shipped here)")
    ap.add_argument("--other-mod", default=DEFAULT_OTHER_MOD, metavar="PATH_OR_URL",
                    help=f"local clone or git URL of the other mod (default: {DEFAULT_OTHER_MOD})")
    ap.add_argument("--cache", default=str(HERE / ".cache"), metavar="DIR")
    args = ap.parse_args(argv)

    vanilla = Path(args.vanilla)
    if not (vanilla / "project.godot").is_file():
        raise m.Failed(f"{vanilla} is not a decompiled project (no project.godot)")

    cache = Path(args.cache)
    other_mod = fetch_other_mod(args.other_mod, cache)
    sets = other_mod_patch_sets(other_mod)
    if not sets:
        raise m.Failed(f"{other_mod} has no version folders under mod/patches/")

    print(f"Checking this mod's patches against {len(sets)} patch-set(s) "
          f"from {args.other_mod}\n")

    scratch = cache / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, str, str]] = []
    for other_set in sets:
        status, detail = check_one(vanilla, other_set, scratch)
        results.append((other_set.name, status, detail))
        print(f"  [{status.upper()}] {other_set.name}")
        if status == CONFLICT:
            print(f"    {detail.splitlines()[0]}")

    shutil.rmtree(scratch, ignore_errors=True)

    applicable = [r for r in results if r[1] != NOT_APPLICABLE]
    conflicts = [r for r in results if r[1] == CONFLICT]
    if not applicable:
        print("\nNone of the other mod's patch-sets target this vanilla copy's version "
              "-- nothing was actually checked. Point --vanilla at the version this "
              "mod ships for, or use --other-mod to check a different mod.")
        return 2
    if conflicts:
        print(f"\n{len(conflicts)}/{len(applicable)} matching patch-set(s) conflict. Full detail:\n")
        for name, _, detail in conflicts:
            print(f"--- {name} ---\n{detail}\n")
        return 1

    print(f"\nAll {len(applicable)} matching patch-set(s) from the other mod are compatible "
          f"({len(results) - len(applicable)} skipped, wrong version).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except m.Failed as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
