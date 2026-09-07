# The Choicer Voicer - Retake Mod

Lets you hear your own take mixed with the backing track and the original
line while you're still on the replay screen, instead of waiting until the
whole scene is done. A checkbox turns your voice on/off in that mix, a slider
crossfades between the backing track and the original line, and Settings ->
Mods -> Retake lets you set defaults for both (applied at the start of every
clip), invert which side of the slider shows which track, or turn the whole
thing off and get the game's original behaviour back.

The mod is **Online Multiplayer Compatible**, end-to-end tested from today's last version [v133](https://gamebanana.com/mods/704055).

**Windows and Linux, version 0.5.3. You need to own the game.**

## you need to own the game

There's no game files in here. No code, no assets, no exe. It's this mod's own
patches, a handful of new scenes/scripts, and a script that builds the mod out
of the copy you already bought - same approach as TCV's online multiplayer
mod, and for the same reason: see [why you can't just drop files
in](#why-you-cant-just-drop-files-in).

## installing

1. Buy the game: https://yeahmaybe.itch.io/the-choicer-voicer
2. Download this repo as a zip and unzip it properly (don't run the installer
   from inside the zip/rar - extract it to a normal folder first).
3. **Windows:** double click `Install.bat`.
   **Linux:** `chmod +x Install.sh && ./Install.sh`, or `python3 install_mod.py`.
4. It finds your copy of the game on its own (Steam, itch, Downloads,
   Desktop), or asks you to point at it. Takes a few minutes the first time -
   it downloads gdRE and Godot (both free, official) to rebuild the game with.
   Faster on later runs, it reuses what it already downloaded.
5. Launch the new build. Settings -> Mods -> Retake has the options.

Your saves and voice packs aren't touched - the modded build reads the same
save folder as the normal one, so keep both and launch whichever you like.

### command line options

```
python install_mod.py "/path/to/TheChoicerVoicer_0-5-3 compatibility.exe"
```

| Flag | What it does |
| --- | --- |
| `-o PATH` | where to put the modded build |
| `--godot PATH` | use a Godot you've already got |
| `--godot-version VER` | build on this Godot instead of the game's own |
| `--gdre PATH` | use a `gdre_tools` you've already got |
| `--keep-work` | keep the decompiled project instead of binning it |
| `--project DIR` | patch a decompiled project and stop, for modders |
| `--decompile-only` | unpack the game and stop, unmodified (for adding a new version) |

## why you cant just drop files in

Godot games are one executable with everything packed inside, and this one's
got the pack baked into the exe rather than sat next to it as a `.pck`. Godot
only looks for loose override files when there's no pack inside the exe, so
anything dropped next to it is ignored - the game never reads it. The scripts
inside the pack are compiled down to tokens at export time too, not text, so
there'd be nothing to edit even with the pack cracked open. The only way in is
rebuilding the exe, which is what the installer does.

## how it works

`install_mod.py` downloads [gdRE](https://github.com/GDRETools/gdsdecomp) and
decompiles your copy, applies the patches under `mod/patches/` (small,
line-anchored diffs against the game's own scenes) and drops in the new files
under `mod/` (the feature itself, its preferences and the Settings -> Mods
page), then downloads the matching [Godot](https://godotengine.org) and
re-exports. Which Godot it grabs is worked out from the decompiled project
rather than fixed, the same way the multiplayer mod's installer does it.

What's in `mod/`:

```
mod/patches/v0_5_3/*.patch     edits to the game's own scenes
mod/scenes/gameplay/...        the feature itself, and its preferences
mod/scenes/nav_specific/...    the Settings -> Mods -> Retake page
mod/addons/...                 icons used by both
mod/export_presets.cfg         the Windows and Linux export presets
```

### living beside other mods

**No game script is patched.** The whole feature lives in `retake_mod.gd`,
which rides on a single node the scene patch adds to `dub_mode.tscn` and
reaches the game through that node's owner - rewiring the buttons it needs at
runtime rather than editing the code behind them. So the mod's entire
footprint on the game is two scene files, and neither is one the online
multiplayer mod touches (it patches seven scripts, `dub_mode.gd` among them).

The Settings -> Mods page is shared ground rather than this mod's own: it
scans a folder at startup, so a mod appears there by dropping one scene into
it, and no two installers ever edit the same line. Preferences go to
`user://mod_settings.cfg` under a section named after the mod, never into the
game's own profile. `tests/check_mod_compat.py` replays another mod's patches
and then this one's on top, to catch a clash before a player does.

If a future game update moves these files around, the installer prints the
lines it expected next to what's actually there and stops rather than
guessing - that diagnostic (also saved to `install_log.txt`) is normally
enough to bring the patches up to date.

## rough edges

- Only tested against Windows 0.5.3 so far. Linux support is implemented
  (game-path detection, gdRE/Godot downloads, export preset) but not yet
  verified against a real Linux install of the game.
- Only one version's worth of patches exists right now (`v0_5_3`). A future
  game update needs a new `mod/patches/v0_5_X/` folder; see `--decompile-only`.

## ai assistance

Parts of this mod, including this installer (adapted from the online
multiplayer mod's own installer, credited below) and this documentation, were
written with the assistance of **Claude**, an AI assistant by Anthropic
(<https://claude.ai>), used through its agentic coding interface.

## credits

The Choicer Voicer is by **YeahMaybe**. This is an unofficial fan mod, nothing
to do with them and not endorsed by them.

This mod and its installer are by **Nemeco_**. The installer's engine (game
detection, gdRE/Godot download and caching, the patch applier, engine-version
detection) is adapted from the installer of **TCV's online multiplayer mod**,
by TypeOneAppolo / AppoloPL: <https://github.com/TypeOneAppolo/tcv-multiplayer-mod>
- go play that too.

The icons used in this mod come from the [godot-easy-icons](https://store.godotengine.org/asset/fellow-roach/godot-easy-icons/) pack by [Fellow Roach](https://store.godotengine.org/publisher/fellow-roach/) on the Godot Engine asset store.

MIT licence, see [LICENSE](LICENSE). Built with
[Godot](https://godotengine.org) and [gdRE](https://github.com/GDRETools/gdsdecomp).