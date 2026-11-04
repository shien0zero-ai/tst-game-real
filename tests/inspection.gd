extends SceneTree
## Exercise real inspection input, visible motion, and interruptions in the live game.

const SETTINGS_PATH := "user://settings.cfg"

var _failures: PackedStringArray = []
var _main: Node
var _camera: Camera3D
var _weapon: Node3D
var _menu: Node
var _gun_mesh: Node3D
var _hand_mesh: Node3D
var _gun_rest: Transform3D
var _hand_rest: Transform3D
var _settings_existed: bool = false
var _settings_backup := PackedByteArray()


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	_settings_existed = FileAccess.file_exists(SETTINGS_PATH)
	if _settings_existed:
		_settings_backup = FileAccess.get_file_as_bytes(SETTINGS_PATH)
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	if packed == null:
		_failures.append("Main scene could not be loaded for the inspection check.")
		await _finish()
		return
	_main = packed.instantiate()
	root.add_child(_main)
	current_scene = _main
	_camera = _main.get_node("Player/Head/Camera3D") as Camera3D
	_weapon = _camera.get_node("WeaponRig") as Node3D
	_menu = _main.get_node("PauseMenu")
	_gun_mesh = _first_mesh(_weapon.find_child("M1911Visual", true, false))
	_hand_mesh = _first_mesh(_weapon.find_child("Hands", true, false))
	_expect(_gun_mesh != null and _hand_mesh != null, "The inspection has visible gun and hand meshes.")
	_expect(_weapon.has_method("begin_inspection") and _weapon.has_method("cancel_inspection"), "The weapon exposes inspection controls.")
	var n_bound: bool = false
	for event: InputEvent in InputMap.action_get_events("inspect_weapon"):
		if event is InputEventKey and event.physical_keycode == KEY_N:
			n_bound = true
	_expect(n_bound, "Physical N is bound to inspect the weapon.")
	if not _failures.is_empty():
		await _finish()
		return
	await _frames(60)
	_gun_rest = _camera_pose(_gun_mesh)
	_hand_rest = _camera_pose(_hand_mesh)
	await _test_complete_motion()
	await _test_action_interruptions()
	await _test_menu_and_reset()
	await _finish()


func _test_complete_motion() -> void:
	var slide: Node3D = _weapon.find_child("Slide", true, false) as Node3D
	var magazine: Node3D = _weapon.find_child("Magazine", true, false) as Node3D
	var slide_before: Transform3D = slide.transform
	var magazine_before: Transform3D = magazine.transform
	await _tap_n()
	_expect(_inspecting(), "Pressing physical N starts inspection.")
	await _frames(56)
	_expect(_pose_changed(_camera_pose(_gun_mesh), _gun_rest), "Inspection visibly moves or turns the gun.")
	_expect(_pose_changed(_camera_pose(_hand_mesh), _hand_rest), "The holding hands follow the inspection motion.")
	_expect(_shots() == 0 and int(_weapon.get("ammo")) == 7, "Inspection does not fire or consume ammunition.")
	_expect(int(_main.get("score")) == 0 and int(_main.get("hits")) == 0, "Inspection cannot score target hits.")
	_expect(_pose_close(slide.transform, slide_before), "Inspection does not rack the slide.")
	_expect(_pose_close(magazine.transform, magazine_before), "Inspection does not remove the magazine.")
	# Another N press must not keep restarting a one-shot animation.
	await _tap_n()
	var duration: float = float(_weapon.get("inspect_duration"))
	_expect(duration > 1.0 and duration < 10.0, "Inspection has a bounded viewing duration.")
	await _frames(ceili(clampf(duration, 1.0, 10.0) * 60.0) - 56 + 35)
	_expect(not _inspecting(), "Inspection ends automatically despite a repeated N press.")
	_expect_idle_pose("Finishing inspection restores the normal holding pose.")
	_expect(_shots() == 0 and int(_weapon.get("ammo")) == 7, "Completing inspection leaves ammunition and shot count intact.")


func _test_action_interruptions() -> void:
	await _reset()
	await _tap_n()
	await _frames(36)
	await _tap_action("shoot")
	_expect(not _inspecting(), "Firing interrupts inspection.")
	_expect(_shots() == 1 and int(_weapon.get("ammo")) == 6, "The interrupting trigger press fires exactly one shot.")
	_expect(int(_main.get("hits")) == 1, "The interrupting shot uses the actual camera ray and hits the target.")
	await _frames(40)
	_expect_idle_pose("The weapon returns to its holding pose after the interrupting shot.")

	await _reset()
	await _tap_n()
	await _frames(30)
	Input.action_press("aim")
	await _frames(4)
	_expect(not _inspecting() and bool(_weapon.get("is_aiming")), "Aiming interrupts inspection and enters ADS.")
	await _tap_n()
	_expect(not _inspecting(), "N cannot start inspection while aiming.")
	Input.action_release("aim")
	await _frames(30)

	await _tap_action("shoot")
	await _frames(30)
	await _tap_n()
	await _frames(30)
	await _tap_action("reload")
	_expect(not _inspecting() and bool(_weapon.get("reloading")), "Reloading interrupts inspection and starts the reload.")
	await _tap_n()
	_expect(not _inspecting(), "N cannot start inspection during a reload.")
	await _frames(ceili(float(_weapon.get("reload_duration")) * 60.0) + 35)
	_expect(int(_weapon.get("ammo")) == 7 and not bool(_weapon.get("reloading")), "The interrupting reload completes normally.")


func _test_menu_and_reset() -> void:
	await _reset()
	await _tap_n()
	await _frames(30)
	await _tap_action("ui_cancel")
	_expect(paused and bool(_menu.get("is_open")), "Esc opens settings during inspection.")
	_expect(not _inspecting(), "Opening settings cancels inspection.")
	await _tap_n()
	await _frames(8)
	_expect(not _inspecting() and _shots() == 0, "N in the paused menu cannot inspect or fire.")
	await _tap_action("ui_cancel")
	await _frames(40)
	_expect(not paused and not _inspecting(), "Resuming does not replay an inspection requested in the menu.")
	_expect_idle_pose("Resuming restores the normal holding pose.")

	await _tap_n()
	await _frames(36)
	await _tap_action("reset_range")
	await _frames(30)
	_expect(not _inspecting() and int(_weapon.get("ammo")) == 7 and _shots() == 0, "Range reset cancels inspection and restores the weapon.")
	_expect_idle_pose("Range reset clears every inspection pose offset.")
	await _tap_n()
	_expect(_inspecting(), "Inspection can start again after a range reset.")


func _reset() -> void:
	Input.action_release("aim")
	_main.call("reset_session")
	await _frames(40)


func _finish() -> void:
	if is_instance_valid(_menu):
		_menu.call("close_menu")
	paused = false
	_send_n(false)
	for action: String in ["shoot", "aim", "reload", "ui_cancel", "reset_range", "inspect_weapon"]:
		Input.action_release(action)
	if is_instance_valid(_main):
		_main.queue_free()
		await _frames(2)
	if _settings_existed:
		var backup: FileAccess = FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
		if backup == null:
			_failures.append("The previous settings could not be restored after inspection checks.")
		else:
			backup.store_buffer(_settings_backup)
			backup.close()
	elif FileAccess.file_exists(SETTINGS_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))
	if _failures.is_empty():
		print("PASS: physical N inspection, visible gun/hand motion, automatic return, action interruptions, pause isolation, and reset.")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _first_mesh(node: Node) -> Node3D:
	var meshes: Array[Node] = node.find_children("*", "MeshInstance3D", true, false)
	return meshes[0] as Node3D if not meshes.is_empty() else null


func _camera_pose(node: Node3D) -> Transform3D:
	return _camera.global_transform.affine_inverse() * node.global_transform


func _angle_between(a: Transform3D, b: Transform3D) -> float:
	return a.basis.orthonormalized().get_rotation_quaternion().angle_to(b.basis.orthonormalized().get_rotation_quaternion())


func _pose_changed(a: Transform3D, b: Transform3D) -> bool:
	return a.origin.distance_to(b.origin) > 0.012 or _angle_between(a, b) > 0.10


func _pose_close(a: Transform3D, b: Transform3D) -> bool:
	return a.origin.distance_to(b.origin) < 0.003 and _angle_between(a, b) < 0.02


func _expect_idle_pose(message: String) -> void:
	_expect(_pose_close(_camera_pose(_gun_mesh), _gun_rest) and _pose_close(_camera_pose(_hand_mesh), _hand_rest), message)


func _inspecting() -> bool:
	return bool(_weapon.get("is_inspecting"))


func _shots() -> int:
	return int(_main.get("shots"))


func _send_n(pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_N
	event.physical_keycode = KEY_N
	event.pressed = pressed
	Input.parse_input_event(event)


func _tap_n() -> void:
	_send_n(true)
	await _frames(2)
	_send_n(false)
	await _frames(2)


func _tap_action(action: String) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = true
	Input.parse_input_event(event)
	await _frames(2)
	event.pressed = false
	Input.parse_input_event(event)
	await _frames(2)


func _frames(count: int) -> void:
	for _frame: int in count:
		await process_frame


func _expect(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
