extends SceneTree
## Exercise the actual firing input, hitscan physics, magazine, and range reset.

var _failures: PackedStringArray = []
var _main: Node
var _player: CharacterBody3D
var _camera: Camera3D
var _weapon: Node3D
var _target: StaticBody3D


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	if packed == null:
		push_error("Main scene could not be loaded for the shooting check.")
		quit(1)
		return
	_main = packed.instantiate()
	root.add_child(_main)
	current_scene = _main
	_player = _main.get_node("Player") as CharacterBody3D
	_camera = _player.get_node("Head/Camera3D") as Camera3D
	_weapon = _camera.get_node("WeaponRig") as Node3D
	_target = _main.get_node("Targets/Target10") as StaticBody3D
	await _frames(90)
	for action: String in ["shoot", "aim", "reload", "reset_range"]:
		_expect(not InputMap.action_get_events(action).is_empty(), "Input binding exists: " + action)
	_expect(int(_weapon.get("capacity")) == 7, "The M1911 magazine holds seven rounds.")
	_expect(int(_weapon.get("ammo")) == 7, "The range starts with a full magazine.")
	_expect(not bool(_weapon.get("reloading")), "The range starts outside a reload.")
	await _test_firing_and_reload()
	await _test_reset()
	await _test_occlusion()
	if _failures.is_empty():
		print("PASS: center hits and score, semi-auto input, cooldown, ADS, empty magazine, timed reload, range reset, and wall occlusion.")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _test_firing_and_reload() -> void:
	# Hold the input beyond the fire interval: a semi-automatic pistol fires once.
	_send_action("shoot", true)
	await _frames(2)
	_expect(_stat("shots") == 1, "A trigger press fires one shot.")
	_expect(int(_weapon.get("ammo")) == 6, "A shot consumes one round.")
	_expect(_stat("hits") == 1, "A centered shot hits the ten-metre target.")
	_expect(_stat("score") > 0, "A centered target hit awards points.")
	_expect(int(_target.get("hit_count")) == 1, "The actual target records the hitscan impact.")
	_expect(_target.get_node("Marks").get_child_count() > 0, "A target hit creates an impact mark.")
	await _frames(30)
	_expect(_stat("shots") == 1 and int(_weapon.get("ammo")) == 6, "Holding the trigger does not fire automatically.")
	_send_action("shoot", false)
	await _settle()

	# Two distinct presses inside the cooldown still accept only the first shot.
	await _tap("shoot")
	var shots_before: int = _stat("shots")
	var ammo_before: int = int(_weapon.get("ammo"))
	_expect(shots_before == 2, "Releasing and pressing again fires the next shot.")
	await _tap("shoot")
	_expect(_stat("shots") == shots_before and int(_weapon.get("ammo")) == ammo_before, "Cooldown rejects rapid extra presses without spending ammunition.")

	Input.action_press("aim")
	await _frames(3)
	_expect(bool(_weapon.get("is_aiming")), "Holding aim enters aim-down-sights mode.")
	Input.action_release("aim")
	await _frames(3)
	_expect(not bool(_weapon.get("is_aiming")), "Releasing aim leaves aim-down-sights mode.")

	# Allow the recoil to recover before each remaining shot at the same target.
	var rounds_left: int = int(_weapon.get("ammo"))
	for _round: int in range(rounds_left):
		await _settle()
		await _tap("shoot")
	_expect(int(_weapon.get("ammo")) == 0, "Seven accepted shots empty the magazine.")
	_expect(_stat("shots") == 7, "The magazine produces exactly seven shots.")
	shots_before = _stat("shots")
	var hits_before: int = _stat("hits")
	var score_before: int = _stat("score")
	await _settle()
	await _tap("shoot")
	_expect(int(_weapon.get("ammo")) == 0 and _stat("shots") == shots_before, "An empty trigger press does not fire or spend ammunition.")
	_expect(_stat("hits") == hits_before and _stat("score") == score_before, "Dry firing cannot add hits or points.")

	await _tap("reload")
	_expect(bool(_weapon.get("reloading")), "Reload input starts the reload.")
	_expect(int(_weapon.get("ammo")) == 0, "Reload does not refill the magazine immediately.")
	await _tap("shoot")
	_expect(_stat("shots") == shots_before, "Shooting is blocked during reload.")
	var reload_frames: int = ceili(float(_weapon.get("reload_duration")) * 60.0)
	await _frames(maxi(1, floori(float(reload_frames) / 3.0)))
	_expect(bool(_weapon.get("reloading")) and int(_weapon.get("ammo")) == 0, "The reload remains active before its duration elapses.")
	await _frames(reload_frames + 4)
	_expect(not bool(_weapon.get("reloading")), "Reload completes after its duration.")
	_expect(int(_weapon.get("ammo")) == 7, "Completed reload restores seven rounds.")


func _test_reset() -> void:
	await _settle()
	await _tap("shoot")
	_expect(_stat("hits") > 0 and _stat("score") > 0, "The session contains target hits before reset.")
	await _tap("reload")
	_expect(bool(_weapon.get("reloading")), "A partial magazine can be reloaded.")
	await _tap("reset_range")
	await _frames(2)
	_expect(_stat("shots") == 0 and _stat("hits") == 0 and _stat("score") == 0, "Range reset clears every session counter.")
	_expect(int(_weapon.get("ammo")) == 7 and not bool(_weapon.get("reloading")), "Range reset restores ammunition and cancels reload.")
	for target: Node in _main.get_node("Targets").get_children():
		_expect(int(target.get("hit_count")) == 0, "Range reset clears target hits: " + target.name)
		_expect(target.get_node("Marks").get_child_count() == 0, "Range reset removes impact marks: " + target.name)
	_expect(_player.position.distance_to(Vector3(0.0, 0.1, 8.0)) < 0.2, "Range reset returns the player to the firing position.")

	# A canceled reload must not refill the next magazine a second time later.
	await _settle()
	await _tap("shoot")
	_expect(int(_weapon.get("ammo")) == 6, "Shooting works immediately after a range reset.")
	await _frames(ceili(float(_weapon.get("reload_duration")) * 60.0) + 4)
	_expect(int(_weapon.get("ammo")) == 6, "A canceled reload cannot later refill ammunition.")


func _test_occlusion() -> void:
	_main.call("reset_session")
	await _settle()
	var blocker := StaticBody3D.new()
	blocker.name = "TestOccluder"
	blocker.collision_layer = 1
	blocker.collision_mask = 0
	blocker.position = Vector3(0.0, 1.5, 3.0)
	var shape := BoxShape3D.new()
	shape.size = Vector3(2.0, 3.0, 0.4)
	var collision := CollisionShape3D.new()
	collision.shape = shape
	blocker.add_child(collision)
	_main.add_child(blocker)
	await _frames(3)
	await _tap("shoot")
	_expect(_stat("shots") == 1 and int(_weapon.get("ammo")) == 6, "A shot into world geometry still consumes one round.")
	_expect(_stat("hits") == 0 and _stat("score") == 0 and int(_target.get("hit_count")) == 0, "A solid world collider blocks the target hitscan.")
	blocker.queue_free()
	await _settle()
	await _tap("shoot")
	_expect(_stat("hits") == 1 and _stat("score") > 0, "Removing the blocker makes the same target hittable again.")
	_expect(int(_target.get("hit_count")) == 1, "The unblocked target records the impact.")


func _stat(key: String) -> int:
	return int(_main.get(key))


func _send_action(action: String, pressed: bool) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = pressed
	Input.parse_input_event(event)


func _tap(action: String) -> void:
	_send_action(action, true)
	await _frames(2)
	_send_action(action, false)
	await _frames(2)


func _settle() -> void:
	await _frames(36)
	_camera.rotation = Vector3.ZERO


func _frames(count: int) -> void:
	for _frame: int in range(count):
		await physics_frame


func _expect(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
