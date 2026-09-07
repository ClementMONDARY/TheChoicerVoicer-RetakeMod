#!/usr/bin/env python3
"""Build The Choicer Voicer Retake mod from a copy of the game you own.

    python install_mod.py "/path/to/TheChoicerVoicer_0-5-3 compatibility.exe"

Run with --help for the other options.

Adapted from the installer of TCV's online multiplayer mod (TypeOneAppolo /
AppoloPL, MIT licence -- see LICENSE) -- same problem (a Godot game with its
pack baked into the exe, so the only way to patch it is decompile, edit the
project, rebuild), same solution. What changed: this mod's own content
(patches + new files), no netcode/autoload/mic-fix, and Linux added alongside
Windows.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE / "mod"

SUPPORTED_VERSIONS = ["0.5.3"]
GAME_VERSION = " or ".join(SUPPORTED_VERSIONS)

# Sizes of the Windows builds we have actually confirmed. Only 0.5.3 has been
# checked against this mod so far -- see patch_variants_for() for what happens
# on a version this dict and the patches/ folder don't know about yet.
KNOWN_GAME_SIZES = {
    208741456: "0.5.3 compatibility build (Windows)",
    208741312: "0.5.3 build (Windows)",
}

# The engine the mod falls back to when it cannot work out what the game
# itself was built with. See engine_version().
FALLBACK_GODOT_VERSION = "4.4.1-stable"

RELEASE_BASE = "https://github.com/godotengine/godot-builds/releases/download"

ENGINE_VERSION_RE = re.compile(
    r"\b(\d+\.\d+(?:\.\d+)?)[.\-](stable|rc\d+|beta\d+|dev\d+)\b", re.IGNORECASE)

LATEST_PATCH_OF = {
    "4.4": "4.4.1-stable",
    "4.3": "4.3-stable",
    "4.2": "4.2.2-stable",
    "4.1": "4.1.4-stable",
    "4.0": "4.0.4-stable",
}

GDRE_VERSION = "v2.6.3"
GDRE_URL_BY_OS = {
    "windows": ("https://github.com/GDRETools/gdsdecomp/releases/download/"
                "v2.6.3/GDRE_tools-v2.6.3-windows.zip"),
    "linux": ("https://github.com/GDRETools/gdsdecomp/releases/download/"
              "v2.6.3/GDRE_tools-v2.6.3-linux.zip"),
}
GDRE_EXE_NAME_BY_OS = {"windows": "gdre_tools.exe", "linux": "gdre_tools"}

# Godot's own release naming, one form per OS. Unverified on Linux until this
# mod actually gets built there (Phase 3) -- if this 404s, the fix is here.
GODOT_ARCHIVE_NAME_BY_OS = {
    "windows": "Godot_v{version}_win64.exe.zip",
    "linux": "Godot_v{version}_linux.x86_64.zip",
}
GODOT_EXE_GLOB_BY_OS = {"windows": "Godot_v*_win64.exe", "linux": "Godot_v*_linux.x86_64"}
TEMPLATE_MEMBER_BY_OS = {
    "windows": "templates/windows_release_x86_64.exe",
    "linux": "templates/linux_release_x86_64",
}

EXPORT_PRESET_BY_OS = {"windows": "Windows Desktop", "linux": "Linux"}
DEFAULT_OUTPUT_BY_OS = {
    "windows": "TheChoicerVoicer-Retake.exe",
    "linux": "TheChoicerVoicer-Retake.x86_64",
}

NODE_PATH_RE = re.compile(r'(\$%?[A-Za-z_]\w*)((?:\s*/\s*%?[A-Za-z_]\w*)+)')

# A marker that only exists once this mod has been applied, so a second run
# against an already-patched project (or the wrong exe) fails clearly instead
# of silently re-patching or corrupting something. It has to name a file this
# mod alone writes: the Mods page itself is shared, so any mod may have put it
# there, and testing that would refuse installs that are perfectly fine.
MARKER_FILE = Path("scenes/nav_specific/settings_blocks/micro_blocks/mods/retake_mod_settings_block.gd")
MARKER_TEXT = "RetakeModSettings"

# Shared mod layer: the Settings -> Mods page and the preference store every mod
# writes into. Whichever mod is installed first lays it down; the ones after read
# this version to decide between leaving it alone and replacing it with a newer one.
SHARED_VERSION_FILE = Path("common/data/mod_settings.gd")
SHARED_VERSION_RE = re.compile(r"const\s+SHARED_VERSION\s*:\s*int\s*=\s*(\d+)")

# Patches that install that shared layer rather than this mod's own feature.
# Another mod may have applied them already, and applying them twice would give
# the settings menu two Mods tabs, so each one carries a sentinel that says so.
SHARED_PATCH_SENTINELS = {
    "scene__menu__settings__menu_settings_cleaner.tscn.patch": 'name="ModsPreferences"',
}

LOG_PATH = HERE / "install_log.txt"


def current_os() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    raise Failed(f"this installer supports Windows and Linux, not {platform.system()}")


class _Tee:
    """Writes to the console and to the log, and never lets the log break the run."""

    def __init__(self, stream, handle):
        self._stream = stream
        self._handle = handle

    def write(self, text: str) -> int:
        written = self._stream.write(text)
        try:
            self._handle.write(text)
            self._handle.flush()
        except Exception:
            pass
        return written

    def flush(self) -> None:
        self._stream.flush()
        try:
            self._handle.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        return getattr(self._stream, "isatty", lambda: False)()


_log_handle = None


def start_logging() -> None:
    global _log_handle
    if _log_handle is not None:
        return
    try:
        _log_handle = open(LOG_PATH, "w", encoding="utf-8", errors="replace")
    except OSError:
        return
    import datetime
    _log_handle.write(f"installer log, started {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n")
    _log_handle.write(f"python {sys.version.split()[0]} on {sys.platform}\n\n")
    _log_handle.flush()
    sys.stdout = _Tee(sys.stdout, _log_handle)
    sys.stderr = _Tee(sys.stderr, _log_handle)


def log_crash(exc: BaseException) -> None:
    import traceback
    try:
        text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        print("\nUNEXPECTED ERROR:\n" + text, file=sys.stderr)
    except Exception:
        pass


class Failed(Exception):
    pass


def say(step: str, msg: str) -> None:
    print(f"[{step}] {msg}", flush=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _truststore_context() -> ssl.SSLContext | None:
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return None


def _certifi_context() -> ssl.SSLContext | None:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _use_context(ctx: ssl.SSLContext) -> None:
    urllib.request.install_opener(
        urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx)))


def install_https_opener() -> None:
    if os.environ.get("TCV_INSECURE_SSL") == "1":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        _use_context(ctx)
        say("warn", "TCV_INSECURE_SSL is set, so certificates are not being checked")


_CERT_STORES: list[tuple[str, object]] = [
    ("your OS certificate store, via truststore", _truststore_context),
    ("certifi's bundled certificates", _certifi_context),
]
_cert_stores_tried = 0


def _is_certificate_error(exc: Exception) -> bool:
    return "CERTIFICATE_VERIFY" in str(exc)


def _cert_fallback() -> bool:
    global _cert_stores_tried
    while _cert_stores_tried < len(_CERT_STORES):
        label, build = _CERT_STORES[_cert_stores_tried]
        _cert_stores_tried += 1
        ctx = build()
        if ctx is None:
            continue
        say("warn", f"certificate check failed; trying again with {label}")
        _use_context(ctx)
        return True
    return False


def with_cert_retry(call, *args, **kwargs):
    while True:
        try:
            return call(*args, **kwargs)
        except Exception as exc:
            if not _is_certificate_error(exc) or not _cert_fallback():
                raise


def _tls_hint(exc: Exception) -> str:
    if "CERTIFICATE_VERIFY" not in str(exc):
        return ""
    return (
        "\n\n  This is a TLS certificate error, not a problem with the mod.\n"
        "  Fixes, easiest first:\n"
        "    1. pip install certifi truststore   then run this again.\n"
        "    2. If your network or antivirus inspects HTTPS, truststore (above)\n"
        "       picks up its root from the OS certificate store once installed.\n"
        "    3. Last resort, skip verification for this run:\n"
        "         set TCV_INSECURE_SSL=1        (Windows cmd)\n"
        "         $env:TCV_INSECURE_SSL=1       (PowerShell)\n"
        "         export TCV_INSECURE_SSL=1     (Linux)\n"
        "       then re-run."
    )


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        say("cache", f"already have {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    say("get", url.rsplit("/", 1)[-1])
    seen = [0]

    def hook(count: int, block: int, total: int) -> None:
        seen[0] = count * block
        if total > 0:
            pct = min(100, seen[0] * 100 // total)
            print(f"\r      {pct:3d}%  ({seen[0] // 1048576} / {total // 1048576} MB)",
                  end="", flush=True)

    try:
        with_cert_retry(urllib.request.urlretrieve, url, tmp, hook)
    except Exception as exc:
        raise Failed(f"could not download {url}\n  {exc}{_tls_hint(exc)}")
    print()
    tmp.replace(dest)
    return dest


def unzip(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(dest)


def make_executable(path: Path) -> None:
    """Extracted archives don't keep the +x bit on Linux; put it back."""
    if current_os() == "linux" and path.is_file():
        path.chmod(path.stat().st_mode | 0o111)


def run(cmd: list[str], what: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        tail = (proc.stdout or "") + (proc.stderr or "")
        raise Failed(f"{what} failed (exit {proc.returncode})\n"
                     + "\n".join(tail.strip().splitlines()[-25:]))
    return proc


# ---------------------------------------------------------------------------
# Patch application -- identical in spirit to the multiplayer mod's own
# hand-rolled hunk applier: tolerant of the game moving a line or two between
# updates, and refuses rather than guesses when a hunk could fit more than one
# place. See patch_variants_for() for what happens when nothing fits at all.
# ---------------------------------------------------------------------------

def parse_hunks(patch_text: str) -> list[tuple[int, list[str]]]:
    lines = patch_text.split("\n")
    hunks: list[tuple[int, list[str]]] = []
    i = 0
    while i < len(lines):
        head = re.match(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", lines[i])
        if not head:
            i += 1
            continue
        start = int(head.group(1))
        body: list[str] = []
        i += 1
        while i < len(lines):
            line = lines[i]
            if line.startswith("@@") or line.startswith("--- ") or line.startswith("+++ "):
                break
            if line.startswith(("\\",)):
                i += 1
                continue
            body.append(line)
            i += 1
        while body and body[-1] == "":
            body.pop()
        hunks.append((start, body))
    return hunks


def _normalise(line: str) -> str:
    return " ".join(line.split())


def _find_block(lines: list[str], old: list[str], want: int) -> tuple[int, str]:
    for delta in range(0, 400):
        for pos in {want + delta, want - delta}:
            if 0 <= pos <= len(lines) - len(old) and lines[pos:pos + len(old)] == old:
                return pos, "exact"

    loose_old = [_normalise(l) for l in old]
    loose_lines = [_normalise(l) for l in lines]
    hits = [pos for pos in range(len(lines) - len(old) + 1)
            if loose_lines[pos:pos + len(old)] == loose_old]
    if len(hits) == 1:
        return hits[0], "whitespace differs"
    return -1, "ambiguous" if hits else "not found"


def _mismatch_report(target: Path, index: int, old: list[str],
                     lines: list[str], want: int) -> str:
    report = [f"\n  --- {target.name}, hunk {index}: what the mod expected ---"]
    for line in old:
        report.append(f"    | {line}")
    low = max(0, want - 6)
    high = min(len(lines), want + len(old) + 6)
    report.append(f"  --- what is actually at lines {low + 1}-{high} of that file ---")
    for offset, line in enumerate(lines[low:high], low + 1):
        report.append(f"    {offset:5d} | {line}")
    report.append("  --- end ---")
    return "\n".join(report)


class HunkMismatch(Failed):
    def __init__(self, message: str, report: str):
        super().__init__(message)
        self.report = report


def apply_patch(target: Path, patch_text: str, version: str = "") -> None:
    lines = read_text(target).split("\n")
    offset = 0
    for index, (start, body) in enumerate(parse_hunks(patch_text), 1):
        old: list[str] = []
        new: list[str] = []
        for raw in body:
            tag, content = raw[:1], raw[1:]
            if tag == "-":
                old.append(content)
            elif tag == "+":
                new.append(content)
            else:
                old.append(content)
                new.append(content)

        want = start - 1 + offset
        found, how = _find_block(lines, old, want)
        if found < 0:
            raise HunkMismatch(
                f"{target.name}: hunk {index} does not match.\n"
                f"  This build looks like {version or 'an unknown version'}, "
                "but its scripts are not what the mod expects.\n"
                "  Either it is a version this mod has not caught up with, "
                "or the project is already patched.",
                _mismatch_report(target, index, old, lines, want))
        if how != "exact":
            say("warn", f"{target.name} hunk {index} matched with {how} -- "
                        "the game's formatting moved, the code did not")
        lines[found:found + len(old)] = new
        offset += len(new) - len(old)
    write_text(target, "\n".join(lines))


# ---------------------------------------------------------------------------
# Engine / GDRE acquisition
# ---------------------------------------------------------------------------

def godot_url(version: str) -> str:
    name = GODOT_ARCHIVE_NAME_BY_OS[current_os()].format(version=version)
    return f"{RELEASE_BASE}/{version}/{name}"


def templates_url(version: str) -> str:
    return f"{RELEASE_BASE}/{version}/Godot_v{version}_export_templates.tpz"


def template_dir_name(version: str) -> str:
    return version.replace("-", ".")


def normalise_version(version: str) -> str:
    version = version.strip().replace(" ", "")
    match = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?[.\-](\w+)$", version)
    if not match:
        return version
    major, minor, patch, channel = match.groups()
    head = f"{major}.{minor}" if patch in (None, "0") else f"{major}.{minor}.{patch}"
    return f"{head}-{channel.lower()}"


LANGUAGE_FLOORS: list[tuple[str, re.Pattern[str], str]] = [
    ("4.4", re.compile(r"(?::|=|->)\s*Dictionary\["), "typed dictionaries"),
]


def source_engine_floor(work: Path) -> tuple[str, str] | None:
    best: tuple[str, str] | None = None
    for path in work.rglob("*.gd"):
        try:
            text = read_text(path)
        except OSError:
            continue
        for series, pattern, what in LANGUAGE_FLOORS:
            if best and version_key(best[0]) >= version_key(series):
                continue
            if pattern.search(text):
                best = (series, f"the game's own scripts use {what}, which needs Godot {series}")
    return best


def version_key(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", version.split("-")[0])
    parts = [int(n) for n in numbers[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def engine_version(work: Path, gdre_output: str = "") -> tuple[str, str]:
    candidates: list[tuple[str, str]] = []

    match = ENGINE_VERSION_RE.search(gdre_output)
    if match:
        candidates.append((normalise_version(f"{match.group(1)}-{match.group(2)}"),
                           "a version string in the decompiler's output"))

    try:
        text = read_text(work / "project.godot")
    except OSError:
        text = ""

    match = ENGINE_VERSION_RE.search(text)
    if match:
        candidates.append((normalise_version(f"{match.group(1)}-{match.group(2)}"),
                           "a version string in project.godot"))

    features = re.search(r'config/features\s*=\s*PackedStringArray\(([^)]*)\)', text)
    if features:
        for token in re.findall(r'"([^"]+)"', features.group(1)):
            if token in LATEST_PATCH_OF:
                candidates.append((LATEST_PATCH_OF[token],
                                   f"project.godot says it was saved by Godot {token}"))

    floor = source_engine_floor(work)
    if floor:
        candidates.append((LATEST_PATCH_OF.get(floor[0], FALLBACK_GODOT_VERSION), floor[1]))

    if not candidates:
        return FALLBACK_GODOT_VERSION, "guessed, nothing in the project says"

    best = max(candidates, key=lambda pair: version_key(pair[0]))
    others = [c for c in candidates if c[0] != best[0]]
    if others:
        say("mod", "engine version signals disagree: "
                   + "; ".join(f"{v} ({why})" for v, why in candidates)
                   + f" -- taking the highest, {best[0]}")
    return best


def steam_libraries() -> list[Path]:
    roots: list[Path] = []
    if current_os() == "windows":
        for env in ("ProgramFiles(x86)", "ProgramFiles"):
            base = os.environ.get(env)
            if base:
                roots.append(Path(base) / "Steam")
        home = os.environ.get("LOCALAPPDATA")
        if home:
            roots.append(Path(home) / "Steam")
    else:
        roots.append(Path.home() / ".local" / "share" / "Steam")
        roots.append(Path.home() / ".steam" / "steam")

    libs: list[Path] = []
    for root in roots:
        apps = root / "steamapps"
        if apps.is_dir():
            libs.append(apps / "common")
        vdf = apps / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                for match in re.finditer(r'"path"\s+"([^"]+)"', read_text(vdf)):
                    libs.append(Path(match.group(1).replace("\\\\", "\\")) / "steamapps" / "common")
            except OSError:
                pass
    return [lib for lib in libs if lib.is_dir()]


def find_game_exe() -> list[Path]:
    """Best-effort search. Windows patterns are proven (from the multiplayer
    mod); the Linux itch app path is a reasonable guess, not yet confirmed
    against a real Linux install -- see Phase 3 in the project notes."""
    candidates: list[Path] = []
    seen: set[str] = set()
    default_output = DEFAULT_OUTPUT_BY_OS[current_os()]

    def consider(path: Path) -> None:
        key = str(path).lower()
        if key in seen or not path.is_file():
            return
        seen.add(key)
        if path.name.lower() == default_output.lower():
            return
        candidates.append(path)

    places = list(steam_libraries())
    home = Path.home()
    places += [home / "Downloads", home / "Desktop", home / "Documents", Path.cwd()]
    if current_os() == "windows":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            places.append(Path(local) / "itch" / "apps")
        patterns = ["TheChoicerVoicer*.exe", "*/TheChoicerVoicer*.exe",
                    "*/*/TheChoicerVoicer*.exe"]
    else:
        places.append(home / ".config" / "itch" / "apps")
        patterns = ["TheChoicerVoicer*", "*/TheChoicerVoicer*", "*/*/TheChoicerVoicer*"]

    for place in places:
        if not place.is_dir():
            continue
        try:
            for pattern in patterns:
                for hit in place.glob(pattern):
                    if current_os() == "linux" and hit.is_dir():
                        continue
                    if current_os() == "linux" and not os.access(hit, os.X_OK):
                        continue
                    consider(hit)
        except OSError:
            continue

    candidates.sort(key=lambda p: (p.stat().st_size not in KNOWN_GAME_SIZES, str(p).lower()))
    return candidates


def choose_game_exe() -> Path:
    print("Looking for your copy of the game...")
    found = find_game_exe()

    if len(found) == 1 and found[0].stat().st_size in KNOWN_GAME_SIZES:
        print(f"Found: {found[0]}")
        return found[0]

    if found:
        print("\nWhich copy of the game should I use?\n")
        for i, path in enumerate(found[:9], 1):
            tag = "" if path.stat().st_size in KNOWN_GAME_SIZES else "   (untested version)"
            print(f"  {i}. {path}{tag}")
        print("  0. none of these, let me type the path\n")
        answer = input("Number: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(found[:9]):
            return found[int(answer) - 1]
    else:
        print("No copy found automatically.\n")

    print("Drag your game exe onto this window and press Enter,")
    print("or paste the full path to it.\n")
    typed = input("Game exe: ").strip().strip('"')
    if not typed:
        raise Failed("no game exe given")
    return Path(typed)


def check_game_exe(exe: Path) -> None:
    if not exe.is_file():
        raise Failed(f"no such file: {exe}")
    known = KNOWN_GAME_SIZES.get(exe.stat().st_size)
    if known:
        say("game", f"{exe.name} looks like the {known}")
    else:
        say("warn", f"{exe.name} is not a build this mod has been tested against.\n"
                    f"        Trying anyway. Expect a clear error shortly if it is "
                    f"not {GAME_VERSION}.")


def get_gdre(cache: Path, supplied: str | None) -> Path:
    if supplied:
        path = Path(supplied)
        if not path.is_file():
            raise Failed(f"--gdre {path} does not exist")
        return path
    osname = current_os()
    archive = download(GDRE_URL_BY_OS[osname], cache / f"gdre-{GDRE_VERSION}-{osname}.zip")
    out = cache / f"gdre-{GDRE_VERSION}-{osname}"
    if not out.exists():
        unzip(archive, out)
    exe_name = GDRE_EXE_NAME_BY_OS[osname]
    for candidate in out.rglob(exe_name):
        make_executable(candidate)
        return candidate
    raise Failed(f"{exe_name} not found inside the downloaded archive")


def release_exists(version: str) -> bool:
    request = urllib.request.Request(godot_url(version), method="HEAD")
    try:
        with with_cert_retry(urllib.request.urlopen, request, timeout=30) as response:
            return response.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return True


def resolve_godot_version(version: str) -> str:
    if version == FALLBACK_GODOT_VERSION or release_exists(version):
        return version
    say("warn", f"there is no Godot {version} to download. Building with "
                f"{FALLBACK_GODOT_VERSION} instead.")
    return FALLBACK_GODOT_VERSION


def get_godot(cache: Path, supplied: str | None, version: str) -> Path:
    osname = current_os()
    if supplied:
        path = Path(supplied)
        if path.is_dir():
            inner = list(path.glob(GODOT_EXE_GLOB_BY_OS[osname]))
            if inner:
                return inner[0]
        if not path.is_file():
            raise Failed(f"--godot {path} does not exist")
        return path

    archive = download(godot_url(version), cache / f"godot-{version}-{osname}.zip")
    out = cache / f"godot-{version}-{osname}"
    if not out.exists():
        unzip(archive, out)
    for candidate in out.rglob(GODOT_EXE_GLOB_BY_OS[osname]):
        if "console" not in candidate.name:
            make_executable(candidate)
            return candidate
    raise Failed("Godot executable not found inside the downloaded archive")


def templates_dir(version: str) -> Path:
    name = template_dir_name(version)
    if current_os() == "windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Godot" / "export_templates" / name
    return Path.home() / ".local" / "share" / "godot" / "export_templates" / name


def install_full_templates(cache: Path, dest: Path, version: str) -> None:
    archive = download(templates_url(version), cache / f"godot-templates-{version}.tpz")
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for entry in zf.namelist():
            if entry.endswith("/"):
                continue
            name = entry.split("/", 1)[1] if "/" in entry else entry
            with zf.open(entry) as src, open(dest / name, "wb") as dst:
                shutil.copyfileobj(src, dst)


def ensure_templates(cache: Path, version: str) -> None:
    dest = templates_dir(version)
    wanted = dest / TEMPLATE_MEMBER_BY_OS[current_os()].rsplit("/", 1)[-1]
    if wanted.is_file():
        say("skip", f"export template already installed in {dest}")
        return
    install_full_templates(cache, dest, version)
    make_executable(wanted)


def decompile(gdre: Path, exe: Path, work: Path) -> str:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    cmd = [str(gdre), "--headless", f"--recover={exe}", f"--output-dir={work}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    output = (proc.stdout or "") + (proc.stderr or "")

    scripts = sum(1 for _ in work.rglob("*.gd"))
    looks_complete = (work / "project.godot").is_file() and scripts >= 100
    if proc.returncode != 0:
        if looks_complete:
            say("warn", f"gdRE exited with code {proc.returncode}, but it had already "
                        f"unpacked the whole game ({scripts} scripts) -- carrying on")
        else:
            tail = "\n".join(output.strip().splitlines()[-25:])
            raise Failed(f"decompiling the game failed (exit {proc.returncode})\n{tail}")

    if not (work / "project.godot").is_file():
        raise Failed("decompile produced no project.godot -- is that the game exe?")
    if scripts < 100:
        raise Failed(f"decompile produced only {scripts} scripts -- the unpack is incomplete")
    return output


def repair_node_paths(work: Path) -> int:
    """gdRE writes some node paths as "$A / B" instead of "$A/B". Every
    decompiled build needs this fixed, mod or no mod."""
    fixed = 0
    for path in work.rglob("*.gd"):
        text = read_text(path)
        patched = NODE_PATH_RE.sub(
            lambda m: m.group(1) + re.sub(r"\s*/\s*", "/", m.group(2)), text)
        if patched != text:
            write_text(path, patched)
            fixed += 1
    return fixed


def detect_version(work: Path) -> str:
    match = re.search(r'config/version="([^"]+)"', read_text(work / "project.godot"))
    if not match:
        raise Failed("project.godot has no config/version -- unexpected game build")
    return match.group(1)


def patch_variants_for(version: str) -> list[tuple[str, list[Path]]]:
    """Every patch set that might fit this reported version, best guess first.

    Same reasoning as the multiplayer mod: a game update can ship without
    bumping config/version, so when nothing is named for the reported version
    every set gets tried, newest first, rather than refusing outright.
    """
    root = MOD / "patches"
    prefix = "v" + version.replace(".", "_")
    dirs = sorted((d for d in root.iterdir()
                   if d.is_dir() and d.name != "common"
                   and (d.name == prefix or d.name.startswith(prefix))),
                  key=lambda d: (len(d.name), d.name))
    if not dirs:
        dirs = sorted((d for d in root.iterdir() if d.is_dir() and d.name != "common"),
                      key=lambda d: d.name, reverse=True)
        if not dirs:
            raise Failed(f"this build reports version {version} and the mod carries "
                         "no patches at all -- the download is incomplete.")
        say("warn", f"no patch set is named for version {version}; trying all "
                    f"{len(dirs)} of them ({', '.join(d.name for d in dirs)})")
    common_dir = root / "common"
    common = sorted(common_dir.glob("*.patch")) if common_dir.is_dir() else []
    return [(d.name, common + sorted(d.glob("*.patch"))) for d in dirs]


def apply_patch_set(work: Path, patches: list[Path], version: str) -> int:
    snapshot: dict[Path, str] = {}
    try:
        applied = 0
        for patch in patches:
            rel = patch.name[: -len(".patch")].replace("__", "/")
            target = work / rel
            if not target.is_file():
                raise Failed(f"expected game file missing: {rel}")
            sentinel = SHARED_PATCH_SENTINELS.get(patch.name)
            if sentinel and sentinel in read_text(target):
                say("skip", f"{rel} already carries the shared Mods page")
                continue
            if target not in snapshot:
                snapshot[target] = read_text(target)
            apply_patch(target, read_text(patch), version)
            applied += 1
        return applied
    except Failed:
        for target, original in snapshot.items():
            write_text(target, original)
        raise


# New whole files this mod adds: settings-page scenes/scripts and their icons.
# Copied wholesale rather than patched in, same as the multiplayer mod's own
# net/*.gd -- these paths simply don't exist yet in a vanilla decompile.
NEW_FILES = [
    "addons/godot-easy-icons/icons/@icons/microphone.svg",
    "addons/godot-easy-icons/icons/@icons/microphone_mute.svg",
    "addons/godot-easy-icons/icons/@icons/speaker.svg",
    "addons/godot-easy-icons/icons/streamline/screen-1.svg",
    "scenes/nav_specific/settings_blocks/micro_blocks/mods/retake_mod_settings.gd",
    "scenes/nav_specific/settings_blocks/micro_blocks/mods/retake_mod_settings.gd.uid",
    "scenes/nav_specific/settings_blocks/micro_blocks/mods/retake_mod_settings_block.gd",
    "scenes/nav_specific/settings_blocks/micro_blocks/mods/retake_mod_settings_block.gd.uid",
    "scenes/nav_specific/settings_blocks/micro_blocks/mods/retake_mod_settings_block.tscn",
]

# The shared layer, written only when this download carries a version at least as
# new as whatever is already installed. Dropping a settings block into the mods
# folder above is all a mod has to do to appear on the page: the page scans that
# folder at runtime, so no installer ever edits a file another installer owns.
SHARED_FILES = [
    "common/data/mod_settings.gd",
    "common/data/mod_settings.gd.uid",
    "scenes/nav_specific/settings_blocks/mods_settings_block.gd",
    "scenes/nav_specific/settings_blocks/mods_settings_block.gd.uid",
    "scenes/nav_specific/settings_blocks/mods_settings_block.tscn",
]


def _shared_version(path: Path) -> int:
    """Version of the shared mod layer at path, -1 when there is none there."""
    if not path.is_file():
        return -1
    match = SHARED_VERSION_RE.search(read_text(path))
    return int(match.group(1)) if match else 0


def _copy_from_mod(work: Path, relatives: list[str]) -> None:
    for rel in relatives:
        src = MOD / rel
        if not src.is_file():
            raise Failed(f"mod/{rel} is missing -- the download is incomplete")
        dst = work / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_new_files(work: Path) -> None:
    _copy_from_mod(work, NEW_FILES)
    say("mod", f"added {len(NEW_FILES)} new files (settings UI, icons)")


LOAD_STEPS_RE = re.compile(r"^(\[gd_scene\b[^\]]*?\bload_steps=)(\d+)", re.MULTILINE)
RESOURCE_HEADER_RE = re.compile(r"^\[(?:ext|sub)_resource\b", re.MULTILINE)


def refresh_load_steps(work: Path, patches: list[Path]) -> int:
    """Recompute the load_steps header of every scene this mod patched.

    Godot writes that number as (ext_resource + sub_resource) + 1. A patch
    carrying a hard-coded count only ever fits the first mod installed: the next
    one stacking its own resources into the same scene would find a number it
    does not expect and refuse to apply. Recomputing it here keeps that one
    shared line out of every mod's patches.
    """
    fixed = 0
    for patch in patches:
        rel = patch.name[: -len(".patch")].replace("__", "/")
        target = work / rel
        if not rel.endswith(".tscn") or not target.is_file():
            continue
        text = read_text(target)
        count = len(RESOURCE_HEADER_RE.findall(text)) + 1
        updated, hits = LOAD_STEPS_RE.subn(lambda m: f"{m.group(1)}{count}", text, count=1)
        if hits and updated != text:
            write_text(target, updated)
            fixed += 1
    return fixed


def copy_shared_files(work: Path) -> None:
    installed = _shared_version(work / SHARED_VERSION_FILE)
    shipped = _shared_version(MOD / SHARED_VERSION_FILE)
    if installed > shipped:
        say("skip", f"another mod already installed a newer shared mod layer "
                    f"(v{installed} against the v{shipped} in this download)")
        return
    _copy_from_mod(work, SHARED_FILES)
    if installed < 0:
        say("mod", f"added the shared mod layer v{shipped} (Settings -> Mods page)")
    else:
        say("mod", f"shared mod layer updated from v{installed} to v{shipped}")


def apply_mod(work: Path) -> None:
    marker = work / MARKER_FILE
    if marker.is_file() and MARKER_TEXT in read_text(marker):
        raise Failed("this project already contains the Retake mod")

    version = detect_version(work)
    say("mod", f"project reports version {version}")

    say("mod", f"repaired {repair_node_paths(work)} decompiler node-path artifacts")

    variants = patch_variants_for(version)
    first_failure: HunkMismatch | None = None
    applied = False
    for label, patches in variants:
        try:
            count = apply_patch_set(work, patches, version)
        except HunkMismatch as mismatch:
            if first_failure is None:
                first_failure = mismatch
            if len(variants) > 1:
                say("warn", f"patch set {label} does not fit this build, trying the next")
            continue
        if len(variants) > 1:
            say("mod", f"patch set {label} fits this build")
        say("mod", f"patched {count} game files")
        say("mod", f"recomputed load_steps in {refresh_load_steps(work, patches)} scenes")
        applied = True
        break

    if not applied:
        print(first_failure.report)
        raise Failed(
            str(first_failure)
            + "\n\n  The lines it expected and the lines actually in your copy are\n"
              "  printed above and saved in install_log.txt. Sending that file is\n"
              "  enough for the mod to be updated for this build."
        )

    copy_shared_files(work)
    copy_new_files(work)
    shutil.copy2(MOD / "export_presets.cfg", work / "export_presets.cfg")
    say("mod", "registered the export preset")


def powershell(script: str, timeout: int = 30) -> str:
    if current_os() != "windows":
        return ""
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return ""
    try:
        proc = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", script],
                              capture_output=True, text=True, errors="replace",
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip()


def defender_detections(output: Path) -> list[str]:
    raw = powershell(
        "Get-MpThreatDetection -ErrorAction SilentlyContinue | "
        "Sort-Object InitialDetectionTime | Select-Object -Last 12 | ForEach-Object { "
        "\"$($_.InitialDetectionTime)  $($_.ThreatName)  $($_.Resources -join ' ')\" }")
    stem = output.stem.lower()
    return [line.strip() for line in raw.splitlines() if stem in line.lower()]


def realtime_protection_on() -> bool:
    answer = powershell("(Get-MpComputerStatus -ErrorAction SilentlyContinue)"
                        ".RealTimeProtectionEnabled")
    return answer.strip().lower() == "true"


def recover_leftover_build(output: Path, work: Path) -> bool:
    for stray in (output.with_suffix(".tmp"), work / (output.stem + ".tmp")):
        if stray.is_file() and stray.stat().st_size > 1048576:
            stray.replace(output)
            say("build", f"the exporter left the build as {stray.name}; renamed it")
            return True
    return False


def explain_missing_export(proc: subprocess.CompletedProcess, output: Path) -> None:
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    interesting = [line for line in tail
                   if "ERROR" in line or "error" in line or "Failed" in line]
    if interesting:
        print("\nGodot said:")
        for line in interesting[-8:]:
            print(f"  {line}")

    print(f"\nGodot finished without complaining, but {output.name} is not there.")

    if current_os() == "windows":
        hits = defender_detections(output)
        if hits:
            print("\nWindows Defender deleted it. Its own log says so:")
            for line in hits[-3:]:
                print(f"  {line}")
        elif realtime_protection_on():
            print("\nAlmost always this is antivirus. A freshly built, unsigned Godot game")
            print("looks exactly like the thing malware scanners are trained to catch, and")
            print("Defender quarantines it the moment the file is renamed to .exe.")
        else:
            print("\nUsually this is antivirus quarantining the new file the instant it")
            print("appears. Check whatever scanner you run for a blocked item.")

        folder = output.resolve().parent
        print("\nTo let it through, open PowerShell as administrator and run:")
        print(f'  Add-MpPreference -ExclusionPath "{folder}"')
        print("\nIf Defender already took a copy, release it too:")
        print("  Start-Process ms-settings:windowsdefender")
        print("  (Virus & threat protection -> Protection history -> Allow)")
        print("\nThe exclusion only covers that one folder, and you can drop it again")
        print(f'afterwards with Remove-MpPreference -ExclusionPath "{folder}".')
    else:
        print("\nCheck disk space and permissions on the output folder, and whether")
        print("anything (an AppArmor profile, a security scanner) blocked the write.")


PARSE_FAILURE_MARKERS = ("Parse Error:", 'with error "Parse error"')


def import_project(godot: Path, work: Path) -> tuple[bool, str]:
    probe = subprocess.run([str(godot), "--headless", "--path", str(work), "--import"],
                           capture_output=True, text=True, errors="replace")
    output = (probe.stdout or "") + (probe.stderr or "")
    if probe.returncode != 0 and not any(m in output for m in PARSE_FAILURE_MARKERS):
        editor = subprocess.run(
            [str(godot), "--headless", "--path", str(work), "--editor", "--quit"],
            capture_output=True, text=True, errors="replace")
        output += (editor.stdout or "") + (editor.stderr or "")
    return not any(marker in output for marker in PARSE_FAILURE_MARKERS), output


def parse_failure_summary(output: str) -> str:
    lines = [line.strip() for line in output.splitlines()
             if any(marker in line for marker in PARSE_FAILURE_MARKERS)]
    unique: list[str] = []
    for line in lines:
        if line not in unique:
            unique.append(line)
    return "\n".join(f"  {line}" for line in unique[:6])


def prepare_engine(cache: Path, args, work: Path, wanted: str, how: str) -> tuple[Path, str]:
    attempts: list[str] = [wanted]
    if not args.godot and not args.godot_version and wanted != FALLBACK_GODOT_VERSION:
        attempts.append(FALLBACK_GODOT_VERSION)

    last_output = ""
    for index, version in enumerate(attempts):
        if not args.godot:
            version = resolve_godot_version(version)
        say("build", f"trying Godot {version} ({how})" if index == 0
            else f"trying Godot {version} instead")
        godot = get_godot(cache, args.godot, version)
        ensure_templates(cache, version)

        say("build", "importing project assets (this takes a minute)")
        ok, last_output = import_project(godot, work)
        if ok:
            say("build", f"Godot {version} reads this game fine")
            return godot, version

        say("warn", f"Godot {version} cannot parse this game's scripts:\n"
                    + parse_failure_summary(last_output))
        how = "the previous choice could not parse the game"

    raise Failed(
        "no engine this installer knows about can parse your copy of the game.\n"
        + parse_failure_summary(last_output)
        + "\n\n  That normally means the game is built on a Godot newer than this\n"
          "  installer expects. Try --godot-version with a newer release, for\n"
          "  example --godot-version 4.5-stable, and please open an issue saying\n"
          "  which one worked.")


def export(godot: Path, work: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    preset = EXPORT_PRESET_BY_OS[current_os()]
    while True:
        say("build", f"exporting to {output}")
        proc = run([str(godot), "--headless", "--path", str(work),
                    "--export-release", preset, str(output.resolve())],
                   "exporting the game")
        if output.is_file() or recover_leftover_build(output, work):
            make_executable(output)
            return
        explain_missing_export(proc, output)
        if not sys.stdin.isatty():
            raise Failed("the export produced no file -- see the notes above")
        print()
        if input("Press Enter to build again once that's done, or type q to give up: "
                 ).strip().lower().startswith("q"):
            raise Failed("the export produced no file -- see the notes above")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Build The Choicer Voicer Retake mod from your own copy of the game.",
        epilog="You need to own the game. This tool never downloads it.")
    ap.add_argument("game_exe", nargs="?",
                    help="your official TheChoicerVoicer exe/binary "
                         f"({GAME_VERSION})")
    ap.add_argument("-o", "--output", default=None,
                    help="where to write the modded build (default: "
                         f"{DEFAULT_OUTPUT_BY_OS['windows']} / "
                         f"{DEFAULT_OUTPUT_BY_OS['linux']})")
    ap.add_argument("--project", metavar="DIR",
                    help="patch an already-decompiled project instead of an exe, "
                         "and stop before exporting (for modders)")
    ap.add_argument("--godot", help="path to a Godot editor instead of downloading it")
    ap.add_argument("--godot-version", metavar="VER",
                    help="build with this Godot instead of the one the game was "
                         f"made with, e.g. {FALLBACK_GODOT_VERSION}")
    ap.add_argument("--gdre", help="path to a gdre_tools binary instead of downloading it")
    ap.add_argument("--cache", default=str(HERE / ".cache"),
                    help="where downloads are kept between runs")
    ap.add_argument("--work", default=str(HERE / "work"),
                    help="scratch directory for the decompiled project")
    ap.add_argument("--keep-work", action="store_true",
                    help="do not delete the decompiled project afterwards")
    ap.add_argument("--decompile-only", action="store_true",
                    help="unpack the game and stop, without changing anything "
                         "(used to add support for a new game version)")
    args = ap.parse_args(argv)

    install_https_opener()

    if not MOD.is_dir():
        raise Failed(f"mod/ folder missing next to {Path(__file__).name}")

    cache = Path(args.cache)
    work = Path(args.work)

    if args.project:
        work = Path(args.project)
        if not (work / "project.godot").is_file():
            raise Failed(f"{work} is not a Godot project")
        apply_mod(work)
        version, _ = engine_version(work)
        print(f"\nPatched {work}. Open it in Godot {version} and export.")
        return 0

    exe = Path(args.game_exe) if args.game_exe else choose_game_exe()
    check_game_exe(exe)

    say("1/5", "getting gdRE Tools")
    gdre = get_gdre(cache, args.gdre)

    say("2/5", "decompiling your copy of the game")
    gdre_output = decompile(gdre, exe, work)

    if args.decompile_only:
        print(f"\nUnpacked to {work.resolve()} and left untouched.")
        print("Nothing was modified -- these are the game's own files.")
        return 0

    say("3/5", "applying the Retake mod")
    apply_mod(work)

    say("4/5", "getting Godot and export templates")
    if args.godot_version:
        godot_version, how = normalise_version(args.godot_version), "you asked for it"
    else:
        godot_version, how = engine_version(work, gdre_output)
    godot, godot_version = prepare_engine(cache, args, work, godot_version, how)

    say("5/5", f"building with Godot {godot_version}")
    output = Path(args.output) if args.output else Path(DEFAULT_OUTPUT_BY_OS[current_os()])
    export(godot, work, output)

    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)

    size = output.stat().st_size
    print(f"\nDone -> {output.resolve()}  ({size // 1048576} MB)")
    print("Launch it and open Settings -> Mods to find the Retake options.")
    return 0


if __name__ == "__main__":
    start_logging()
    try:
        sys.exit(main(sys.argv[1:]))
    except Failed as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)
    except SystemExit:
        raise
    except BaseException as exc:
        log_crash(exc)
        raise
