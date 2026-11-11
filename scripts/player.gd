extends CharacterBody3D
## Distances are metres. Movement speeds are metres per second.

signal damaged(amount: float)
signal died
signal health_changed

@export_range(1.0, 10.0, 0.1) var walk_speed: float = 4.5
@export_range(1.0, 15.0, 0.1) var sprint_speed: float = 7.0
@export_range(1.0, 10.0, 0.1) var jump_speed: float = 4.5
@export_range(1.0, 40.0, 0.5) var acceleration: float = 18.0
@export_range(0.0001, 0.01, 0.0001) var mouse_sensitivity: float = 0.002

@onready var head: Node3D = $Head
@onready var camera: Camera3D = $Head/Camera3D

var _spawn_transform: Transform3D
var _gravity: float = float(ProjectSettings.get_setting("physics/3d/default_gravity", 9.8))
var _recoil_pitch: float = 0.0
var controls_enabled: bool = true
var health_enabled: bool = false
var max_health: float = 100.0
var health: float = 100.0
var stamina: float = 100.0
var max_stamina: float = 100.0
var bleeding: bool = false
var movement_multiplier: float = 1.0
var _damage_grace: float = 0.0
var _dead_emitted: bool = false


func _ready() -> void:
	_spawn_transform = global_transform
	# Headless checks do not need a mouse or a display.
	if DisplayServer.get_name() != "headless":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _unhandled_input(event: InputEvent) -> void:
	if controls_enabled and event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotate_y(-event.screen_relative.x * mouse_sensitivity)
		head.rotation.x = clampf(head.rotation.x - event.screen_relative.y * mouse_sensitivity, deg_to_rad(-85.0), deg_to_rad(85.0))


func _process(delta: float) -> void:
	_recoil_pitch = lerpf(_recoil_pitch, 0.0, 1.0 - exp(-12.0 * delta))
	camera.rotation.x = _recoil_pitch


func add_recoil(amount: float) -> void:
	_recoil_pitch = minf(_recoil_pitch + amount, deg_to_rad(5.0))


func _physics_process(delta: float) -> void:
	_damage_grace = maxf(0.0, _damage_grace - delta)
	if health_enabled and bleeding and health > 0.0:
		health = maxf(0.0, health - 0.65 * delta)
		health_changed.emit()
		_check_death()
	var can_move: bool = controls_enabled and (Input.mouse_mode == Input.MOUSE_MODE_CAPTURED or DisplayServer.get_name() == "headless")
	var input_vector: Vector2 = Vector2.ZERO
	if can_move:
		input_vector = Input.get_vector("move_left", "move_right", "move_forward", "move_backward")
	var direction: Vector3 = global_basis * Vector3(input_vector.x, 0.0, input_vector.y)
	var sprinting: bool = can_move and input_vector.length() > 0.1 and Input.is_action_pressed("sprint") and (not health_enabled or stamina > 2.0)
	if health_enabled:
		stamina = clampf(stamina + (-19.0 if sprinting else 13.0) * delta, 0.0, max_stamina)
	var speed: float = (sprint_speed if sprinting else walk_speed) * movement_multiplier
	if health_enabled and health < 25.0:
		speed *= 0.75
	velocity.x = move_toward(velocity.x, direction.x * speed, acceleration * delta)
	velocity.z = move_toward(velocity.z, direction.z * speed, acceleration * delta)
	if not is_on_floor():
		velocity.y -= _gravity * delta
	elif can_move and Input.is_action_just_pressed("jump"):
		velocity.y = jump_speed
	move_and_slide()
	if global_position.y < -12.0:
		if health_enabled:
			receive_damage(max_health, global_position)
		else:
			respawn()


func receive_damage(amount: float, _source: Vector3 = Vector3.ZERO) -> void:
	if not health_enabled or health <= 0.0 or _damage_grace > 0.0 or amount <= 0.0:
		return
	_damage_grace = 0.10
	var taken: float = minf(health, amount)
	health -= taken
	if health < 60.0 and taken >= 10.0:
		bleeding = true
	damaged.emit(taken)
	health_changed.emit()
	_check_death()


func heal(amount: float) -> void:
	if health <= 0.0:
		return
	health = minf(max_health, health + amount)
	bleeding = false
	health_changed.emit()


func _check_death() -> void:
	if health <= 0.0 and not _dead_emitted:
		_dead_emitted = true
		controls_enabled = false
		died.emit()


func set_spawn_transform(value: Transform3D) -> void:
	_spawn_transform = value


func respawn() -> void:
	global_transform = _spawn_transform
	velocity = Vector3.ZERO
	head.rotation = Vector3.ZERO
	_recoil_pitch = 0.0
	camera.rotation = Vector3.ZERO
	health = max_health
	stamina = max_stamina
	bleeding = false
	_damage_grace = 0.0
	_dead_emitted = false
	movement_multiplier = 1.0
	health_changed.emit()
