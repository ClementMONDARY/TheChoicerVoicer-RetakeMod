class_name ModSettings extends RefCounted


## Shared preference store for TCV mods.
##
## Mods keep their preferences here instead of patching profile.gd, so two mods
## installed side by side never write to the same file and the install order stops
## mattering. Each mod owns one section, named after itself.
##
## Values live in user://mod_settings.cfg, beside the game's own save data, and
## survive a rebuild of the game executable.


## Bumped whenever these shared files change in a way other mods depend on. Every
## mod installer ships this layer and uses the number to decide whether the copy
## already installed by another mod should be left alone or replaced.
const SHARED_VERSION: int = 1


const FILE_PATH: String = "user://mod_settings.cfg"


## Emitted after any value actually changes. An empty key means a whole section
## was reset, so a listener should re-read everything it cares about in it.
signal changed(section: String, key: String)


static var _instance: ModSettings = null
static var _config: ConfigFile = null


static func instance() -> ModSettings:
	if _instance == null:
		_instance = ModSettings.new()
		_config = ConfigFile.new()
		_config.load(FILE_PATH) # a missing file just means every read falls back to its default
	return _instance


static func read(section: String, key: String, default: Variant) -> Variant:
	instance()
	return _config.get_value(section, key, default)


static func write(section: String, key: String, value: Variant) -> void:
	instance()
	if _config.has_section_key(section, key) and _config.get_value(section, key) == value: return
	_config.set_value(section, key, value)
	_config.save(FILE_PATH)
	_instance.changed.emit(section, key)


static func reset_section(section: String) -> void:
	instance()
	if !_config.has_section(section): return
	_config.erase_section(section)
	_config.save(FILE_PATH)
	_instance.changed.emit(section, "")
