extends CharacterBody3D
## Solo PvE guard: patrol, investigate noise, seek a last sighting and fire with LOS.

const GUARD_VISUAL = preload("res://scripts/raid_enemy_visual.gd")

@export var max_health: float = 80.0
@export var patrol_speed: float = 1.8
@export var chase_speed: float = 3.2
@export var detection_range: float = 30.0
@export var attack_range: float = 20.0
@export var shot_damage: float = 11.0
@export var shot_interval: float = 1.05
@export var model_yaw_degrees: float = 0.0

var session: Node
var patrol_route := PackedVector3Array()
var enemy_id: int = 0
var display_name: String = "警備員"
var health: float = 80.0
var is_dead: bool = false
var state: String = "patrol"

var _visual: Node3D
var _body_collision: CollisionShape3D
var _player: Node3D
var _spawn_position := Vector3.ZERO
var _last_known := Vector3.ZERO
var _memory_left: float = 0.0
var _reaction_left: float = 0.0
var _shot_left: float = 0.0
var _sense_left: float = 0.0
var _path_left: float = 0.0
var _search_left: float = 0.0
var _visible_player: bool = false
var _patrol_index: int = 0
var _path := PackedVector3Array()
var _path_index: int = 0
var _path_goal := Vector3.INF
var _rng := RandomNumberGenerator.new()
var _gravity: float = 9.8


func _ready() -> void:
	add_to_group("raid_enemies")
	collision_layer = 4
	collision_mask = 7
	floor_snap_length = 0.4
	_spawn_position = global_position
	health = max_health
	_rng.seed = 73121 + enemy_id * 15427
	_shot_left = 0.5 + _rng.randf_range(0.0, 0.6)
	_sense_left = _rng.randf_range(0.0, 0.15)
	_gravity = float(ProjectSettings.get_setting("physics/3d/default_gravity", 9.8))
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.32
	capsule.height = 1.72
	_body_collision = CollisionShape3D.new()
	_body_collision.name = "BodyCollision"
	_body_collision.shape = capsule
	_body_collision.position.y = 0.86
	add_child(_body_collision)
	_visual = GUARD_VISUAL.new() as Node3D
	_visual.set("model_yaw_degrees", model_yaw_degrees)
	add_child(_visual)
	if patrol_route.is_empty():
		patrol_route = PackedVector3Array([position, position + Vector3(0, 0, -4)])


func _raid_active() -> bool:
	return is_instance_valid(session) and String(session.get("phase")) == "raid"


func _physics_process(delta: float) -> void:
	if is_dead:
		return
	var player_value: Variant = session.get("player") if is_instance_valid(session) else null
	_player = player_value as Node3D
	_shot_left = maxf(0.0, _shot_left - delta)
	_reaction_left = maxf(0.0, _reaction_left - delta)
	_path_left = maxf(0.0, _path_left - delta)
	_sense_left -= delta
	_memory_left = maxf(0.0, _memory_left - delta)
	var desired_velocity := Vector3.ZERO
	if _raid_active() and is_instance_valid(_player):
		if _sense_left <= 0.0:
			_sense_left = 0.18
			_sense_player()
		var goal: Vector3 = global_position
		var movement_speed: float = patrol_speed
		if _visible_player:
			_face_towards(_player.global_position, delta)
			var distance: float = _flat_distance(global_position, _player.global_position)
			if distance > attack_range:
				_set_state("chase")
				goal = _player.global_position
				movement_speed = chase_speed
			else:
				_set_state("attack")
				if distance < 3.3:
					goal = global_position + (global_position - _player.global_position).normalized() * 2.2
					movement_speed = patrol_speed
				if _reaction_left <= 0.0 and _shot_left <= 0.0:
					_attempt_shot()
		elif _memory_left > 0.0:
			if _flat_distance(global_position, _last_known) > 1.2:
				_set_state("chase" if state == "chase" else "investigate")
				goal = _last_known
				movement_speed = chase_speed if state == "chase" else patrol_speed
			else:
				_set_state("investigate")
				_search_left += delta
				rotation.y += sin(_search_left * 1.1 + enemy_id) * delta * 0.65
		else:
			_set_state("patrol")
			goal = patrol_route[_patrol_index]
			if _flat_distance(global_position, goal) < 0.8:
				_patrol_index = (_patrol_index + 1) % patrol_route.size()
				goal = patrol_route[_patrol_index]
		if _flat_distance(global_position, goal) > 0.6:
			desired_velocity = _direction_to_goal(goal) * movement_speed
			if not _visible_player:
				_face_direction(desired_velocity, delta)
	velocity.x = move_toward(velocity.x, desired_velocity.x, delta * 12.0)
	velocity.z = move_toward(velocity.z, desired_velocity.z, delta * 12.0)
	if not is_on_floor():
		velocity.y -= _gravity * delta
	else:
		velocity.y = 0.0
	move_and_slide()
	if global_position.y < -10.0:
		global_position = _spawn_position
		velocity = Vector3.ZERO
	var planar_speed: float = Vector2(velocity.x, velocity.z).length()
	_visual.call("set_motion", planar_speed, state != "patrol")
	_visual.call("animate_fallback", delta, planar_speed)


func _sense_player() -> void:
	var was_visible: bool = _visible_player
	_visible_player = _can_see_player()
	if _visible_player:
		_last_known = _player.global_position
		_memory_left = 8.0
		_search_left = 0.0
		if not was_visible:
			_reaction_left = 0.58 + _rng.randf_range(0.0, 0.20)
		return
	if was_visible:
		_set_state("chase")
	if is_instance_valid(session) and session.has_method("get_player_noise"):
		var noise: float = clampf(float(session.call("get_player_noise")), 0.0, 1.0)
		if noise > 0.15 and global_position.distance_to(_player.global_position) < 3.5 + noise * 10.5:
			hear_noise(_player.global_position, 15.0)


func _can_see_player() -> bool:
	if not is_instance_valid(_player):
		return false
	var to_player: Vector3 = _player.global_position - global_position
	if to_player.length() > detection_range:
		return false
	var flat := Vector3(to_player.x, 0.0, to_player.z)
	if flat.length() > 0.1 and _memory_left <= 0.0:
		var forward := -global_basis.z
		if forward.dot(flat.normalized()) < 0.20:
			return false
	var eye: Vector3 = global_position + Vector3(0, 1.48, 0)
	var player_eye: Vector3 = _player.global_position + Vector3(0, 1.5, 0)
	var camera := _player.get_node_or_null("Head/Camera3D") as Node3D
	if camera != null:
		player_eye = camera.global_position
	var query := PhysicsRayQueryParameters3D.create(eye, player_eye, 3)
	query.exclude = [get_rid()]
	query.hit_from_inside = true
	var result: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	return not result.is_empty() and result.get("collider") == _player


func _direction_to_goal(goal: Vector3) -> Vector3:
	if _path_left <= 0.0 or _path_goal.distance_to(goal) > 2.5:
		_path_left = 0.85 + enemy_id * 0.025
		_path_goal = goal
		_path_index = 0
		_path = PackedVector3Array()
		if is_instance_valid(session) and session.has_method("get_navigation_path"):
			var result: Variant = session.call("get_navigation_path", global_position, goal)
			if result is PackedVector3Array:
				_path = result
		elif _path.is_empty():
			_path = PackedVector3Array([goal])
	while _path_index < _path.size() and _flat_distance(global_position, _path[_path_index]) < 0.6:
		_path_index += 1
	# A partial path can end at the nearest reachable point. Wait there rather
	# than walking straight into the wall separating us from the remembered goal.
	if _path_index >= _path.size():
		return Vector3.ZERO
	var next: Vector3 = _path[_path_index]
	var direction := Vector3(next.x - global_position.x, 0.0, next.z - global_position.z)
	return direction.normalized() if direction.length_squared() > 0.01 else Vector3.ZERO


func _face_towards(target: Vector3, delta: float) -> void:
	_face_direction(target - global_position, delta)


func _face_direction(direction: Vector3, delta: float) -> void:
	if Vector2(direction.x, direction.z).length_squared() < 0.001:
		return
	var angle: float = atan2(-direction.x, -direction.z)
	rotation.y = lerp_angle(rotation.y, angle, 1.0 - exp(-7.0 * delta))


func _attempt_shot() -> void:
	_shot_left = shot_interval + _rng.randf_range(-0.12, 0.24)
	if not _raid_active() or not _can_see_player():
		return
	var origin: Vector3 = _visual.call("muzzle_position")
	var target: Vector3 = _player.global_position + Vector3(0, 1.12, 0)
	var distance: float = origin.distance_to(target)
	var hit_chance: float = clampf(0.86 - distance * 0.018, 0.34, 0.80)
	if _rng.randf() > hit_chance:
		var side: Vector3 = global_basis.x
		target += side * _rng.randf_range(0.7, 1.4) * (-1.0 if _rng.randf() < 0.5 else 1.0)
		target.y += _rng.randf_range(-0.30, 0.55)
	var query := PhysicsRayQueryParameters3D.create(origin, target, 7)
	query.exclude = [get_rid()]
	query.hit_from_inside = true
	var result: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	var impact: Vector3 = result.get("position", target)
	_visual.call("show_shot", impact)
	if not result.is_empty() and result.get("collider") == _player and _player.has_method("receive_damage"):
		_player.call("receive_damage", shot_damage, global_position)


func hear_noise(origin: Vector3, radius: float = 28.0) -> void:
	if is_dead or not _raid_active() or global_position.distance_to(origin) > radius:
		return
	_last_known = origin
	_memory_left = maxf(_memory_left, 6.0)
	_search_left = 0.0
	if not _visible_player:
		_set_state("investigate")


func alert_to(origin: Vector3) -> void:
	hear_noise(origin, 35.0)


func register_hit(point: Vector3, _normal: Vector3) -> int:
	if is_dead or not _raid_active():
		return 0
	var headshot: bool = point.y - global_position.y > 1.45
	health = maxf(0.0, health - (90.0 if headshot else 44.0))
	if health <= 0.0:
		_die()
		return 40
	var value: Variant = session.get("player") if is_instance_valid(session) else null
	if value is Node3D:
		_last_known = (value as Node3D).global_position
		_memory_left = 8.0
		_reaction_left = maxf(_reaction_left, 0.35)
		_sense_left = 0.0
		_set_state("chase")
	return 10


func _die() -> void:
	if is_dead:
		return
	is_dead = true
	health = 0.0
	velocity = Vector3.ZERO
	_visible_player = false
	_set_state("dead")
	set_deferred("collision_layer", 0)
	_body_collision.set_deferred("disabled", true)
	_visual.call("die")
	if is_instance_valid(session) and session.has_method("on_enemy_killed"):
		session.call("on_enemy_killed", self)


func get_body_loot_position() -> Vector3:
	return global_position + Vector3(0, 0.16, 0)


func _set_state(next: String) -> void:
	if state == next:
		return
	state = next
	if is_instance_valid(session) and session.has_method("report_enemy_state"):
		session.call("report_enemy_state", self, state)


func _flat_distance(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x - b.x, a.z - b.z).length()
