extends VBoxContainer


## Container for the Settings -> Mods page.
##
## Blocks are discovered at runtime rather than instanced in the scene, so installing
## a mod means dropping one scene into BLOCKS_FOLDER and nothing else. No two mod
## installers ever edit the same line, and the install order stops mattering.


const BLOCKS_FOLDER: String = "res://scenes/nav_specific/settings_blocks/micro_blocks/mods/"


@onready var mod_blocks: VBoxContainer = %ModBlocks


func _ready() -> void :
	for file_name: String in _discover_blocks():
		var packed: Resource = load(BLOCKS_FOLDER + file_name)
		if packed is PackedScene: mod_blocks.add_child(packed.instantiate())
	if mod_blocks.get_child_count() == 0: _show_empty_notice()


func _discover_blocks() -> PackedStringArray:
	var found: PackedStringArray = []
	for file_name: String in DirAccess.get_files_at(BLOCKS_FOLDER):
		# An exported build holds x.scn plus an x.tscn.remap stub; the editor holds x.tscn.
		# Loading through the .tscn path works in both cases, so normalise onto that.
		if file_name.ends_with(".remap"): file_name = file_name.trim_suffix(".remap")
		elif file_name.ends_with(".scn"): file_name = file_name.get_basename() + ".tscn"
		elif !file_name.ends_with(".tscn"): continue
		if !found.has(file_name): found.append(file_name)
	found.sort()
	return found


func _show_empty_notice() -> void :
	var notice: = Label.new()
	notice.text = "No mod settings found."
	notice.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mod_blocks.add_child(notice)
