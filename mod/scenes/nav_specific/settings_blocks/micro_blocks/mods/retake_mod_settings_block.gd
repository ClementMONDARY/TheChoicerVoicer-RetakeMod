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


func _set_from_profile() -> void :
	chk_enable_retake_mod.button_pressed = Profile.dub_mode_replay_mod_enabled
	chk_enable_default_mic_on_replay.button_pressed = Profile.dub_mode_default_mic_on_replay
	slider_tracks_mixin_default.value = Profile.dub_mode_default_tracks_mixin
	chk_invert_mixin_slider.button_pressed = Profile.dub_mode_invert_tracks_mixin_display
	_apply_invert_display(Profile.dub_mode_invert_tracks_mixin_display)


func _on_reset_values() -> void :
	Profile.dub_mode_replay_mod_enabled = true
	Profile.dub_mode_default_mic_on_replay = false
	Profile.dub_mode_default_tracks_mixin = 100.0
	Profile.dub_mode_invert_tracks_mixin_display = false
	_set_from_profile()


func _connect_signals() -> void :
	chk_enable_retake_mod.toggled.connect(Profile._set_dub_mode_replay_mod_enabled)
	chk_enable_default_mic_on_replay.toggled.connect(Profile._set_dub_mode_default_mic_on_replay)
	slider_tracks_mixin_default.value_changed.connect(Profile._set_dub_mode_default_tracks_mixin)
	chk_invert_mixin_slider.toggled.connect(Profile._set_dub_mode_invert_tracks_mixin_display)
	chk_invert_mixin_slider.toggled.connect(_apply_invert_display)
	btn_reset_values.pressed.connect(_on_reset_values)


func _ready() -> void :
	_icon_backing = icon_mixin_left.texture
	_icon_voicelines = icon_mixin_right.texture
	_set_from_profile()
	_connect_signals()


func _on_chk_enable_retake_mod_toggled(toggled_on: bool) -> void:
	chk_enable_default_mic_on_replay.disabled = not toggled_on
	slider_tracks_mixin_default.editable = toggled_on
	chk_invert_mixin_slider.disabled = not toggled_on
