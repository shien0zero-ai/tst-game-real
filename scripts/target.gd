extends StaticBody3D

@export var target_name: String = "01"
@onready var marks: Node3D = $Marks
@onready var hit_label: Label3D = $HitLabel

var hit_count: int = 0
var total_points: int = 0


func _ready() -> void:
	_update_label()


func register_hit(world_point: Vector3, normal: Vector3) -> int:
	var local_point: Vector3 = to_local(world_point)
	var radius: float = Vector2(local_point.x, local_point.y).length()
	var points: int = 1
	if radius <= 0.10:
		points = 10
	elif radius <= 0.24:
		points = 7
	elif radius <= 0.42:
		points = 4
	hit_count += 1
	total_points += points
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.06, 0.045, 0.025)
	material.roughness = 1.0
	var mesh := SphereMesh.new()
	mesh.radius = 0.011
	mesh.height = 0.022
	mesh.radial_segments = 8
	mesh.rings = 4
	mesh.material = material
	var mark := MeshInstance3D.new()
	mark.mesh = mesh
	marks.add_child(mark)
	mark.global_position = world_point + normal * 0.002
	if marks.get_child_count() > 64:
		marks.get_child(0).queue_free()
	_update_label()
	return points


func reset_target() -> void:
	hit_count = 0
	total_points = 0
	for mark: Node in marks.get_children():
		mark.queue_free()
	_update_label()


func _update_label() -> void:
	hit_label.text = "%s  /  %02d HITS" % [target_name, hit_count]
