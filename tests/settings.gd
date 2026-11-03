extends SceneTree
## Exercise the live pause menu, sensitivity controls, persistence, and input isolation.

const SETTINGS_PATH: String = "user://settings.cfg"
const DEFAULT_SENSITIVITY: float = 0.002

var _failures: PackedStringArray = []
var _main: Node
var _player: CharacterBody3D
var _weapon: Node3D
var _menu: Node
var _settings_existed: bool = false
var _settings_backup: PackedByteArray = PackedByteArray()


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	_settings_existed = FileAccess.file_exists(SETTINGS_PATH)
	if _settings_existed:
		_settings_backup = FileAccess.get_file_as_bytes(SETTINGS_PATH)
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	if packed == null:
		_failures.append("Main scene could not be loaded for the settings check.")
		await _finish()
		return
	_spawn(packed)
	await _physics_frames(90)
	_expect(not paused and not bool(_menu.get("is_open")), "The game starts with its settings menu closed.")
	_expect(_near(_sensitivity(), DEFAULT_SENSITIVITY), "A fresh settings file uses the default mouse sensitivity.")
	await _test_controls()
	await _test_pause_isolation()
	await _test_persistence(packed)
	await _finish()


func _spawn(packed: PackedScene) -> void:
	_main = packed.instantiate()
	root.add_child(_main)
	current_scene = _main
	_player = _main.get_node("Player") as CharacterBody3D
	_weapon = _player.get_node("Head/Camera3D/WeaponRig") as Node3D
	_menu = _main.get_node("PauseMenu")


func _test_controls() -> void:
	await _tap("ui_cancel")
	_expect(paused and bool(_menu.get("is_open")), "Esc opens the settings menu and pauses gameplay.")
	_menu.call("set_sensitivity_multiplier", 1.75)
	_expect(_near(_sensitivity(), 0.0035), "Changing sensitivity immediately changes the actual player setting.")
	var slider: HSlider = _menu.get("sensitivity_slider") as HSlider
	_expect(slider != null, "The settings menu exposes its real sensitivity slider.")
	if slider != null:
		slider.value = 210.0
		_expect(_near(_sensitivity(), 0.0042), "Moving the real UI slider updates mouse sensitivity.")
	_menu.call("set_sensitivity_multiplier", -10.0)
	_expect(_near(_sensitivity(), 0.0002), "Sensitivity cannot be reduced below the supported minimum.")
	_menu.call("set_sensitivity_multiplier", 20.0)
	_expect(_near(_sensitivity(), 0.006), "Sensitivity cannot exceed the supported maximum.")
	_menu.call("restore_defaults")
	_expect(_near(_sensitivity(), DEFAULT_SENSITIVITY), "Reset to default restores the original sensitivity.")
	await _tap("ui_cancel")
	_expect(not paused and not bool(_menu.get("is_open")), "Esc also closes the menu while the game is paused.")


func _test_pause_isolation() -> void:
	_main.call("reset_session")
	await _physics_frames(30)
	await _tap("shoot")
	_expect(_shots() == 1 and int(_weapon.get("ammo")) == 6, "A gameplay shot is accepted before pausing.")
	_weapon.call("begin_reload")
	_expect(bool(_weapon.get("reloading")), "A reload starts before the pause check.")
	_menu.call("open_menu")
	var position_before: Vector3 = _player.global_position
	var shots_before: int = _shots()
	Input.action_press("move_forward")
	_send_action("shoot", true)
	_send_action("reload", true)
	# Wait longer than an entire reload while the scene is paused.
	await _process_frames(ceili(float(_weapon.get("reload_duration")) * 60.0) + 15)
	_expect(_player.global_position.distance_to(position_before) < 0.0001, "Movement input cannot move the player behind the settings menu.")
	_expect(_shots() == shots_before and int(_weapon.get("ammo")) == 6, "Menu interaction cannot fire or consume ammunition.")
	_expect(bool(_weapon.get("reloading")), "Gameplay reload time does not advance while the settings menu is open.")
	Input.action_release("move_forward")
	_send_action("shoot", false)
	_send_action("reload", false)
	_menu.call("close_menu")
	await _process_frames(2)
	_expect(_shots() == shots_before and int(_weapon.get("ammo")) == 6, "Resuming does not turn menu input into an accidental shot.")
	await _physics_frames(ceili(float(_weapon.get("reload_duration")) * 60.0) + 8)
	_expect(not bool(_weapon.get("reloading")) and int(_weapon.get("ammo")) == 7, "A paused reload completes normally after resuming.")

	# Opening the menu in the same frame as firing must discard pending fire input.
	_send_action("shoot", true)
	_menu.call("open_menu")
	await _process_frames(2)
	_send_action("shoot", false)
	_menu.call("close_menu")
	await _physics_frames(20)
	_expect(_shots() == shots_before and int(_weapon.get("ammo")) == 7, "A trigger request queued before opening settings is not fired on resume.")


func _test_persistence(packed: PackedScene) -> void:
	_menu.call("open_menu")
	_menu.call("set_sensitivity_multiplier", 1.6)
	_menu.call("close_menu")
	_expect(FileAccess.file_exists(SETTINGS_PATH), "Closing settings saves the sensitivity to the player's configuration.")
	_main.queue_free()
	await _process_frames(2)
	_spawn(packed)
	await _process_frames(3)
	_expect(_near(_sensitivity(), 0.0032), "A new game instance restores the saved sensitivity.")
	_menu.call("open_menu")
	var slider: HSlider = _menu.get("sensitivity_slider") as HSlider
	if slider != null:
		_expect(_near(slider.value, 160.0), "Reopened settings show the saved sensitivity in the actual slider.")
	_menu.call("close_menu")


func _finish() -> void:
	if is_instance_valid(_menu):
		_menu.call("close_menu")
	paused = false
	for action: String in ["move_forward", "shoot", "reload", "ui_cancel"]:
		Input.action_release(action)
	if is_instance_valid(_main):
		_main.queue_free()
		await _process_frames(2)
	if _settings_existed:
		var backup_file: FileAccess = FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
		if backup_file == null:
			_failures.append("The previous sensitivity configuration could not be restored.")
		else:
			backup_file.store_buffer(_settings_backup)
			backup_file.close()
	elif FileAccess.file_exists(SETTINGS_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))
	if _failures.is_empty():
		print("PASS: Esc pause menu, live sensitivity slider, bounds/defaults, saved settings, paused gameplay, and safe resume.")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _sensitivity() -> float:
	return float(_player.get("mouse_sensitivity"))


func _shots() -> int:
	return int(_main.get("shots"))


func _near(actual: float, expected: float) -> bool:
	return absf(actual - expected) < 0.000001


func _send_action(action: String, pressed: bool) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = pressed
	Input.parse_input_event(event)


func _tap(action: String) -> void:
	_send_action(action, true)
	await _process_frames(2)
	_send_action(action, false)
	await _process_frames(2)


func _process_frames(count: int) -> void:
	for _frame: int in range(count):
		await process_frame


func _physics_frames(count: int) -> void:
	for _frame: int in range(count):
		await physics_frame


func _expect(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
