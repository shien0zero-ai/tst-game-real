extends Control

var spread: float = 6.0
var aiming: bool = false
var hit_time: float = 0.0


func _process(delta: float) -> void:
	hit_time = maxf(0.0, hit_time - delta)
	queue_redraw()


func _draw() -> void:
	var center: Vector2 = size * 0.5
	var color := Color(0.95, 0.97, 0.96, 0.85)
	if not aiming:
		for direction: Vector2 in [Vector2.LEFT, Vector2.RIGHT, Vector2.UP, Vector2.DOWN]:
			draw_line(center + direction * spread, center + direction * (spread + 5.0), Color(0.04, 0.05, 0.05, 0.7), 3.0, true)
			draw_line(center + direction * spread, center + direction * (spread + 5.0), color, 1.0, true)
	if hit_time > 0.0:
		var hit_color := Color(1.0, 0.72, 0.32, minf(hit_time * 8.0, 1.0))
		for direction: Vector2 in [Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)]:
			draw_line(center + direction * 5.0, center + direction * 10.0, hit_color, 2.0, true)
