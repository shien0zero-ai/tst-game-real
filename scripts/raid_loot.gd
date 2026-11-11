extends StaticBody3D
## Contents are rolled once at deployment, and remaining items stay in the case.

const FONT = preload("res://assets/fonts/menu_jp.otf")
var contents: Dictionary = {}
var display_name: String = "物資ケース"
var loot_kind: String = "supplies"
var searched: bool = false
var is_corpse: bool = false


func _ready() -> void:
	add_to_group("raid_loot")
	collision_layer = 9
	collision_mask = 0
	var dimensions := Vector3(0.72, 0.50, 0.48) if is_corpse else Vector3(0.90, 0.76, 0.66)
	var shape := BoxShape3D.new()
	shape.size = dimensions
	var collision := CollisionShape3D.new()
	collision.shape = shape
	collision.position.y = dimensions.y * 0.5
	add_child(collision)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.20, 0.23, 0.16) if is_corpse else Color(0.32, 0.29, 0.19)
	material.roughness = 0.87
	if not is_corpse and ResourceLoader.exists("res://assets/raid/materials/wood.tres"):
		material = load("res://assets/raid/materials/wood.tres").duplicate() as StandardMaterial3D
		material.uv1_scale = Vector3(0.7, 0.7, 0.7)
	_box(dimensions, Vector3(0, dimensions.y * 0.5, 0), material)
	var trim := StandardMaterial3D.new()
	trim.albedo_color = Color(0.11, 0.14, 0.12)
	trim.metallic = 0.5
	trim.roughness = 0.73
	for x: float in [-dimensions.x * 0.35, dimensions.x * 0.35]:
		_box(Vector3(0.045, dimensions.y + 0.014, dimensions.z + 0.014), Vector3(x, dimensions.y * 0.5, 0), trim)
	var label := Label3D.new()
	label.font = FONT
	label.text = "AID" if loot_kind == "medical" else (".45 ACP" if loot_kind == "ammo" else "DEPOT 04")
	label.font_size = 32
	label.pixel_size = 0.003
	label.modulate = Color(0.80, 0.77, 0.60)
	label.position = Vector3(0, dimensions.y * 0.55, dimensions.z * 0.5 + 0.008)
	label.no_depth_test = false
	add_child(label)


func _box(dimensions: Vector3, offset: Vector3, material: Material) -> void:
	var mesh := BoxMesh.new()
	mesh.size = dimensions
	var visual := MeshInstance3D.new()
	visual.mesh = mesh
	visual.material_override = material
	visual.position = offset
	add_child(visual)


func get_interaction_point() -> Vector3:
	return global_position + Vector3(0, 0.25 if is_corpse else 0.42, 0)


func is_empty() -> bool:
	for value: Variant in contents.values():
		if int(value) > 0:
			return false
	return true


func get_prompt() -> String:
	if is_empty():
		return display_name + "  /  空です"
	return "[ E ]  %sを%s" % [display_name, "回収" if searched else "調べる"]
