extends Node3D
## DEPOT 04: one connected industrial raid map. Coordinates are metres.

const CELL_SIZE: float = 0.5
const GRID_ORIGIN := Vector2(-46.0, -42.0)
const GRID_SIZE := Vector2i(185, 169)
const CLEARANCE: float = 0.45
const SPAWN := Vector3(-36.0, 0.1, 34.0)
const EXTRACTION := Vector3(37.0, 0.0, -38.0)
const MATERIAL_DIRECTORY := "res://assets/raid/materials/"
const PROP_DIRECTORY := "res://assets/raid/models/"

var _materials: Dictionary = {}
var _surfaces: Dictionary = {}
var _obstacles: Array[AABB] = []
var _footprints: Array[Rect2] = []
var _grid := AStarGrid2D.new()
var _solids: StaticBody3D
var _props: Node3D
var _signs: Node3D
var _piece_count: int = 0
var _box_arrays: Array = []
var _cylinder_arrays: Array = []
var _wire_arrays: Array = []
var _ready_map: bool = false


func _ready() -> void:
	_build_materials()
	var unit_box := BoxMesh.new()
	unit_box.size = Vector3.ONE
	_box_arrays = unit_box.get_mesh_arrays()
	var unit_cylinder := CylinderMesh.new()
	unit_cylinder.top_radius = 0.5
	unit_cylinder.bottom_radius = 0.5
	unit_cylinder.height = 1.0
	unit_cylinder.radial_segments = 16
	_cylinder_arrays = unit_cylinder.get_mesh_arrays()
	unit_cylinder = CylinderMesh.new()
	unit_cylinder.top_radius = 0.5
	unit_cylinder.bottom_radius = 0.5
	unit_cylinder.height = 1.0
	unit_cylinder.radial_segments = 4
	_wire_arrays = unit_cylinder.get_mesh_arrays()
	_solids = StaticBody3D.new()
	_solids.name = "DepotCollision"
	_solids.collision_layer = 1
	_solids.collision_mask = 0
	add_child(_solids)
	_props = Node3D.new()
	_props.name = "Props"
	add_child(_props)
	_signs = Node3D.new()
	_signs.name = "Signs"
	add_child(_signs)
	_build_environment()
	_build_ground()
	_build_perimeter()
	_build_warehouse()
	_build_office()
	_build_workshop()
	_build_containers()
	_build_checkpoint()
	_build_yard()
	_build_extraction()
	_build_background()
	_commit_geometry()
	_build_navigation()
	_ready_map = true


func get_spawn_transform() -> Transform3D:
	return global_transform * Transform3D(Basis.IDENTITY, SPAWN)


func get_extraction_position() -> Vector3:
	return to_global(EXTRACTION)


func get_map_name() -> String:
	return "DEPOT 04 / FREIGHT TERMINAL"


func get_bounds() -> AABB:
	return AABB(Vector3(-48, -1, -44), Vector3(96, 12, 88))


func get_landmarks() -> Array[Dictionary]:
	return [
		{"name": "SOUTH CHECKPOINT", "position": to_global(Vector3(-36, 0, 33))},
		{"name": "WAREHOUSE A", "position": to_global(Vector3(0, 0, -4))},
		{"name": "MEDICAL OFFICE", "position": to_global(Vector3(-28, 0, -12))},
		{"name": "SERVICE WORKSHOP", "position": to_global(Vector3(31, 0, 1))},
		{"name": "NORTH EXTRACTION", "position": get_extraction_position()},
	]


func get_enemy_spawns() -> Array[Dictionary]:
	var spawns: Array[Dictionary] = [
		{"name": "Yard patrol", "position": Vector3(-10, 0.1, 17), "route": PackedVector3Array([Vector3(-10, 0, 17), Vector3(3, 0, 17), Vector3(3, 0, 24), Vector3(-10, 0, 24)])},
		{"name": "Warehouse west", "position": Vector3(-7, 0.12, 3), "route": PackedVector3Array([Vector3(-7, 0, 3), Vector3(-7, 0, -13), Vector3(-4, 0, -13), Vector3(-4, 0, 3)])},
		{"name": "Warehouse east", "position": Vector3(7, 0.12, -10), "route": PackedVector3Array([Vector3(7, 0, -10), Vector3(7, 0, 5), Vector3(4, 0, 5), Vector3(4, 0, -10)])},
		{"name": "Office guard", "position": Vector3(-25, 0.12, -16), "route": PackedVector3Array([Vector3(-25, 0, -16), Vector3(-32, 0, -16), Vector3(-28, 0, -8), Vector3(-23, 0, -7)])},
		{"name": "North cargo", "position": Vector3(-28, 0.1, -32), "route": PackedVector3Array([Vector3(-28, 0, -38), Vector3(-28, 0, -28), Vector3(-20, 0, -24), Vector3(-20, 0, -36)])},
		{"name": "Workshop guard", "position": Vector3(31, 0.12, 2), "route": PackedVector3Array([Vector3(25, 0, 2), Vector3(35, 0, 2), Vector3(35, 0, 7), Vector3(26, 0, 7)])},
		{"name": "South cargo", "position": Vector3(29, 0.1, 24), "route": PackedVector3Array([Vector3(29, 0, 18), Vector3(29, 0, 29), Vector3(37, 0, 29), Vector3(37, 0, 18)])},
		{"name": "North gate guard", "position": Vector3(31, 0.1, -31), "route": PackedVector3Array([Vector3(25, 0, -31), Vector3(40, 0, -31), Vector3(40, 0, -23), Vector3(25, 0, -23)])},
	]
	for entry: Dictionary in spawns:
		entry["position"] = to_global(entry["position"])
		var route := PackedVector3Array()
		for point: Vector3 in entry["route"]:
			route.append(to_global(point))
		entry["route"] = route
	return spawns


func get_loot_spawns() -> Array[Dictionary]:
	# Container origins are on the ground; the session adds its own mesh/trigger.
	var spawns: Array[Dictionary] = [
		{"position": Vector3(-33, 0.03, 27), "kind": "ammo", "label": "CHECKPOINT AMMUNITION"},
		{"position": Vector3(-35, 0.04, -16), "kind": "medical", "label": "CLINIC SUPPLIES"},
		{"position": Vector3(-23, 0.04, -16), "kind": "valuable", "label": "OFFICE DOCUMENTS"},
		{"position": Vector3(-10.5, 0.04, 7), "kind": "weapon", "label": "WAREHOUSE WEAPONS"},
		{"position": Vector3(-10.5, 0.04, -15), "kind": "ammo", "label": "WAREHOUSE AMMUNITION"},
		{"position": Vector3(0, 0.04, -17), "kind": "valuable", "label": "SEALED FREIGHT"},
		{"position": Vector3(10.5, 0.04, 4), "kind": "supplies", "label": "WAREHOUSE PARTS"},
		{"position": Vector3(-29, 0.03, -37), "kind": "supplies", "label": "NORTH CARGO"},
		{"position": Vector3(24, 0.04, -4), "kind": "medical", "label": "WORKSHOP FIRST AID"},
		{"position": Vector3(37, 0.04, 7), "kind": "valuable", "label": "WORKSHOP ELECTRONICS"},
		{"position": Vector3(29, 0.03, 17), "kind": "ammo", "label": "SOUTH CARGO AMMUNITION"},
		{"position": Vector3(37, 0.03, 27), "kind": "supplies", "label": "SOUTH CARGO"},
		{"position": Vector3(27, 0.03, -26), "kind": "medical", "label": "GATE FIRST AID"},
	]
	for entry: Dictionary in spawns:
		entry["position"] = to_global(entry["position"])
	return spawns


func find_path(from: Vector3, to: Vector3) -> PackedVector3Array:
	if not _ready_map:
		return PackedVector3Array()
	var local_from: Vector3 = to_local(from)
	var local_to: Vector3 = to_local(to)
	var start: Vector2i = _nearest_free(_grid_id(local_from))
	var finish: Vector2i = _nearest_free(_grid_id(local_to))
	if not _grid.is_in_boundsv(start) or not _grid.is_in_boundsv(finish):
		return PackedVector3Array()
	if _line_walkable(local_from, local_to):
		return PackedVector3Array([to_global(Vector3(local_to.x, 0.04, local_to.z))])
	var ids: Array[Vector2i] = _grid.get_id_path(start, finish, true)
	if ids.is_empty():
		return PackedVector3Array()
	var points := PackedVector3Array()
	for point: Vector2i in ids:
		points.append(Vector3(GRID_ORIGIN.x + point.x * CELL_SIZE, 0.04, GRID_ORIGIN.y + point.y * CELL_SIZE))
	# String-pull within the same inflated collision footprint, keeping AI turns
	# smooth without allowing diagonals through door jambs or storage racks.
	var result := PackedVector3Array()
	var anchor: Vector3 = local_from
	var cursor: int = 0
	while cursor < points.size():
		var farthest: int = cursor
		for candidate: int in range(cursor + 1, points.size()):
			if _line_walkable(anchor, points[candidate]):
				farthest = candidate
			else:
				break
		result.append(to_global(points[farthest]))
		anchor = points[farthest]
		cursor = farthest + 1
	if _line_walkable(anchor, local_to):
		result.append(to_global(Vector3(local_to.x, 0.04, local_to.z)))
	return result


func is_walkable_position(point: Vector3) -> bool:
	return _point_walkable(to_local(point))


func _grid_id(point: Vector3) -> Vector2i:
	return Vector2i(roundi((point.x - GRID_ORIGIN.x) / CELL_SIZE), roundi((point.z - GRID_ORIGIN.y) / CELL_SIZE))


func _nearest_free(point: Vector2i) -> Vector2i:
	point.x = clampi(point.x, 0, GRID_SIZE.x - 1)
	point.y = clampi(point.y, 0, GRID_SIZE.y - 1)
	if not _grid.is_point_solid(point):
		return point
	for radius: int in range(1, 8):
		var best := Vector2i(-1, -1)
		var best_distance: float = INF
		for x: int in range(point.x - radius, point.x + radius + 1):
			for z: int in range(point.y - radius, point.y + radius + 1):
				var candidate := Vector2i(x, z)
				if not _grid.is_in_boundsv(candidate) or _grid.is_point_solid(candidate):
					continue
				var distance: float = Vector2(candidate - point).length_squared()
				if distance < best_distance:
					best = candidate
					best_distance = distance
		if best.x >= 0:
			return best
	return Vector2i(-1, -1)


func _point_walkable(point: Vector3) -> bool:
	if point.x < -46.9 or point.x > 46.9 or point.z < -42.9 or point.z > 42.9:
		return false
	for bounds: Rect2 in _footprints:
		if point.x >= bounds.position.x and point.x <= bounds.end.x and point.z >= bounds.position.y and point.z <= bounds.end.y:
			return false
	return true


func _line_walkable(from: Vector3, to: Vector3) -> bool:
	if minf(from.x, to.x) < -46.9 or maxf(from.x, to.x) > 46.9 or minf(from.z, to.z) < -42.9 or maxf(from.z, to.z) > 42.9:
		return false
	# Exact segment/rectangle slabs prevent thin walls and clipped rack corners
	# from disappearing between samples when the grid path is simplified.
	var a := Vector2(from.x, from.z)
	var direction := Vector2(to.x - from.x, to.z - from.z)
	var segment_min := Vector2(minf(from.x, to.x), minf(from.z, to.z))
	var segment_max := Vector2(maxf(from.x, to.x), maxf(from.z, to.z))
	for bounds: Rect2 in _footprints:
		if bounds.position.x > segment_max.x or bounds.end.x < segment_min.x or bounds.position.y > segment_max.y or bounds.end.y < segment_min.y:
			continue
		var enter: float = 0.0
		var leave: float = 1.0
		var intersects: bool = true
		for axis: int in 2:
			if absf(direction[axis]) < 0.000001:
				if a[axis] < bounds.position[axis] or a[axis] > bounds.end[axis]:
					intersects = false
					break
			else:
				var near: float = (bounds.position[axis] - a[axis]) / direction[axis]
				var far: float = (bounds.end[axis] - a[axis]) / direction[axis]
				enter = maxf(enter, minf(near, far))
				leave = minf(leave, maxf(near, far))
				if enter > leave:
					intersects = false
					break
		if intersects:
			return false
	return true


func _build_navigation() -> void:
	_grid.region = Rect2i(Vector2i.ZERO, GRID_SIZE)
	_grid.cell_size = Vector2(CELL_SIZE, CELL_SIZE)
	_grid.offset = GRID_ORIGIN
	_grid.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	_grid.default_compute_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	_grid.default_estimate_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	_grid.update()
	# Rasterize each inflated obstacle instead of testing every map cell against
	# every obstacle. The fine grid then remains inexpensive to build at startup.
	for bounds: Rect2 in _footprints:
		var first := Vector2i(ceili((bounds.position.x - GRID_ORIGIN.x) / CELL_SIZE), ceili((bounds.position.y - GRID_ORIGIN.y) / CELL_SIZE))
		var last := Vector2i(floori((bounds.end.x - GRID_ORIGIN.x) / CELL_SIZE), floori((bounds.end.y - GRID_ORIGIN.y) / CELL_SIZE))
		first = first.max(Vector2i.ZERO)
		last = last.min(GRID_SIZE - Vector2i.ONE)
		for x: int in range(first.x, last.x + 1):
			for z: int in range(first.y, last.y + 1):
				_grid.set_point_solid(Vector2i(x, z), true)


func _build_materials() -> void:
	_materials["asphalt"] = _surface_material("asphalt", Color(0.16, 0.17, 0.17), 0.95)
	_materials["concrete"] = _surface_material("concrete", Color(0.46, 0.46, 0.42), 0.93)
	_materials["brick"] = _surface_material("brick", Color(0.36, 0.25, 0.19), 0.95)
	_materials["steel"] = _surface_material("steel", Color(0.23, 0.26, 0.25), 0.79, 0.72)
	_materials["corrugated"] = _surface_material("corrugated", Color(0.31, 0.35, 0.31), 0.86, 0.55)
	_materials["wood"] = _surface_material("wood", Color(0.25, 0.18, 0.11), 0.91)
	# Keep the sunlit road below the bright concrete markings, with a restrained
	# normal map so distant asphalt does not sparkle during movement.
	_materials["asphalt"] = _materials["asphalt"].duplicate()
	_materials["asphalt"].albedo_color = Color(0.62, 0.62, 0.62)
	_materials["asphalt"].normal_scale = 0.30
	_materials["extraction_paint"] = _materials["asphalt"].duplicate()
	_materials["extraction_paint"].albedo_color = Color(0.26, 0.39, 0.28)
	_materials["trim"] = _plain_material(Color(0.11, 0.14, 0.14), 0.75, 0.7)
	_materials["rust"] = _plain_material(Color(0.27, 0.16, 0.095), 0.94, 0.45)
	_materials["yellow"] = _plain_material(Color(0.65, 0.46, 0.17), 0.93)
	_materials["white"] = _plain_material(Color(0.72, 0.72, 0.65), 0.94)
	_materials["red"] = _plain_material(Color(0.38, 0.095, 0.055), 0.9, 0.15)
	_materials["blue"] = _plain_material(Color(0.12, 0.23, 0.3), 0.88, 0.2)
	_materials["dark"] = _plain_material(Color(0.045, 0.055, 0.055), 0.93)
	_materials["glass"] = _plain_material(Color(0.13, 0.21, 0.22, 0.32), 0.62)
	_materials["glass"].transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_materials["glass"].cull_mode = BaseMaterial3D.CULL_DISABLED
	_materials["lamp"] = _plain_material(Color(0.82, 0.77, 0.59), 0.6)
	_materials["lamp"].emission_enabled = true
	_materials["lamp"].emission = Color(0.85, 0.76, 0.48)
	_materials["lamp"].emission_energy_multiplier = 2.0
	_materials["green"] = _plain_material(Color(0.18, 0.48, 0.29), 0.8)
	_materials["green_lamp"] = _plain_material(Color(0.12, 0.8, 0.36), 0.6)
	_materials["green_lamp"].emission_enabled = true
	_materials["green_lamp"].emission = Color(0.1, 0.85, 0.31)
	_materials["green_lamp"].emission_energy_multiplier = 3.5


func _plain_material(color: Color, roughness: float, metallic: float = 0.0) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = roughness
	material.metallic = metallic
	return material


func _surface_material(kind: String, fallback_color: Color, roughness: float, metallic: float = 0.0) -> StandardMaterial3D:
	var path: String = MATERIAL_DIRECTORY + kind + ".tres"
	if ResourceLoader.exists(path):
		var loaded := load(path) as StandardMaterial3D
		if loaded != null:
			return loaded
	var material := _plain_material(fallback_color, roughness, metallic)
	var noise := FastNoiseLite.new()
	noise.seed = 4704 + kind.length() * 83
	noise.frequency = 0.045 if kind in ["asphalt", "concrete"] else 0.025
	noise.fractal_octaves = 4
	var gradient := Gradient.new()
	gradient.colors = PackedColorArray([fallback_color.darkened(0.16), fallback_color.lightened(0.07)])
	var albedo := NoiseTexture2D.new()
	albedo.width = 256
	albedo.height = 256
	albedo.seamless = true
	albedo.noise = noise
	albedo.color_ramp = gradient
	var normal := NoiseTexture2D.new()
	normal.width = 256
	normal.height = 256
	normal.seamless = true
	normal.noise = noise
	normal.as_normal_map = true
	normal.bump_strength = 0.18
	material.albedo_texture = albedo
	material.normal_enabled = true
	material.normal_texture = normal
	material.normal_scale = 0.15
	material.uv1_triplanar = true
	material.uv1_world_triplanar = true
	material.uv1_scale = Vector3.ONE * 0.5
	return material


func _build_environment() -> void:
	var sky_material := ProceduralSkyMaterial.new()
	sky_material.sky_top_color = Color(0.2, 0.25, 0.3)
	sky_material.sky_horizon_color = Color(0.48, 0.53, 0.56)
	sky_material.ground_bottom_color = Color(0.17, 0.18, 0.17)
	sky_material.ground_horizon_color = Color(0.43, 0.45, 0.43)
	sky_material.sun_angle_max = 8.0
	var sky := Sky.new()
	sky.sky_material = sky_material
	var environment := Environment.new()
	environment.background_mode = Environment.BG_SKY
	environment.sky = sky
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.68, 0.73, 0.75)
	environment.ambient_light_energy = 0.50
	environment.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.ssao_enabled = true
	environment.ssao_radius = 0.75
	environment.ssao_intensity = 1.1
	environment.fog_enabled = true
	environment.fog_light_color = Color(0.48, 0.54, 0.55)
	environment.fog_density = 0.0028
	environment.fog_sky_affect = 0.2
	var world := WorldEnvironment.new()
	world.name = "DepotEnvironment"
	world.environment = environment
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.name = "DepotSun"
	sun.rotation_degrees = Vector3(-53, -31, 0)
	sun.light_color = Color(1.0, 0.94, 0.83)
	sun.light_energy = 1.0
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 120.0
	add_child(sun)


func _build_ground() -> void:
	_box("Asphalt apron", Vector3(0, -0.2, 0), Vector3(96, 0.4, 88), "asphalt", true, false)
	for x: float in [-38.0, -20.0, -2.0, 16.0, 34.0]:
		_box("Apron repair joint", Vector3(x, 0.002, 0), Vector3(0.035, 0.005, 85), "dark", false)
	for z: float in [-35.0, -17.0, 1.0, 19.0, 37.0]:
		_box("Apron repair joint", Vector3(0, 0.002, z), Vector3(93, 0.005, 0.035), "dark", false)
	for index: int in 17:
		var z: float = 36 - index * 4.5
		_box("Service lane dash", Vector3(43, 0.009, z), Vector3(0.12, 0.014, 2.0), "yellow", false)
	for index: int in 15:
		var x: float = -34 + index * 4.6
		_box("South cargo lane dash", Vector3(x, 0.009, 32), Vector3(2.1, 0.014, 0.12), "yellow", false)
	for x: float in [-11.0, -5.0, 5.0, 11.0]:
		_box("Bay approach line", Vector3(x, 0.01, 17.5), Vector3(0.12, 0.014, 10.0), "yellow", false)
	for index: int in 9:
		_box("Pedestrian crossing", Vector3(-20 + index * 0.65, 0.012, 19), Vector3(0.3, 0.016, 4.0), "white", false)
	for point: Vector3 in [Vector3(-40, 0.008, 17), Vector3(18, 0.008, -23), Vector3(13, 0.008, 30), Vector3(-4, 0.008, -29), Vector3(40, 0.008, 12)]:
		_puddle(point, Vector2(3.1, 1.8), 14)
	for point: Vector3 in [Vector3(-19, 0.014, 9), Vector3(20, 0.014, -15), Vector3(40, 0.014, -28)]:
		_drain(point)


func _build_perimeter() -> void:
	# A low concrete curb and physical fence stop the player at the raid boundary.
	_box("North boundary", Vector3(0, 0.3, -43.4), Vector3(95.4, 0.6, 0.45), "concrete")
	_box("South boundary", Vector3(0, 0.3, 43.4), Vector3(95.4, 0.6, 0.45), "concrete")
	_box("West boundary", Vector3(-47.4, 0.3, 0), Vector3(0.45, 0.6, 86.4), "concrete")
	_box("East boundary", Vector3(47.4, 0.3, 0), Vector3(0.45, 0.6, 86.4), "concrete")
	_collision("North fence", Vector3(0, 1.65, -43.4), Vector3(95, 2.2, 0.12))
	_collision("South fence", Vector3(0, 1.65, 43.4), Vector3(95, 2.2, 0.12))
	_collision("West fence", Vector3(-47.4, 1.65, 0), Vector3(0.12, 2.2, 86))
	_collision("East fence", Vector3(47.4, 1.65, 0), Vector3(0.12, 2.2, 86))
	for index: int in 24:
		var x: float = -46 + index * 4.0
		_fence_panel(Vector3(x, 0.6, -43.4), 4.0, 0.0)
		_fence_panel(Vector3(x, 0.6, 43.4), 4.0, 0.0)
	for index: int in 22:
		var z: float = -42 + index * 4.0
		_fence_panel(Vector3(-47.4, 0.6, z), 4.0, PI * 0.5)
		_fence_panel(Vector3(47.4, 0.6, z), 4.0, PI * 0.5)


func _build_warehouse() -> void:
	_box("Warehouse slab", Vector3(0, 0.0, -4), Vector3(30.8, 0.08, 32.8), "concrete", true, false)
	# South loading doors are 6 metres wide; side service doors are 3.2 metres.
	for bounds: Vector2 in [Vector2(-15, -11), Vector2(-5, 5), Vector2(11, 15)]:
		_box("Warehouse south lower", Vector3((bounds.x + bounds.y) * 0.5, 0.62, 12), Vector3(bounds.y - bounds.x, 1.24, 0.32), "concrete")
		_box("Warehouse south cladding", Vector3((bounds.x + bounds.y) * 0.5, 3.65, 12), Vector3(bounds.y - bounds.x, 4.86, 0.25), "corrugated")
	_box("Warehouse south door header", Vector3(0, 5.0, 12), Vector3(30, 3.1, 0.3), "corrugated")
	for x: float in [-8.0, 8.0]:
		_door_frame(Vector3(x, 0, 12.03), 6.0, 3.35, 0.0)
		for slat: int in 8:
			_box("Rolled shutter", Vector3(x, 3.52 + slat * 0.11, 12.16), Vector3(5.85, 0.07, 0.16), "steel", false)
	for bounds: Vector2 in [Vector2(-15, -3), Vector2(3, 15)]:
		_box("Warehouse north lower", Vector3((bounds.x + bounds.y) * 0.5, 0.62, -20), Vector3(bounds.y - bounds.x, 1.24, 0.32), "concrete")
		_box("Warehouse north cladding", Vector3((bounds.x + bounds.y) * 0.5, 3.65, -20), Vector3(bounds.y - bounds.x, 4.86, 0.25), "corrugated")
	_box("Warehouse north door header", Vector3(0, 5, -20), Vector3(30, 3.1, 0.3), "corrugated")
	_door_frame(Vector3(0, 0, -20.03), 6, 3.35, PI)
	for side: float in [-1.0, 1.0]:
		var x: float = side * 15
		for bounds: Vector2 in [Vector2(-20, -6.6), Vector2(-3.4, 12)]:
			_box("Warehouse side concrete", Vector3(x, 0.62, (bounds.x + bounds.y) * 0.5), Vector3(0.32, 1.24, bounds.y - bounds.x), "concrete")
			_box("Warehouse side cladding", Vector3(x, 2.15, (bounds.x + bounds.y) * 0.5), Vector3(0.25, 1.85, bounds.y - bounds.x), "corrugated")
			_box("Warehouse side upper", Vector3(x, 5.65, (bounds.x + bounds.y) * 0.5), Vector3(0.25, 1.8, bounds.y - bounds.x), "corrugated")
			for z: float in range(ceili(bounds.x + 1), floori(bounds.y - 1), 3):
				_window(Vector3(x + side * 0.05, 3.9, z), Vector2(2.5, 1.5), side * PI * 0.5)
		_box("Warehouse service door header", Vector3(x, 4.9, -5), Vector3(0.3, 3.3, 3.2), "corrugated")
		_door_frame(Vector3(x + side * 0.04, 0, -5), 3.2, 3.2, side * PI * 0.5)
		for z: float in [-19.6, -12.0, -4.0, 4.0, 11.6]:
			_box("Warehouse structural column", Vector3(x - side * 0.32, 3.25, z), Vector3(0.3, 6.5, 0.32), "trim")
		for z: float in range(-19, 12, 2):
			_box("Warehouse vertical skin rib", Vector3(x + side * 0.17, 2.15, z), Vector3(0.065, 1.7, 0.055), "steel", false)
	# Pitched roof and open steel trusses form an actual enclosed building.
	var pitch: float = atan2(1.5, 15.4)
	for side: float in [-1.0, 1.0]:
		_box("Warehouse pitched roof", Vector3(side * 7.7, 7.2, -4), Vector3(15.5, 0.18, 33.1), "corrugated", true, false, 0.0, Vector3(0, 0, -side * pitch))
		_box("Warehouse eave gutter", Vector3(side * 15.6, 6.47, -4), Vector3(0.22, 0.24, 33.4), "trim", false)
		for z: float in [-19.7, 11.7]:
			_cylinder("Gutter downpipe", Vector3(side * 15.6, 3.2, z), 0.055, 6.3, "steel", false)
	_box("Roof ridge", Vector3(0, 7.98, -4), Vector3(0.3, 0.13, 33.5), "trim", false)
	for z: float in [-17.0, -9.0, -1.0, 7.0]:
		_beam(Vector3(-14.8, 6.35, z), Vector3(0, 7.85, z), 0.065, "trim")
		_beam(Vector3(0, 7.85, z), Vector3(14.8, 6.35, z), 0.065, "trim")
		_beam(Vector3(-14.8, 6.35, z), Vector3(14.8, 6.35, z), 0.055, "trim")
		_beam(Vector3(-8, 6.35, z), Vector3(0, 7.85, z), 0.035, "steel")
		_beam(Vector3(8, 6.35, z), Vector3(0, 7.85, z), 0.035, "steel")
	for x: float in [-12.7, 12.7]:
		for z: float in [-12.0, 1.0]:
			_storage_rack(Vector3(x, 0.04, z), 1.2, 6.5, 3.5)
	for z: float in [-9.0, 4.0]:
		_storage_rack(Vector3(0, 0.04, z), 2.0, 6.0, 3.2)
	for position: Vector3 in [Vector3(-4, 0, -16), Vector3(9, 0, -17), Vector3(-11, 0, -3), Vector3(11, 0, 9)]:
		_pallet(position, 0.0)
		_prop("crate", position + Vector3(0, 0.15, 0), 0.0)
	for x: float in [-7.0, 7.0]:
		for z: float in [-12.0, 3.0]:
			_strip_light(Vector3(x, 5.9, z), 2.1, 1.15)
	_sign("DEPOT 04", Vector3(0, 5.8, 12.2), Vector2(10, 1.25), 0, 110, Color(0.83, 0.79, 0.65))
	_sign("WAREHOUSE A", Vector3(0, 4.6, -20.2), Vector2(7.5, 0.95), PI, 70)
	_sign("01", Vector3(-8, 4.65, 12.22), Vector2(2, 0.6), 0, 65)
	_sign("02", Vector3(8, 4.65, 12.22), Vector2(2, 0.6), 0, 65)


func _build_office() -> void:
	_box("Office foundation", Vector3(-28.5, 0, -11.5), Vector3(17.6, 0.08, 17.6), "concrete", true, false)
	_box("Office west brick", Vector3(-37, 1.8, -11.5), Vector3(0.32, 3.6, 17), "brick")
	for z: float in [-20.0, -3.0]:
		_box("Office window sill wall", Vector3(-28.5, 0.65, z), Vector3(17, 1.3, 0.32), "brick")
		_box("Office upper brick", Vector3(-28.5, 3.25, z), Vector3(17, 0.7, 0.32), "brick")
		for x: float in [-35.5, -31.0, -26.5, -22.0]:
			_box("Office window pier", Vector3(x, 2.1, z), Vector3(1.5, 1.65, 0.32), "brick")
		for x: float in [-33.25, -28.75, -24.25]:
			_window(Vector3(x, 2.1, z - 0.05 if z < -10 else z + 0.05), Vector2(2.8, 1.65), PI if z < -10 else 0.0)
	for bounds: Vector2 in [Vector2(-20, -9), Vector2(-6, -3)]:
		_box("Office east brick", Vector3(-20, 1.8, (bounds.x + bounds.y) * 0.5), Vector3(0.32, 3.6, bounds.y - bounds.x), "brick")
	_box("Office doorway header", Vector3(-20, 3.25, -7.5), Vector3(0.32, 0.7, 3), "brick")
	_door_frame(Vector3(-19.82, 0, -7.5), 3, 2.85, PI * 0.5)
	for bounds: Vector2 in [Vector2(-37, -29.7), Vector2(-26.3, -20)]:
		_box("Office partition", Vector3((bounds.x + bounds.y) * 0.5, 1.65, -11), Vector3(bounds.y - bounds.x, 3.3, 0.18), "concrete")
	_box("Office partition header", Vector3(-28, 3.05, -11), Vector3(3.4, 0.5, 0.18), "concrete")
	_box("Office roof", Vector3(-28.5, 3.72, -11.5), Vector3(18, 0.24, 18), "corrugated", true, false)
	for x: float in [-37.4, -19.6]:
		_box("Office fascia", Vector3(x, 3.67, -11.5), Vector3(0.12, 0.4, 18), "trim", false)
	for z: float in [-20.4, -2.6]:
		_box("Office fascia", Vector3(-28.5, 3.67, z), Vector3(18, 0.4, 0.12), "trim", false)
	_workbench(Vector3(-33, 0.04, -18.7), 4.8, 0.8, 0.0)
	_workbench(Vector3(-34, 0.04, -4.5), 4, 0.8, 0.0)
	_box("Records cabinet", Vector3(-21.1, 0.95, -18), Vector3(1.2, 1.9, 1.2), "steel")
	for x: float in [-23.5, -22.0]:
		_box("Office locker", Vector3(x, 0.95, -4), Vector3(1.2, 1.9, 0.8), "steel")
		for vent: int in 6:
			_box("Locker vent", Vector3(x, 1.35 + vent * 0.065, -3.57), Vector3(0.65, 0.018, 0.02), "dark", false)
		_box("Locker handle", Vector3(x + 0.4, 0.98, -3.5), Vector3(0.045, 0.3, 0.055), "trim", false)
	_box("Medical wall cabinet", Vector3(-36.65, 1.7, -16), Vector3(0.35, 1.1, 1.5), "white", false)
	_box("Medical cross horizontal", Vector3(-36.43, 1.7, -16), Vector3(0.06, 0.15, 0.65), "red", false)
	_box("Medical cross vertical", Vector3(-36.42, 1.7, -16), Vector3(0.065, 0.65, 0.15), "red", false)
	_strip_light(Vector3(-29, 3.3, -16), 1.5, 1.1)
	_strip_light(Vector3(-29, 3.3, -7), 1.5, 1.05)
	_sign("OFFICE / MEDICAL", Vector3(-19.75, 3.08, -7.5), Vector2(5.4, 0.62), PI * 0.5, 65)
	_sign("FIRST AID", Vector3(-28, 2.55, -10.87), Vector2(2.4, 0.45), 0.0, 42, Color(0.77, 0.78, 0.66))
	for z: float in [-17.0, -6.0]:
		_cylinder("Office exterior pipe", Vector3(-37.25, 1.6, z), 0.05, 3.2, "rust", false)


func _build_workshop() -> void:
	_box("Workshop foundation", Vector3(31, 0, 1), Vector3(18.6, 0.08, 18.6), "concrete", true, false)
	_box("Workshop east wall", Vector3(40, 2.25, 1), Vector3(0.3, 4.5, 18), "corrugated")
	_box("Workshop north wall", Vector3(31, 2.25, -8), Vector3(18, 4.5, 0.3), "corrugated")
	for bounds: Vector2 in [Vector2(-8, -1), Vector2(5, 10)]:
		_box("Workshop west wall", Vector3(22, 2.25, (bounds.x + bounds.y) * 0.5), Vector3(0.3, 4.5, bounds.y - bounds.x), "corrugated")
	_box("Workshop loading header", Vector3(22, 3.85, 2), Vector3(0.3, 1.3, 6), "corrugated")
	_door_frame(Vector3(21.84, 0, 2), 6, 3.2, -PI * 0.5)
	for bounds: Vector2 in [Vector2(22, 30.2), Vector2(33.8, 40)]:
		_box("Workshop south wall", Vector3((bounds.x + bounds.y) * 0.5, 2.25, 10), Vector3(bounds.y - bounds.x, 4.5, 0.3), "corrugated")
	_box("Workshop south header", Vector3(32, 3.85, 10), Vector3(3.6, 1.3, 0.3), "corrugated")
	_door_frame(Vector3(32, 0, 10.17), 3.6, 3.2, 0.0)
	_box("Workshop roof", Vector3(31, 4.65, 1), Vector3(19, 0.22, 19), "corrugated", true, false)
	for z: float in [-7.5, -1.0, 5.0, 9.5]:
		_box("Workshop support", Vector3(39.7, 2.25, z), Vector3(0.3, 4.5, 0.3), "trim")
	_workbench(Vector3(37, 0.04, -6.3), 4.5, 1.0, 0.0)
	_workbench(Vector3(38.5, 0.04, 3), 4.4, 0.8, PI * 0.5)
	_prop("generator", Vector3(27, 0.04, -5), 0.0)
	for x: float in [30.0, 32.0]:
		_box("Workshop machine base", Vector3(x, 0.55, -4.5), Vector3(1.3, 1.1, 1.4), "steel")
		_cylinder("Workshop flywheel", Vector3(x, 1.0, -3.72), 0.42, 0.18, "trim", false, Vector3(PI * 0.5, 0, 0))
	_strip_light(Vector3(28, 4.1, 1), 2.0, 1.15)
	_strip_light(Vector3(35, 4.1, 3), 2.0, 1.15)
	_sign("SERVICE / EAST", Vector3(21.75, 3.82, 2), Vector2(6.8, 0.8), -PI * 0.5, 70)
	_sign("WORKSHOP", Vector3(32, 3.8, 10.22), Vector2(5, 0.75), 0.0, 65)


func _build_containers() -> void:
	_container(Vector3(-34, 0, -31), Vector3(3, 2.8, 10), "blue", 0.0, "N-07")
	_container(Vector3(-24, 0, -32), Vector3(3, 2.8, 10), "green", 0.0, "N-12")
	_container(Vector3(-40, 0, -31), Vector3(3, 2.8, 8), "red", 0.0, "N-03")
	_container(Vector3(-24, 2.8, -32), Vector3(3, 2.8, 10), "corrugated", 0.0, "N-13")
	_container(Vector3(24, 0, 23), Vector3(3, 2.8, 10), "green", 0.0, "S-01")
	_container(Vector3(32, 0, 23), Vector3(3, 2.8, 10), "blue", 0.0, "S-05")
	_container(Vector3(40, 0, 23), Vector3(3, 2.8, 10), "red", 0.0, "S-09")
	for position: Vector3 in [Vector3(-20, 0, -39), Vector3(-35, 0, -23), Vector3(19, 0, 20), Vector3(36, 0, 31)]:
		_prop("barrel", position, 0.0)
		_prop("barrel", position + Vector3(0.78, 0, 0.4), 0.0)
	for position: Vector3 in [Vector3(-32, 0, -24), Vector3(20, 0, 30)]:
		_pallet(position, PI * 0.5)
		_prop("crate", position + Vector3(0, 0.15, 0), PI * 0.5)


func _build_checkpoint() -> void:
	_box("Checkpoint concrete pad", Vector3(-36, 0.015, 33), Vector3(13, 0.05, 15), "concrete", true, false)
	for x: float in [-42.0, -30.0]:
		for z: float in [27.0, 39.0]:
			_box("Checkpoint canopy column", Vector3(x, 2.2, z), Vector3(0.18, 4.4, 0.18), "trim")
	_box("Checkpoint canopy", Vector3(-36, 4.5, 33), Vector3(13.5, 0.17, 13.5), "corrugated", true, false)
	for x: float in [-41.0, -31.0]:
		_prop("barrier", Vector3(x, 0, 24), 0.0)
		_prop("barrier", Vector3(x, 0, 40.5), 0.0)
	_prop("crate", Vector3(-40, 0.05, 36), 0.2)
	_prop("generator", Vector3(-30.8, 0.05, 37.3), -PI * 0.5)
	_strip_light(Vector3(-36, 4.1, 32), 1.8, 0.8)
	_sign("ASHGATE / 04", Vector3(-36, 3.85, 26.15), Vector2(8.5, 1.0), PI, 80)
	_sign("SOUTH CHECKPOINT", Vector3(-36, 3.5, 26.4), Vector2(9, 0.65), 0.0, 65)
	_box("Checkpoint board", Vector3(-42.2, 1.7, 30), Vector3(0.1, 1.4, 2.2), "trim")
	_sign("NORTH GATE\nEXTRACTION", Vector3(-42.11, 1.7, 30), Vector2(2, 1.2), PI * 0.5, 50, Color(0.65, 0.8, 0.64), false)


func _build_yard() -> void:
	for position: Vector3 in [Vector3(-16, 0, 23), Vector3(8, 0, 27), Vector3(18, 0, -28), Vector3(34, 0, -11), Vector3(-42, 0, 5)]:
		_prop("barrier", position, 0.0)
	for position: Vector3 in [Vector3(-24, 0, 14), Vector3(12, 0, 20), Vector3(-9, 0, 30), Vector3(16.5, 0, 7), Vector3(-20, 0, -23)]:
		_pallet(position, 0.0)
		_prop("crate", position + Vector3(0, 0.15, 0), 0.0)
		_prop("crate", position + Vector3(1.25, 0.15, 0.18), 0.14)
	for position: Vector3 in [Vector3(-18, 0, 8), Vector3(-39, 0, -2), Vector3(19, 0, -18), Vector3(42, 0, -14), Vector3(14, 0, 29)]:
		_prop("barrel", position, 0.0)
		_prop("barrel", position + Vector3(0.75, 0, 0.23), 0.0)
	# Fuel yard: low plinths, vertical tanks, feeder pipework and bollards.
	for x: float in [27.0, 34.0]:
		_box("Tank footing", Vector3(x, 0.15, -18), Vector3(4.4, 0.3, 5), "concrete")
		_cylinder("Fuel tank", Vector3(x, 2.5, -18), 1.75, 4.6, "steel", true)
		_cylinder("Fuel tank upper seam", Vector3(x, 4.45, -18), 1.8, 0.09, "trim", false)
		_cylinder("Fuel tank lower seam", Vector3(x, 0.65, -18), 1.8, 0.09, "trim", false)
		_cylinder("Tank vent", Vector3(x, 5.15, -18), 0.12, 0.75, "rust", false)
		_cylinder("Tank top hatch", Vector3(x, 4.85, -18), 0.45, 0.1, "trim", false)
		_beam(Vector3(x + 1.1, 0.5, -18), Vector3(x + 1.1, 4.7, -18), 0.055, "yellow")
		for rung: int in 13:
			_beam(Vector3(x + 0.85, 0.6 + rung * 0.3, -19.3), Vector3(x + 1.3, 0.6 + rung * 0.3, -19.3), 0.018, "steel")
	for x: float in [23.5, 37.5]:
		for z: float in [-21.0, -14.5]:
			_cylinder("Fuel yard bollard", Vector3(x, 0.55, z), 0.1, 1.1, "yellow", true)
	_beam(Vector3(27, 0.6, -15.8), Vector3(34, 0.6, -15.8), 0.1, "rust")
	_sign("FUEL / NO SMOKING", Vector3(31, 1.25, -14.1), Vector2(5.5, 0.75), 0.0, 58)
	for position: Vector3 in [Vector3(-44, 0, 14), Vector3(19, 0, 34), Vector3(43, 0, -9), Vector3(-19, 0, -39)]:
		_light_pole(position)


func _build_extraction() -> void:
	_box("Extraction bay paint", Vector3(37, 0.018, -38), Vector3(9, 0.02, 8), "extraction_paint", false)
	for x: float in [32.4, 41.6]:
		_box("Extraction edge", Vector3(x, 0.033, -38), Vector3(0.14, 0.022, 8.4), "white", false)
	for z: float in [-42.1, -33.9]:
		_box("Extraction edge", Vector3(37, 0.033, z), Vector3(9.3, 0.022, 0.14), "white", false)
	for x: float in [32.0, 42.0]:
		_box("Extraction gatepost", Vector3(x, 2.0, -42.6), Vector3(0.3, 4, 0.35), "trim")
	_box("Extraction gateheader", Vector3(37, 4, -42.6), Vector3(10.3, 0.28, 0.35), "trim", false)
	_sign("NORTH GATE / EXTRACTION", Vector3(37, 3.35, -42.35), Vector2(10, 0.95), 0.0, 72, Color(0.68, 0.85, 0.66))
	_sign("04", Vector3(37, 1.7, -42.25), Vector2(1.4, 1.2), 0.0, 110, Color(0.6, 0.86, 0.63))
	for x: float in [32.8, 41.2]:
		_box("Extraction signal housing", Vector3(x, 2.5, -42.2), Vector3(0.44, 0.65, 0.25), "trim", false)
		_box("Extraction green signal", Vector3(x, 2.5, -42.03), Vector3(0.26, 0.48, 0.07), "green_lamp", false)
	var light := OmniLight3D.new()
	light.position = Vector3(37, 2.7, -38)
	light.light_color = Color(0.2, 0.8, 0.38)
	light.light_energy = 1.4
	light.omni_range = 7.0
	light.light_cull_mask = 1
	add_child(light)
	_prop("barrier", Vector3(30, 0, -37), PI * 0.5)
	_prop("barrier", Vector3(44, 0, -37), PI * 0.5)


func _build_background() -> void:
	# Non-playable silhouettes beyond the physical depot fence give the map a
	# horizon without introducing extra traversal areas or navigation islands.
	for index: int in 11:
		var x: float = -66 + index * 13
		var h: float = 7 + float((index * 13 + 7) % 8)
		_box("Distant industrial block", Vector3(x, h * 0.5 - 1, -62 - (index % 3) * 4), Vector3(10, h, 10), "concrete", false)
		_box("Distant building roof", Vector3(x, h - 0.8, -62 - (index % 3) * 4), Vector3(10.4, 0.35, 10.4), "trim", false)
	for index: int in 5:
		var z: float = -31 + index * 18
		_box("Distant west factory", Vector3(-62, 4.5, z), Vector3(15, 10, 14), "brick", false)
	for x: float in [-49.0, 54.0]:
		_cylinder("Distant chimney", Vector3(x, 12, -57), 1.0, 26, "brick", false)
		_cylinder("Chimney crown", Vector3(x, 24.9, -57), 1.1, 0.5, "trim", false)
	# A gantry silhouette near the north cargo yard.
	for x: float in [-44, -17]:
		_box("Cargo gantry leg", Vector3(x, 6.5, -40), Vector3(0.65, 13, 0.65), "yellow", false)
	_box("Cargo gantry crossbeam", Vector3(-30.5, 12.8, -40), Vector3(28, 1.1, 0.6), "yellow", false)
	for index: int in 9:
		var x: float = -43 + index * 3
		_beam(Vector3(x, 12.4, -40), Vector3(x + 1.5, 13.3, -40), 0.035, "trim")
		_beam(Vector3(x + 1.5, 13.3, -40), Vector3(x + 3, 12.4, -40), 0.035, "trim")


func _storage_rack(position: Vector3, width: float, length: float, height: float) -> void:
	for x: float in [-width * 0.5, width * 0.5]:
		for z: float in [-length * 0.5, length * 0.5]:
			_box("Rack upright", position + Vector3(x, height * 0.5, z), Vector3(0.1, height, 0.1), "trim", false)
	for y: float in [0.22, height * 0.48, height - 0.1]:
		_box("Rack shelf", position + Vector3(0, y, 0), Vector3(width, 0.1, length), "steel", false)
		_box("Rack safety beam", position + Vector3(0, y - 0.05, length * 0.5), Vector3(width, 0.15, 0.09), "yellow", false)
		for z: float in [-length * 0.32, length * 0.1, length * 0.35]:
			_box("Stored shipping carton", position + Vector3(0, y + 0.43, z), Vector3(width * 0.8, 0.75, 0.95), "wood", false)
	_collision("Storage rack", position + Vector3(0, height * 0.5, 0), Vector3(width + 0.12, height, length + 0.12))


func _workbench(position: Vector3, length: float, depth: float, yaw: float) -> void:
	var basis := Basis(Vector3.UP, yaw)
	_box("Workbench top", position + Vector3(0, 0.95, 0), Vector3(length, 0.12, depth), "wood", false, false, yaw)
	for x: float in [-length * 0.42, length * 0.42]:
		for z: float in [-depth * 0.35, depth * 0.35]:
			_box("Workbench leg", position + basis * Vector3(x, 0.44, z), Vector3(0.09, 0.88, 0.09), "trim", false)
	_box("Workbench lower shelf", position + Vector3(0, 0.3, 0), Vector3(length * 0.9, 0.06, depth * 0.85), "steel", false, false, yaw)
	_collision("Workbench", position + Vector3(0, 0.5, 0), Vector3(length, 1.0, depth), yaw)
	for index: int in 3:
		_box("Workbench small cases", position + basis * Vector3(-length * 0.3 + index * 0.55, 1.14, 0), Vector3(0.38, 0.26, depth * 0.7), "trim", false, false, yaw)


func _container(position: Vector3, size: Vector3, color: String, yaw: float, code: String) -> void:
	_box("Sealed cargo container", position + Vector3(0, size.y * 0.5, 0), size, "corrugated", true, true, yaw)
	var basis := Basis(Vector3.UP, yaw)
	for side: float in [-1.0, 1.0]:
		for index: int in int(size.z / 0.3):
			var z: float = -size.z * 0.5 + 0.18 + index * 0.3
			_box("Container corrugation", position + basis * Vector3(side * (size.x * 0.5 + 0.025), size.y * 0.5, z), Vector3(0.07, size.y - 0.15, 0.06), color, false, false, yaw)
	for side: float in [-1.0, 1.0]:
		_box("Container corner post", position + basis * Vector3(side * size.x * 0.5, size.y * 0.5, size.z * 0.5 + 0.04), Vector3(0.13, size.y, 0.15), color, false, false, yaw)
		_box("Container door", position + basis * Vector3(side * size.x * 0.25, size.y * 0.5, size.z * 0.5 + 0.035), Vector3(size.x * 0.48, size.y - 0.16, 0.045), color, false, false, yaw)
		_box("Container locking rod", position + basis * Vector3(side * size.x * 0.21, size.y * 0.5, size.z * 0.5 + 0.12), Vector3(0.045, size.y - 0.35, 0.065), "trim", false, false, yaw)
		_box("Container lock lever", position + basis * Vector3(side * size.x * 0.21, 1.1, size.z * 0.5 + 0.17), Vector3(0.3, 0.05, 0.045), "steel", false, false, yaw)
	for y: float in [0.08, size.y - 0.08]:
		_box("Container edge rail", position + basis * Vector3(0, y, size.z * 0.5 + 0.08), Vector3(size.x, 0.14, 0.13), color, false, false, yaw)
	_sign(code, position + basis * Vector3(0, 2.0, size.z * 0.5 + 0.18), Vector2(1.6, 0.35), yaw, 36, Color(0.74, 0.74, 0.62), false)


func _prop(kind: String, position: Vector3, yaw: float = 0.0) -> void:
	var path: String = PROP_DIRECTORY + kind + ".glb"
	if ResourceLoader.exists(path):
		var scene := load(path) as PackedScene
		if scene != null:
			var node := scene.instantiate() as Node3D
			if node != null:
				var placement := Node3D.new()
				placement.name = kind.capitalize()
				placement.position = position
				placement.rotation.y = yaw
				_props.add_child(placement)
				placement.add_child(node)
				var bounds: AABB = _prop_bounds(placement)
				if bounds.size.x > 0.001 and bounds.size.y > 0.001 and bounds.size.z > 0.001:
					# Sources have different origins and real-world units. Fit uniformly
					# inside the reference envelope, then derive collision from the mesh.
					# This avoids invisible oversized blockers around small props.
					var reference: Vector3 = _prop_size(kind)
					var ratio: Vector3 = reference / bounds.size
					var fit: float = minf(ratio.x, minf(ratio.y, ratio.z))
					var center: Vector3 = bounds.get_center()
					var offset := Vector3(-center.x, -bounds.position.y, -center.z) * fit
					node.transform = Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * fit), offset) * node.transform
					var size: Vector3 = bounds.size * fit
					_collision(kind, position + Vector3(0, size.y * 0.5, 0), size, yaw)
					return
				_props.remove_child(placement)
				placement.queue_free()
	match kind:
		"barrel":
			_cylinder("Weathered drum", position + Vector3(0, 0.49, 0), 0.31, 0.98, "steel", true)
			for y: float in [0.04, 0.22, 0.76, 0.95]:
				_cylinder("Drum rolled band", position + Vector3(0, y, 0), 0.325, 0.04, "trim", false)
			_cylinder("Drum filler cap", position + Vector3(0.12, 1.0, 0), 0.055, 0.025, "trim", false)
		"barrier":
			_box("Concrete road barrier", position + Vector3(0, 0.52, 0), Vector3(2.5, 1.04, 0.65), "concrete")
			for x: float in [-0.8, 0.0, 0.8]:
				_box("Barrier yellow warning", position + Vector3(x, 0.6, 0.334), Vector3(0.22, 0.56, 0.012), "yellow", false)
		"generator":
			_box("Generator housing", position + Vector3(0, 0.62, 0), Vector3(1.8, 1.24, 1.0), "green", true, true, yaw)
			for index: int in 12:
				_box("Generator grille", position + Basis(Vector3.UP, yaw) * Vector3(-0.7 + index * 0.125, 0.65, 0.515), Vector3(0.04, 0.65, 0.035), "dark", false, false, yaw)
		"lamp":
			_light_pole(position)
		_:
			_box("Shipping crate", position + Vector3(0, 0.5, 0), Vector3(1.1, 1, 1.0), "wood", true, true, yaw)
			for y: float in [0.08, 0.92]:
				_box("Crate perimeter brace", position + Vector3(0, y, 0), Vector3(1.15, 0.1, 1.05), "wood", false, false, yaw)
			for x: float in [-0.46, 0.46]:
				_box("Crate upright brace", position + Basis(Vector3.UP, yaw) * Vector3(x, 0.5, 0.52), Vector3(0.1, 0.92, 0.08), "wood", false, false, yaw)


func _prop_bounds(root: Node3D) -> AABB:
	var result := AABB()
	var first: bool = true
	for child: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh := child as MeshInstance3D
		if mesh.mesh == null:
			continue
		var relative: Transform3D = root.global_transform.affine_inverse() * mesh.global_transform
		var bounds: AABB = relative * mesh.get_aabb()
		result = bounds if first else result.merge(bounds)
		first = false
	return result


func _prop_size(kind: String) -> Vector3:
	match kind:
		"barrel": return Vector3(0.68, 1.0, 0.68)
		"barrier": return Vector3(2.5, 1.0, 0.65)
		"generator": return Vector3(1.8, 1.3, 1.1)
		_: return Vector3(1.15, 1.0, 1.05)


func _pallet(position: Vector3, yaw: float) -> void:
	var basis := Basis(Vector3.UP, yaw)
	for x: float in [-0.48, 0.0, 0.48]:
		_box("Pallet bearer", position + basis * Vector3(x, 0.055, 0), Vector3(0.1, 0.11, 1.2), "wood", false, false, yaw)
	for index: int in 7:
		_box("Pallet top slat", position + basis * Vector3(0, 0.13, -0.54 + index * 0.18), Vector3(1.2, 0.055, 0.14), "wood", false, false, yaw)


func _door_frame(position: Vector3, width: float, height: float, yaw: float) -> void:
	var basis := Basis(Vector3.UP, yaw)
	for side: float in [-1.0, 1.0]:
		_box("Door steel jamb", position + basis * Vector3(side * (width * 0.5 + 0.055), height * 0.5, 0), Vector3(0.15, height, 0.16), "trim", false, false, yaw)
	_box("Door steel header", position + Vector3(0, height + 0.02, 0), Vector3(width + 0.23, 0.16, 0.16), "trim", false, false, yaw)


func _window(position: Vector3, size: Vector2, yaw: float) -> void:
	var basis := Basis(Vector3.UP, yaw)
	_box("Dusty window", position, Vector3(size.x, size.y, 0.025), "glass", false, false, yaw)
	for x: float in [-size.x * 0.5, 0.0, size.x * 0.5]:
		_box("Window vertical mullion", position + basis * Vector3(x, 0, 0.02), Vector3(0.06, size.y + 0.1, 0.065), "trim", false, false, yaw)
	for y: float in [-size.y * 0.5, size.y * 0.5]:
		_box("Window horizontal mullion", position + Vector3(0, y, 0), Vector3(size.x + 0.1, 0.08, 0.08), "trim", false, false, yaw)


func _strip_light(position: Vector3, length: float, energy: float) -> void:
	_box("Fluorescent housing", position, Vector3(length + 0.2, 0.12, 0.26), "trim", false)
	_box("Fluorescent diffuser", position + Vector3(0, -0.08, 0), Vector3(length, 0.06, 0.18), "lamp", false)
	var light := OmniLight3D.new()
	light.position = position + Vector3(0, -0.3, 0)
	light.light_color = Color(0.9, 0.86, 0.72)
	light.light_energy = energy
	light.light_specular = 0.4
	light.omni_range = 8.0
	light.omni_attenuation = 1.1
	light.light_cull_mask = 1
	light.shadow_enabled = false
	add_child(light)


func _light_pole(position: Vector3) -> void:
	_cylinder("Yard lamp pole", position + Vector3(0, 3.2, 0), 0.075, 6.4, "trim", false)
	_box("Yard lamp footing", position + Vector3(0, 0.15, 0), Vector3(0.55, 0.3, 0.55), "concrete")
	_box("Yard lamp arm", position + Vector3(0.55, 6.25, 0), Vector3(1.2, 0.09, 0.09), "steel", false)
	_box("Yard lamp head", position + Vector3(1.1, 6.15, 0), Vector3(0.65, 0.16, 0.5), "trim", false)
	_box("Yard lamp face", position + Vector3(1.1, 6.04, 0), Vector3(0.55, 0.03, 0.4), "lamp", false)


func _fence_panel(center: Vector3, width: float, yaw: float) -> void:
	var basis := Basis(Vector3.UP, yaw)
	for x: float in [-width * 0.5, width * 0.5]:
		_cylinder("Fence post", center + basis * Vector3(x, 1.13, 0), 0.045, 2.26, "trim", false)
	for y: float in [0.12, 2.12]:
		_beam(center + basis * Vector3(-width * 0.5, y, 0), center + basis * Vector3(width * 0.5, y, 0), 0.018, "steel")
	# Real wire geometry is batched with the static scene, not hundreds of draws.
	for slope: float in [-1.0, 1.0]:
		for index: int in 19:
			var intercept: float = -4.4 + index * 0.45
			var intersections: Array[Vector2] = []
			for x: float in [-width * 0.5, width * 0.5]:
				var y: float = slope * x + intercept
				if y >= 0.14 and y <= 2.1:
					intersections.append(Vector2(x, y))
			for y: float in [0.14, 2.1]:
				var x: float = (y - intercept) / slope
				if x > -width * 0.5 and x < width * 0.5:
					intersections.append(Vector2(x, y))
			if intersections.size() >= 2:
				_beam(center + basis * Vector3(intersections[0].x, intersections[0].y, 0), center + basis * Vector3(intersections[1].x, intersections[1].y, 0), 0.007, "steel", true)


func _drain(position: Vector3) -> void:
	_box("Drain frame", position, Vector3(0.8, 0.025, 1.4), "trim", false)
	for index: int in 13:
		_box("Drain slots", position + Vector3(0, 0.02, -0.6 + index * 0.1), Vector3(0.6, 0.005, 0.035), "dark", false)


func _puddle(position: Vector3, size: Vector2, seed_value: int) -> void:
	var material_key: String = "puddle"
	if not _materials.has(material_key):
		var material := _plain_material(Color(0.08, 0.095, 0.1, 0.45), 0.36, 0.1)
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_materials[material_key] = material
	var surface: SurfaceTool = _surface(material_key)
	var points := PackedVector3Array()
	for index: int in 16:
		var angle: float = index * TAU / 16.0
		var variation: float = 0.84 + 0.13 * sin(index * 2.19 + seed_value)
		points.append(position + Vector3(cos(angle) * size.x * variation, 0, sin(angle) * size.y * variation))
	for index: int in 16:
		_emit_triangle(surface, position, points[(index + 1) % 16], points[index], Vector3.UP)


func _sign(text: String, position: Vector3, size: Vector2, yaw: float, font_size: int = 58, color: Color = Color(0.8, 0.81, 0.73), backing: bool = true) -> void:
	if backing:
		_box("Sign backing", position - Basis(Vector3.UP, yaw) * Vector3(0, 0, 0.04), Vector3(size.x, size.y, 0.065), "trim", false, false, yaw)
	var label := Label3D.new()
	label.name = "DepotSign"
	label.text = text
	label.position = position
	label.rotation.y = yaw
	label.font_size = font_size
	label.pixel_size = minf(size.x / maxf(1.0, text.length() * font_size * 0.52), size.y / maxf(font_size * 1.2, 1.0))
	label.modulate = color
	label.outline_modulate = Color(0.035, 0.045, 0.045, 0.8)
	label.outline_size = 4
	label.no_depth_test = false
	label.fixed_size = false
	_signs.add_child(label)


func _surface(material_key: String) -> SurfaceTool:
	if not _surfaces.has(material_key):
		var tool := SurfaceTool.new()
		tool.begin(Mesh.PRIMITIVE_TRIANGLES)
		tool.set_material(_materials[material_key])
		_surfaces[material_key] = tool
	return _surfaces[material_key]


func _box(label: String, position: Vector3, size: Vector3, material_key: String, collidable: bool = true, navigation_block: bool = true, yaw: float = 0.0, rotation_value: Vector3 = Vector3.ZERO) -> void:
	var rotation_basis := Basis.from_euler(rotation_value) if rotation_value != Vector3.ZERO else Basis(Vector3.UP, yaw)
	_emit_arrays(_box_arrays, position, size, rotation_basis, material_key)
	if collidable:
		_collision(label, position, size, yaw, navigation_block, rotation_value)


func _cylinder(label: String, position: Vector3, radius: float, height: float, material_key: String, collidable: bool = false, rotation_value: Vector3 = Vector3.ZERO) -> void:
	_emit_arrays(_cylinder_arrays, position, Vector3(radius * 2, height, radius * 2), Basis.from_euler(rotation_value), material_key)
	if collidable:
		_collision(label, position, Vector3(radius * 2, height, radius * 2), 0.0)


func _beam(from: Vector3, to: Vector3, radius: float, material_key: String, thin_wire: bool = false) -> void:
	var direction: Vector3 = to - from
	if direction.length_squared() < 0.00001:
		return
	var basis := Basis(Quaternion(Vector3.UP, direction.normalized()))
	_emit_arrays(_wire_arrays if thin_wire else _cylinder_arrays, (from + to) * 0.5, Vector3(radius * 2, direction.length(), radius * 2), basis, material_key)


func _emit_arrays(arrays: Array, position: Vector3, scale_value: Vector3, rotation_basis: Basis, material_key: String) -> void:
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	var tool: SurfaceTool = _surface(material_key)
	for vertex_index: int in indices:
		tool.set_normal(rotation_basis * normals[vertex_index])
		tool.set_uv(uvs[vertex_index])
		tool.add_vertex(rotation_basis * (vertices[vertex_index] * scale_value) + position)


func _emit_triangle(tool: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, normal: Vector3) -> void:
	for point: Vector3 in [a, b, c]:
		tool.set_normal(normal)
		tool.set_uv(Vector2(point.x, point.z))
		tool.add_vertex(point)


func _collision(label: String, position: Vector3, size: Vector3, yaw: float = 0.0, navigation_block: bool = true, rotation_value: Vector3 = Vector3.ZERO) -> void:
	var shape := BoxShape3D.new()
	shape.size = size
	var collision := CollisionShape3D.new()
	collision.name = label.validate_node_name() + str(_piece_count)
	_piece_count += 1
	collision.shape = shape
	collision.position = position
	collision.rotation = rotation_value if rotation_value != Vector3.ZERO else Vector3(0, yaw, 0)
	_solids.add_child(collision)
	if navigation_block and position.y - size.y * 0.5 < 1.85 and position.y + size.y * 0.5 > 0.12:
		var rotated_size: Vector3 = Vector3(absf(cos(yaw)) * size.x + absf(sin(yaw)) * size.z, size.y, absf(sin(yaw)) * size.x + absf(cos(yaw)) * size.z)
		_obstacles.append(AABB(position - rotated_size * 0.5, rotated_size))
		_footprints.append(Rect2(Vector2(position.x - rotated_size.x * 0.5 - CLEARANCE, position.z - rotated_size.z * 0.5 - CLEARANCE), Vector2(rotated_size.x, rotated_size.z) + Vector2.ONE * CLEARANCE * 2.0))


func _commit_geometry() -> void:
	for key: String in _surfaces:
		var surface: SurfaceTool = _surfaces[key]
		surface.index()
		surface.generate_tangents()
		var mesh: ArrayMesh = surface.commit()
		var node := MeshInstance3D.new()
		node.name = "Depot_" + key
		node.mesh = mesh
		add_child(node)
