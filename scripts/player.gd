extends CharacterBody3D
## Distances are metres. Movement speeds are metres per second.

@export_range(1.0, 10.0, 0.1) var walk_speed: float = 4.5
@export_range(1.0, 15.0, 0.1) var sprint_speed: float = 7.0
@export_range(1.0, 10.0, 0.1) var jump_speed: float = 4.5
@export_range(1.0, 40.0, 0.5) var acceleration: float = 18.0
@export_range(0.0001, 0.01, 0.0001) var mouse_sensitivity: float = 0.002

@onready var head: Node3D = $Head

var _spawn_transform: Transform3D
var _gravity: float = float(ProjectSettings.get_setting("physics/3d/default_gravity", 9.8))


func _ready() -> void:
	_spawn_transform = global_transform
	# Headless checks do not need a mouse or a display.
	if DisplayServer.get_name() != "headless":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotate_y(-event.relative.x * mouse_sensitivity)
		head.rotation.x = clampf(head.rotation.x - event.relative.y * mouse_sensitivity, deg_to_rad(-85.0), deg_to_rad(85.0))
	if event.is_action_pressed("reset_player"):
		respawn()


func _physics_process(delta: float) -> void:
	var can_move: bool = Input.mouse_mode == Input.MOUSE_MODE_CAPTURED or DisplayServer.get_name() == "headless"
	var input_vector: Vector2 = Vector2.ZERO
	if can_move:
		input_vector = Input.get_vector("move_left", "move_right", "move_forward", "move_backward")
	var direction: Vector3 = global_basis * Vector3(input_vector.x, 0.0, input_vector.y)
	var speed: float = sprint_speed if Input.is_action_pressed("sprint") else walk_speed
	velocity.x = move_toward(velocity.x, direction.x * speed, acceleration * delta)
	velocity.z = move_toward(velocity.z, direction.z * speed, acceleration * delta)
	if not is_on_floor():
		velocity.y -= _gravity * delta
	elif can_move and Input.is_action_just_pressed("jump"):
		velocity.y = jump_speed
	move_and_slide()
	if global_position.y < -12.0:
		respawn()


func respawn() -> void:
	global_transform = _spawn_transform
	velocity = Vector3.ZERO
	head.rotation = Vector3.ZERO
