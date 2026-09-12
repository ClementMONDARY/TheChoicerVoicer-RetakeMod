extends HBoxContainer


## Retake mod: hear a take back mixed against the backing track and the original voicelines.
##
## Everything the feature needs lives on this node and this script, so the mod's whole
## footprint on the game is one [node] block in dub_mode.tscn. No game script is patched,
## which is what lets this sit next to mods that patch dub_mode.gd themselves.


@onready var dub_mode: Node = owner
@onready var audio_interface: AudioInterfaceManagerBufferless = %AudioInterfaceManagerBufferless
@onready var player_backing_track: AudioStreamPlayer = %PlayerBackingTrack
@onready var btn_hear_again: ButtonCV = %BtnHearAgain
@onready var btn_stop_listening: ButtonCV = %BtnStopListening


@onready var chk_mic_replay: CheckBox = %ChkMicReplay
@onready var slider_tracks_mixin: HSlider = %TracksMixinSlider
@onready var icon_mixin_left: TextureRect = %IconMixinLeft
@onready var icon_mixin_right: TextureRect = %IconMixinRight


var resource: GameplayResourceDubMode


var _icon_backing: Texture2D
var _icon_voicelines: Texture2D


var _last_seen_clip_index: int = -1
var _watching_for_replay_end: bool = false
var _inputs_locked: bool = false




func _ready() -> void :
	resource = Metro.gameplay_resource_dub_mode
	_icon_backing = icon_mixin_left.texture
	_icon_voicelines = icon_mixin_right.texture

	# Rewired whether the mod is on or off: the handler falls straight through to the
	# vanilla call when disabled, so the master toggle keeps working mid-session instead
	# of leaving this one connection half restored.
	btn_hear_again.button_clicked.disconnect(dub_mode._hear_again)
	btn_hear_again.button_clicked.connect(_on_hear_again_clicked)

	chk_mic_replay.toggled.connect(_apply_replay_mix.unbind(1))
	slider_tracks_mixin.value_changed.connect(_apply_replay_mix.unbind(1))
	# Mod preferences do not live in Profile, so they need their own refresh path.
	ModSettings.instance().changed.connect(_apply_settings_display.unbind(2))

	_apply_settings_display()




func _process(_delta: float) -> void :
	# Prepping a replique emits nothing, so the arrival of a new one is read off the
	# host's own index instead.
	if dub_mode.clip_index != _last_seen_clip_index:
		_last_seen_clip_index = dub_mode.clip_index
		_reset_controls_to_defaults()

	# A replay ends either on a Stop click or on its own, the second reaching the host
	# through audio_interface's idled signal. Both paths hide BtnStopListening, so watch
	# that rather than hooking a call chain this node does not own.
	if _watching_for_replay_end and !btn_stop_listening.visible:
		_watching_for_replay_end = false
		if player_backing_track.playing: player_backing_track.stop()

	var revealing: bool = audio_interface.state == AudioInterfaceManagerBufferless.INTERFACE_STATE.FIRST
	var settling: bool = !audio_interface.playbar.visible or dub_mode.video_player_static.visible
	_lock_inputs(revealing or settling)




func _apply_settings_display() -> void :
	visible = RetakeModSettings.enabled()
	var inverted: bool = RetakeModSettings.invert_tracks_mixin_display()
	icon_mixin_left.texture = _icon_voicelines if inverted else _icon_backing
	icon_mixin_right.texture = _icon_backing if inverted else _icon_voicelines


func _lock_inputs(locked: bool) -> void :
	if locked == _inputs_locked: return
	_inputs_locked = locked
	chk_mic_replay.disabled = locked
	slider_tracks_mixin.editable = !locked
	modulate.a = 0.5 if locked else 1.0


func _reset_controls_to_defaults() -> void :
	# Plain assignment, so each control re-applies the mix through its own signal.
	chk_mic_replay.button_pressed = RetakeModSettings.default_mic_on_replay()
	slider_tracks_mixin.value = RetakeModSettings.default_tracks_mixin()


func _apply_replay_mix() -> void :
	var backing_vs_vclip: float = slider_tracks_mixin.value / slider_tracks_mixin.max_value
	if RetakeModSettings.invert_tracks_mixin_display(): backing_vs_vclip = 1.0 - backing_vs_vclip
	var angle: float = backing_vs_vclip * (PI / 2.0)
	if player_backing_track.stream: player_backing_track.volume_linear = cos(angle)
	audio_interface.audio_player_vclip.volume_linear = sin(angle)
	audio_interface.audio_player_pecho.volume_linear = float(chk_mic_replay.button_pressed)


func _current_clip_backing_track_timestamp() -> float :
	var timestamps: PackedFloat32Array = dub_mode.performance_array[dub_mode.clip_index].shared_omniclip.dub_timestamps
	if timestamps.is_empty(): return 0.0
	var earliest: float = timestamps[0]
	for timestamp: float in timestamps: earliest = minf(earliest, timestamp)
	return earliest




func _on_hear_again_clicked() -> void :
	# _hear_again never awaits, so everything below still lands in the same frame as the
	# audio_interface.again() it fires - the order the mix was written against.
	dub_mode._hear_again()
	if !RetakeModSettings.enabled(): return
	if !player_backing_track.stream: player_backing_track.stream = resource.backing_track
	if player_backing_track.stream: player_backing_track.play(_current_clip_backing_track_timestamp())
	var current_recording: AudioStreamWAV = MicrophoneService.get_recording() if dub_mode.turn_record_attempts else null
	if current_recording: audio_interface.audio_player_pecho.stream = current_recording;audio_interface.audio_player_pecho.play()
	else: audio_interface.audio_player_pecho.stop()
	_apply_replay_mix()
	_watching_for_replay_end = true
