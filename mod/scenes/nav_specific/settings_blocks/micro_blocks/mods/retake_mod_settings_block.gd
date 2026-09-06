extends VBoxContainer



@onready var chk_enable_retake_mod: CheckButton = %ChkEnableRetakeMod
@onready var btn_reset_values: Button = %BtnResetValues
@onready var chk_enable_default_mic_on_replay: CheckButton = %ChkEnableDefaultMicOnReplay
@onready var slider_tracks_mixin_default: HSlider = %SliderTracksMixinDefault
@onready var chk_invert_mixin_slider: CheckButton = %ChkInvertMixinSlider
@onready var lbl_mixin_left: Label = %LblMixinLeft
@onready var lbl_mixin_right: Label = %LblMixinRight
@onready var icon_mixin_left: TextureRect = %IconMixinLeft
@onready var icon_mixin_right: TextureRect = %IconMixinRight


var _icon_backing: Texture2D
var _icon_voicelines: Texture2D


func _apply_invert_display(inverted: bool) -> void :
	lbl_mixin_left.text = "Voicelines" if inverted else "Backtrack"
	lbl_mixin_right.text = "Backtrack" if inverted else "Voicelines"
	icon_mixin_left.texture = _icon_voicelines if inverted else _icon_backing
	icon_mixin_right.texture = _icon_backing if inverted else _icon_voicelines


func _apply_enabled_display(toggled_on: bool) -> void :
	chk_enable_default_mic_on_replay.disabled = not toggled_on
	slider_tracks_mixin_default.editable = toggled_on
	chk_invert_mixin_slider.disabled = not toggled_on


func _set_from_settings() -> void :
	var is_enabled: bool = RetakeModSettings.enabled()
	var inverted: bool = RetakeModSettings.invert_tracks_mixin_display()
	chk_enable_retake_mod.set_pressed_no_signal(is_enabled)
	chk_enable_default_mic_on_replay.set_pressed_no_signal(RetakeModSettings.default_mic_on_replay())
	slider_tracks_mixin_default.set_value_no_signal(RetakeModSettings.default_tracks_mixin())
	chk_invert_mixin_slider.set_pressed_no_signal(inverted)
	_apply_invert_display(inverted)
	_apply_enabled_display(is_enabled)


func _on_reset_values() -> void :
	RetakeModSettings.reset()
	_set_from_settings()


func _on_default_mic_on_replay_toggled(toggled_on: bool) -> void :
	RetakeModSettings.set_default_mic_on_replay(toggled_on)


func _on_tracks_mixin_changed(value: float) -> void :
	RetakeModSettings.set_default_tracks_mixin(value)


func _on_invert_mixin_toggled(toggled_on: bool) -> void :
	RetakeModSettings.set_invert_tracks_mixin_display(toggled_on)
	_apply_invert_display(toggled_on)


func _connect_signals() -> void :
	chk_enable_default_mic_on_replay.toggled.connect(_on_default_mic_on_replay_toggled)
	slider_tracks_mixin_default.value_changed.connect(_on_tracks_mixin_changed)
	chk_invert_mixin_slider.toggled.connect(_on_invert_mixin_toggled)
	btn_reset_values.pressed.connect(_on_reset_values)


func _ready() -> void :
	_icon_backing = icon_mixin_left.texture
	_icon_voicelines = icon_mixin_right.texture
	_set_from_settings()
	_connect_signals()


# Wired from the scene file, so it stays the single handler for the master toggle.
func _on_chk_enable_retake_mod_toggled(toggled_on: bool) -> void:
	RetakeModSettings.set_enabled(toggled_on)
	_apply_enabled_display(toggled_on)
