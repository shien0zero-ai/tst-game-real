extends SceneTree
## A headless integration check of the actual scene, input, and physics.

var _failures: PackedStringArray = []


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	if packed == null:
		push_error("Main scene could not be loaded.")
		quit(1)
		return
	var main: Node = packed.instantiate()
	root.add_child(main)
	current_scene = main
	var player: CharacterBody3D = main.get_node("Player") as CharacterBody3D
	await _frames(90)
	_expect(player.is_on_floor(), "Player lands on the courtyard floor.")
	_expect(absf(player.position.y) < 0.1, "Player stands at floor height.")

	var start: Vector3 = player.position
	Input.action_press("move_forward")
	await _frames(60)
	Input.action_release("move_forward")
	var walk_distance: float = start.z - player.position.z
	_expect(walk_distance > 3.5, "Forward input moves the player in the camera's forward direction.")

	player.call("respawn")
	await _frames(30)
	start = player.position
	Input.action_press("move_forward")
	Input.action_press("sprint")
	await _frames(60)
	Input.action_release("move_forward")
	Input.action_release("sprint")
	_expect(start.z - player.position.z > walk_distance + 1.0, "Sprint is faster than walking.")

	player.call("respawn")
	await _frames(30)
	Input.action_press("jump")
	await _frames(2)
	Input.action_release("jump")
	await _frames(16)
	_expect(player.position.y > 0.5, "Jump lifts the player above the floor.")
	await _frames(100)
	_expect(player.is_on_floor(), "Player lands after jumping.")

	player.call("respawn")
	await _frames(30)
	Input.action_press("move_backward")
	Input.action_press("sprint")
	await _frames(240)
	Input.action_release("move_backward")
	Input.action_release("sprint")
	_expect(player.position.z > 12.0 and player.position.z < 14.0, "The courtyard wall blocks movement.")

	player.position = Vector3(2.0, -20.0, 1.0)
	await _frames(2)
	_expect(player.position.distance_to(Vector3(0.0, 0.1, 8.0)) < 0.2, "Falling out of the world returns to spawn.")
	player.position = Vector3(5.0, 2.0, 5.0)
	var reset_event := InputEventAction.new()
	reset_event.action = "reset_player"
	reset_event.pressed = true
	Input.parse_input_event(reset_event)
	await _frames(2)
	_expect(player.position.distance_to(Vector3(0.0, 0.1, 8.0)) < 0.2, "Reset input returns to spawn.")
	reset_event.pressed = false
	Input.parse_input_event(reset_event)

	for action: String in ["move_forward", "move_backward", "move_left", "move_right", "jump", "sprint", "reset_player"]:
		_expect(not InputMap.action_get_events(action).is_empty(), "Input binding exists: " + action)
	if _failures.is_empty():
		print("PASS: scene loading, floor and wall collisions, walk, sprint, jump, fall recovery, reset, and input bindings.")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _frames(count: int) -> void:
	for _frame: int in range(count):
		await physics_frame


func _expect(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
