extends Node3D

signal stats_changed
signal hit_confirmed(points: int)

@onready var player: CharacterBody3D = $Player
@onready var weapon: Node3D = $Player/Head/Camera3D/WeaponRig

var shots: int = 0
var hits: int = 0
var score: int = 0


func _ready() -> void:
	weapon.connect("shot_fired", _on_shot_fired)
	weapon.connect("target_hit", _on_target_hit)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("reset_range") and not event.is_echo():
		reset_session()
		get_viewport().set_input_as_handled()


func _on_shot_fired() -> void:
	shots += 1
	stats_changed.emit()


func _on_target_hit(points: int) -> void:
	hits += 1
	score += points
	hit_confirmed.emit(points)
	stats_changed.emit()


func reset_session() -> void:
	shots = 0
	hits = 0
	score = 0
	for target: Node in $Targets.get_children():
		target.call("reset_target")
	player.call("respawn")
	weapon.call("reset_weapon")
	stats_changed.emit()
