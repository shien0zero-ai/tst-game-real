extends Node3D
## World-space presentation for a guard. Gameplay remains in raid_enemy.gd.

const MODEL_PATH := "res://assets/raid/enemy.glb"
const PISTOL = preload("res://scenes/m1911_visual.tscn")
const SHOT = preload("res://assets/audio/pistol_shot.wav")

var model_yaw_degrees: float = 0.0

var _animation: AnimationPlayer
var _idle: StringName = &""
var _walk: StringName = &""
var _run: StringName = &""
var _death: StringName = &""
var _skeleton: Skeleton3D
var _right_hand: int = -1
var _gun_holder: Node3D
var _muzzle: Node3D
var _flash: MeshInstance3D
var _shot_audio: AudioStreamPlayer3D
var _tracer: MeshInstance3D
var _tracer_mesh: ImmediateMesh
var _tracer_material: StandardMaterial3D
var _flash_left: float = 0.0
var _tracer_left: float = 0.0
var _dead: bool = false
var _death_elapsed: float = 0.0
var _step_phase: float = 0.0
var _fallback_legs: Array[Node3D] = []


func _ready() -> void:
	name = "GuardVisual"
	# Follow the hand after the imported AnimationPlayer has evaluated its pose.
	process_priority = 20
	_build_body()
	_build_weapon()
	set_motion(0.0, false)


func _build_body() -> void:
	var packed: PackedScene
	if ResourceLoader.exists(MODEL_PATH):
		packed = load(MODEL_PATH) as PackedScene
	if packed == null:
		_build_fallback()
		return
	var model := packed.instantiate() as Node3D
	var anchor := Node3D.new()
	anchor.name = "ModelScale"
	add_child(anchor)
	var centering := Node3D.new()
	centering.name = "FeetOrigin"
	anchor.add_child(centering)
	centering.add_child(model)
	var boxes: Array[AABB] = []
	_collect_bounds(model, Transform3D.IDENTITY, boxes)
	if not boxes.is_empty():
		var bounds: AABB = boxes[0]
		for index: int in range(1, boxes.size()):
			bounds = bounds.merge(boxes[index])
		var height: float = maxf(0.01, bounds.size.y)
		anchor.scale = Vector3.ONE * (1.72 / height)
		centering.position = -Vector3(bounds.get_center().x, bounds.position.y, bounds.get_center().z)
	anchor.rotation.y = deg_to_rad(model_yaw_degrees)
	var players: Array[Node] = model.find_children("*", "AnimationPlayer", true, false)
	if not players.is_empty():
		_animation = players[0] as AnimationPlayer
		_idle = _find_animation(["aim_idle", "idle"])
		_walk = _find_animation(["aim_walk", "walk"])
		_run = _find_animation(["aim_run", "run", "jog", "sprint"])
		_death = _find_animation(["death", "dying", "dead"])
		for clip: StringName in [_idle, _walk, _run]:
			if clip != &"":
				_animation.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
		if _death != &"":
			_animation.get_animation(_death).loop_mode = Animation.LOOP_NONE
	var skeletons: Array[Node] = model.find_children("*", "Skeleton3D", true, false)
	if not skeletons.is_empty():
		_skeleton = skeletons[0] as Skeleton3D
		var letters := RegEx.create_from_string("[^a-z]")
		for index: int in _skeleton.get_bone_count():
			var bone_key: String = letters.sub(_skeleton.get_bone_name(index).to_lower(), "", true)
			if bone_key.ends_with("righthand") or bone_key.ends_with("handr"):
				_right_hand = index
				break


func _collect_bounds(node: Node3D, parent: Transform3D, boxes: Array[AABB]) -> void:
	var transform_in_model: Transform3D = parent * node.transform
	if node is MeshInstance3D and node.mesh != null:
		boxes.append(transform_in_model * node.mesh.get_aabb())
	for child: Node in node.get_children():
		if child is Node3D:
			_collect_bounds(child as Node3D, transform_in_model, boxes)


func _find_animation(words: Array[String]) -> StringName:
	for word: String in words:
		for candidate: StringName in _animation.get_animation_list():
			if String(candidate).to_lower().contains(word):
				return candidate
	return &""


func _material(color: Color, roughness: float = 0.86, metallic: float = 0.0) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	material.metallic = metallic
	return material


func _part(mesh: Mesh, position_value: Vector3, material: Material, parent: Node3D = self) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.mesh = mesh
	node.material_override = material
	node.position = position_value
	parent.add_child(node)
	return node


func _capsule(radius: float, height: float) -> CapsuleMesh:
	var mesh := CapsuleMesh.new()
	mesh.radius = radius
	mesh.height = height
	mesh.radial_segments = 12
	mesh.rings = 4
	return mesh


func _build_fallback() -> void:
	# Used only while an optional model is unavailable during authoring/tests.
	var cloth := _material(Color(0.18, 0.22, 0.18))
	var armor := _material(Color(0.105, 0.125, 0.115))
	var boots := _material(Color(0.055, 0.058, 0.05))
	var skin := _material(Color(0.32, 0.26, 0.20))
	_part(_capsule(0.23, 0.67), Vector3(0, 1.10, 0), cloth)
	var plate := BoxMesh.new()
	plate.size = Vector3(0.39, 0.43, 0.17)
	_part(plate, Vector3(0, 1.17, -0.16), armor)
	_part(_capsule(0.145, 0.30), Vector3(0, 1.54, -0.005), skin)
	_part(_capsule(0.165, 0.23), Vector3(0, 1.64, 0.015), armor)
	for side: float in [-1.0, 1.0]:
		var leg := Node3D.new()
		leg.position = Vector3(side * 0.115, 0.74, 0)
		add_child(leg)
		_part(_capsule(0.10, 0.64), Vector3(0, -0.30, 0), cloth, leg)
		var boot := BoxMesh.new()
		boot.size = Vector3(0.16, 0.17, 0.30)
		_part(boot, Vector3(0, -0.65, -0.055), boots, leg)
		_fallback_legs.append(leg)
		var arm := _part(_capsule(0.085, 0.51), Vector3(side * 0.24, 1.16, -0.13), cloth)
		arm.rotation.x = deg_to_rad(-43)


func _build_weapon() -> void:
	_gun_holder = Node3D.new()
	_gun_holder.name = "HeldPistol"
	_gun_holder.position = Vector3(0.23, 1.18, -0.18)
	add_child(_gun_holder)
	var pistol := PISTOL.instantiate() as Node3D
	_gun_holder.add_child(pistol)
	_muzzle = pistol.get_node("Muzzle") as Node3D
	var flash_material := StandardMaterial3D.new()
	flash_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	flash_material.albedo_color = Color(1, 0.68, 0.20)
	flash_material.emission_enabled = true
	flash_material.emission = Color(1, 0.40, 0.05)
	flash_material.emission_energy_multiplier = 2.0
	var flash_mesh := SphereMesh.new()
	flash_mesh.radius = 0.025
	flash_mesh.height = 0.06
	flash_mesh.radial_segments = 8
	flash_mesh.rings = 4
	_flash = _part(flash_mesh, Vector3.ZERO, flash_material, _muzzle)
	_flash.visible = false
	_flash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_shot_audio = AudioStreamPlayer3D.new()
	_shot_audio.stream = SHOT
	_shot_audio.volume_db = -15.0
	_shot_audio.unit_size = 7.0
	_shot_audio.max_distance = 55.0
	_muzzle.add_child(_shot_audio)
	_tracer_material = StandardMaterial3D.new()
	_tracer_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_tracer_material.albedo_color = Color(1, 0.76, 0.37)
	_tracer_material.emission_enabled = true
	_tracer_material.emission = Color(1, 0.49, 0.12)
	_tracer = MeshInstance3D.new()
	_tracer_mesh = ImmediateMesh.new()
	_tracer.mesh = _tracer_mesh
	_tracer.visible = false
	_tracer.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_tracer)


func muzzle_position() -> Vector3:
	return _muzzle.global_position if is_instance_valid(_muzzle) else global_position + Vector3(0, 1.25, -0.35)


func show_shot(impact: Vector3) -> void:
	_flash_left = 0.06
	_tracer_left = 0.075
	if is_instance_valid(_shot_audio) and DisplayServer.get_name() != "headless":
		_shot_audio.pitch_scale = randf_range(0.94, 1.06)
		_shot_audio.play()
	if is_instance_valid(_tracer_mesh):
		_tracer_mesh.clear_surfaces()
		_tracer_mesh.surface_begin(Mesh.PRIMITIVE_LINES, _tracer_material)
		_tracer_mesh.surface_add_vertex(to_local(muzzle_position()))
		_tracer_mesh.surface_add_vertex(to_local(impact))
		_tracer_mesh.surface_end()


func set_motion(speed: float, alert: bool) -> void:
	if _dead or not is_instance_valid(_animation):
		return
	var desired: StringName = _idle
	if speed > 0.25:
		desired = _run if speed > 2.6 and _run != &"" else _walk
	if desired == &"":
		if _walk != &"" and speed <= 0.25:
			if _animation.current_animation != _walk:
				_animation.play(_walk)
				_animation.seek(0.15, true)
			_animation.pause()
		return
	if _animation.current_animation != desired or not _animation.is_playing():
		_animation.play(desired, 0.18)
	_animation.speed_scale = clampf(speed / (3.2 if desired == _run else 1.7), 0.65, 1.35) if speed > 0.25 else 1.0


func die() -> void:
	_dead = true
	if is_instance_valid(_animation) and _death != &"":
		_animation.speed_scale = 1.0
		_animation.play(_death, 0.12)
	elif is_instance_valid(_animation):
		_animation.pause()
	if is_instance_valid(_gun_holder):
		_gun_holder.top_level = true
		_gun_holder.global_transform = Transform3D(
			global_basis * Basis.from_euler(Vector3(0, PI * 0.25, PI * 0.5)),
			to_global(Vector3(0.30, 0.12, -0.18))
		)


func _process(delta: float) -> void:
	if not _dead and is_instance_valid(_skeleton) and _right_hand >= 0 and is_instance_valid(_gun_holder):
		var hand: Vector3 = (_skeleton.global_transform * _skeleton.get_bone_global_pose(_right_hand)).origin
		# The visual's origin is level with the slide, above and in front of the
		# backstrap. Keep the grip in the animated palm as the guard walks.
		_gun_holder.global_position = hand + global_basis * Vector3(0.0, 0.075, -0.055)
	_flash_left = maxf(0.0, _flash_left - delta)
	_tracer_left = maxf(0.0, _tracer_left - delta)
	if is_instance_valid(_flash):
		_flash.visible = _flash_left > 0.0
	if is_instance_valid(_tracer):
		_tracer.visible = _tracer_left > 0.0
	if _dead and _death == &"":
		_death_elapsed += delta
		var blend: float = smoothstep(0.0, 0.65, _death_elapsed)
		rotation.x = -PI * 0.5 * blend
		position.y = 0.13 * blend


func animate_fallback(delta: float, speed: float) -> void:
	if _dead:
		return
	_step_phase += delta * speed * 3.8
	for index: int in _fallback_legs.size():
		_fallback_legs[index].rotation.x = sin(_step_phase + index * PI) * minf(speed / 3.2, 1.0) * 0.38
