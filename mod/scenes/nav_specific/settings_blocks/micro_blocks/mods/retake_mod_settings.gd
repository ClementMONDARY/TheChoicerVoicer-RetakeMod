class_name RetakeModSettings


## Keys, defaults and accessors for the Retake mod's preferences, so the feature code
## and its settings block can never disagree on a default or a bound.


const SECTION: String = "retake"

const KEY_ENABLED: String = "enabled"
const KEY_DEFAULT_MIC_ON_REPLAY: String = "default_mic_on_replay"
const KEY_DEFAULT_TRACKS_MIXIN: String = "default_tracks_mixin"
const KEY_INVERT_TRACKS_MIXIN_DISPLAY: String = "invert_tracks_mixin_display"

const DEFAULT_ENABLED: bool = true
const DEFAULT_MIC_ON_REPLAY: bool = false
const DEFAULT_TRACKS_MIXIN: float = 100.0
const DEFAULT_INVERT_TRACKS_MIXIN_DISPLAY: bool = false


static func enabled() -> bool:
	return bool(ModSettings.read(SECTION, KEY_ENABLED, DEFAULT_ENABLED))


static func set_enabled(value: bool) -> void:
	ModSettings.write(SECTION, KEY_ENABLED, value)


static func default_mic_on_replay() -> bool:
	return bool(ModSettings.read(SECTION, KEY_DEFAULT_MIC_ON_REPLAY, DEFAULT_MIC_ON_REPLAY))


static func set_default_mic_on_replay(value: bool) -> void:
	ModSettings.write(SECTION, KEY_DEFAULT_MIC_ON_REPLAY, value)


static func default_tracks_mixin() -> float:
	return float(ModSettings.read(SECTION, KEY_DEFAULT_TRACKS_MIXIN, DEFAULT_TRACKS_MIXIN))


static func set_default_tracks_mixin(value: float) -> void:
	ModSettings.write(SECTION, KEY_DEFAULT_TRACKS_MIXIN, value)


static func invert_tracks_mixin_display() -> bool:
	return bool(ModSettings.read(SECTION, KEY_INVERT_TRACKS_MIXIN_DISPLAY, DEFAULT_INVERT_TRACKS_MIXIN_DISPLAY))


static func set_invert_tracks_mixin_display(value: bool) -> void:
	ModSettings.write(SECTION, KEY_INVERT_TRACKS_MIXIN_DISPLAY, value)


static func reset() -> void:
	ModSettings.reset_section(SECTION)
