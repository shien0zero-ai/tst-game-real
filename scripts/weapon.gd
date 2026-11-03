extends Node3D
## Game-only hitscan pistol. One press fires one shot; magazines are unlimited.

signal shot_fired
signal target_hit(points: int)

@export var capacity: int = 7
@export var shot_interval: float = 0.18
@export var reload_duration: float = 1.35
@export var hip_position := Vector3(0.20, -0.12, -0.34)
@export var aim_position := Vector3(0.0, -0.029, -0.25)

@onready var camera: Camera3D = get_parent() as Camera3D
@onready var player: CharacterBody3D = get_node("../../..") as CharacterBody3D
@onready var visual: Node3D = $M1911Visual
@onready var slide: Node3D = $M1911Visual/Slide
@onready var magazine: Node3D = $M1911Visual/Magazine
@onready var muzzle: Marker3D = $M1911Visual/Muzzle
@onready var shot_sound: AudioStreamPlayer = $ShotSound
@onready var reload_sound: AudioStreamPlayer = $ReloadSound
@onready var empty_sound: AudioStreamPlayer = $EmptySound

var ammo: int = 7
var reloading: bool = false
var is_aiming: bool = false
var recoil_amount: float = 0.0
var _cooldown: float = 0.0
var _reload_remaining: float = 0.0
var _fire_requested: bool = false
var _slide_amount: float = 0.0
var _flash_remaining: float = 0.0
var _flash: MeshInstance3D
var _flash_light: OmniLight3D
var _magazine_rest: Vector3
var _wall_marks: Array[Node3D] = []


func _ready() -> void:
	ammo = capacity
	position = hip_position
	_magazine_rest = magazine.position
	# Keep the viewmodel readable under the shelter without lighting the world.
	for mesh: Node in visual.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).layers = 2
	_create_muzzle_flash()


func _unhandled_input(event: InputEvent) -> void:
	if not _has_control():
		return
	if event.is_action_pressed("shoot") and not event.is_echo():
		_fire_requested = true
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("reload") and not event.is_echo():
		begin_reload()
		get_viewport().set_input_as_handled()


func _physics_process(delta: float) -> void:
	_cooldown = maxf(0.0, _cooldown - delta)
	_flash_remaining = maxf(0.0, _flash_remaining - delta)
	if reloading:
		_reload_remaining -= delta
		if _reload_remaining <= 0.0:
			ammo = capacity
			reloading = false
	if _fire_requested:
		_fire_requested = false
		_fire()


func _process(delta: float) -> void:
	is_aiming = Input.is_action_pressed("aim") and _has_control() and not reloading
	var blend: float = 1.0 - exp(-15.0 * delta)
	var desired: Vector3 = aim_position if is_aiming else hip_position
	var reload_progress: float = 1.0 - _reload_remaining / reload_duration if reloading else 0.0
	var dip: float = sin(reload_progress * PI) if reloading else 0.0
	desired.y -= dip * 0.12
	desired.z += recoil_amount * 0.028
	position = position.lerp(desired, blend)
	rotation.x = (0.031 if is_aiming else 0.0) + recoil_amount * 0.11 - dip * 0.55
	rotation.z = -dip * 0.24
	recoil_amount = move_toward(recoil_amount, 0.0, delta * 7.0)
	_slide_amount = move_toward(_slide_amount, 0.0, delta * 15.0)
	# The slide stays back when the magazine is empty.
	slide.position.z = 0.028 * maxf(_slide_amount, 1.0 if ammo == 0 else 0.0)
	magazine.position = _magazine_rest + Vector3(0.0, -dip * 0.08, 0.0)
	camera.fov = lerpf(camera.fov, 57.0 if is_aiming else 75.0, blend)
	_flash.visible = _flash_remaining > 0.0
	_flash_light.visible = _flash.visible


func _has_control() -> bool:
	return Input.mouse_mode == Input.MOUSE_MODE_CAPTURED or DisplayServer.get_name() == "headless"


func _fire() -> void:
	if reloading or _cooldown > 0.0 or not _has_control():
		return
	_cooldown = shot_interval
	if ammo <= 0:
		_play_sound(empty_sound)
		return
	ammo -= 1
	recoil_amount = 1.0
	_slide_amount = 1.0
	_flash_remaining = 0.045
	_play_sound(shot_sound)
	shot_fired.emit()
	var origin: Vector3 = camera.global_position
	var destination: Vector3 = origin - camera.global_basis.z * 100.0
	var query := PhysicsRayQueryParameters3D.create(origin, destination, 5)
	query.exclude = [player.get_rid()]
	var result: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	if not result.is_empty():
		var collider: Object = result["collider"] as Object
		var point: Vector3 = result["position"]
		var normal: Vector3 = result["normal"]
		if collider.has_method("register_hit"):
			var points: int = int(collider.call("register_hit", point, normal))
			if points > 0:
				target_hit.emit(points)
		else:
			_add_wall_mark(point, normal)
	player.call("add_recoil", deg_to_rad(1.25))


func begin_reload() -> void:
	if reloading or ammo >= capacity:
		return
	reloading = true
	_reload_remaining = reload_duration
	_fire_requested = false
	_play_sound(reload_sound)


func _play_sound(sound: AudioStreamPlayer) -> void:
	# Headless servers have no audio output or mixer playback to maintain.
	if DisplayServer.get_name() != "headless":
		sound.play()


func reset_weapon() -> void:
	ammo = capacity
	reloading = false
	is_aiming = false
	_cooldown = 0.0
	_reload_remaining = 0.0
	_fire_requested = false
	recoil_amount = 0.0
	_slide_amount = 0.0
	_flash_remaining = 0.0
	slide.position.z = 0.0
	magazine.position = _magazine_rest
	position = hip_position
	rotation = Vector3.ZERO
	camera.fov = 75.0
	shot_sound.stop()
	reload_sound.stop()
	empty_sound.stop()
	for mark: Node3D in _wall_marks:
		if is_instance_valid(mark):
			mark.queue_free()
	_wall_marks.clear()


func _create_muzzle_flash() -> void:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color(1.0, 0.7, 0.22)
	material.emission_enabled = true
	material.emission = Color(1.0, 0.45, 0.05)
	material.emission_energy_multiplier = 3.0
	var mesh := SphereMesh.new()
	mesh.radius = 0.012
	mesh.height = 0.024
	mesh.radial_segments = 12
	mesh.rings = 6
	mesh.material = material
	_flash = MeshInstance3D.new()
	_flash.mesh = mesh
	_flash.scale = Vector3(0.9, 0.9, 2.7)
	_flash.position.z = -0.026
	_flash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_flash.visible = false
	muzzle.add_child(_flash)
	_flash_light = OmniLight3D.new()
	_flash_light.light_color = Color(1.0, 0.55, 0.15)
	_flash_light.light_energy = 2.5
	_flash_light.omni_range = 2.0
	_flash_light.visible = false
	muzzle.add_child(_flash_light)


func _add_wall_mark(point: Vector3, normal: Vector3) -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.09, 0.075, 0.06)
	material.roughness = 1.0
	var mesh := SphereMesh.new()
	mesh.radius = 0.012
	mesh.height = 0.024
	mesh.radial_segments = 8
	mesh.rings = 4
	mesh.material = material
	var mark := MeshInstance3D.new()
	mark.mesh = mesh
	get_tree().current_scene.add_child(mark)
	mark.global_position = point - normal * 0.005
	_wall_marks.append(mark)
	if _wall_marks.size() > 64:
		_wall_marks.pop_front().queue_free()
