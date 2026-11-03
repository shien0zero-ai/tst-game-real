extends CanvasLayer

const RETICLE = preload("res://scripts/reticle.gd")
const INK := Color(0.035, 0.055, 0.065, 0.86)
const TEXT := Color(0.91, 0.94, 0.92)
const MUTED := Color(0.62, 0.70, 0.70)
const AMBER := Color(1.0, 0.68, 0.30)

var _session: Node
var _weapon: Node
var _ammo: Label
var _status: Label
var _stats: Label
var _hint: PanelContainer
var _reticle: Control
var _points: Label
var _point_time: float = 0.0


func _ready() -> void:
	_session = get_parent()
	_weapon = _session.get_node("Player/Head/Camera3D/WeaponRig")
	_session.connect("hit_confirmed", _on_hit)
	_session.connect("stats_changed", _update_stats)
	_build_interface()
	_update_stats()


func _build_interface() -> void:
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	var title: PanelContainer = _panel(root, Vector2(24, 24), Vector2(288, 84))
	var titles := VBoxContainer.new()
	titles.add_theme_constant_override("separation", 3)
	title.add_child(titles)
	_label(titles, "FIELD TEST  /  01", 12, AMBER)
	_label(titles, "M1911", 29, TEXT)
	_label(titles, "OUTDOOR FIRING RANGE", 11, MUTED)
	var stat_panel: PanelContainer = _panel(root, Vector2(-338, 24), Vector2(314, 66), Control.PRESET_TOP_RIGHT)
	var stat_box := VBoxContainer.new()
	stat_panel.add_child(stat_box)
	_label(stat_box, "SESSION", 11, AMBER)
	_stats = _label(stat_box, "", 17, TEXT)
	var controls: PanelContainer = _panel(root, Vector2(24, -92), Vector2(600, 68), Control.PRESET_BOTTOM_LEFT)
	var control_box := VBoxContainer.new()
	control_box.add_theme_constant_override("separation", 6)
	controls.add_child(control_box)
	_label(control_box, "LMB  FIRE       RMB  AIM       R  RELOAD       T  RESET", 14, TEXT)
	_label(control_box, "WASD  MOVE     SHIFT  SPRINT     SPACE  JUMP     ESC  CURSOR", 11, MUTED)
	var ammunition: PanelContainer = _panel(root, Vector2(-268, -141), Vector2(244, 117), Control.PRESET_BOTTOM_RIGHT)
	var ammo_box := VBoxContainer.new()
	ammunition.add_child(ammo_box)
	_status = _label(ammo_box, "READY", 12, AMBER)
	_ammo = _label(ammo_box, "07 / 07", 40, TEXT)
	_label(ammo_box, "UNLIMITED MAGAZINES", 10, MUTED)
	_reticle = Control.new()
	_reticle.set_script(RETICLE)
	_reticle.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_reticle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_reticle)
	_points = Label.new()
	_points.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	_points.position = Vector2(-70, 28)
	_points.size = Vector2(140, 30)
	_points.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_points.add_theme_font_size_override("font_size", 18)
	_points.add_theme_color_override("font_color", AMBER)
	root.add_child(_points)
	_hint = _panel(root, Vector2(-200, -56), Vector2(400, 112), Control.PRESET_CENTER)
	var resume_box := VBoxContainer.new()
	resume_box.alignment = BoxContainer.ALIGNMENT_CENTER
	resume_box.add_theme_constant_override("separation", 12)
	_hint.add_child(resume_box)
	var pause_label: Label = _label(resume_box, "CURSOR RELEASED", 13, AMBER)
	pause_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var resume_label: Label = _label(resume_box, "Click to resume", 24, TEXT)
	resume_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER


func _panel(parent: Control, offset: Vector2, dimensions: Vector2, preset: int = Control.PRESET_TOP_LEFT) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.set_anchors_and_offsets_preset(preset)
	panel.position = offset
	panel.size = dimensions
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = INK
	style.border_color = Color(0.36, 0.44, 0.43, 0.45)
	style.set_border_width_all(1)
	style.content_margin_left = 16.0
	style.content_margin_right = 16.0
	style.content_margin_top = 10.0
	style.content_margin_bottom = 10.0
	panel.add_theme_stylebox_override("panel", style)
	parent.add_child(panel)
	return panel


func _label(parent: Control, text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	parent.add_child(label)
	return label


func _process(delta: float) -> void:
	if not is_instance_valid(_weapon):
		return
	var captured: bool = Input.mouse_mode == Input.MOUSE_MODE_CAPTURED or DisplayServer.get_name() == "headless"
	_hint.visible = not captured
	_reticle.visible = captured
	_reticle.set("aiming", bool(_weapon.get("is_aiming")))
	_reticle.set("spread", 6.0 + float(_weapon.get("recoil_amount")) * 12.0)
	_ammo.text = "%02d / %02d" % [int(_weapon.get("ammo")), int(_weapon.get("capacity"))]
	_status.text = "RELOADING..." if bool(_weapon.get("reloading")) else ("EMPTY  /  PRESS R" if int(_weapon.get("ammo")) == 0 else "READY")
	_point_time = maxf(0.0, _point_time - delta)
	_points.modulate.a = minf(_point_time * 4.0, 1.0)


func _update_stats() -> void:
	var shots: int = int(_session.get("shots"))
	var hits: int = int(_session.get("hits"))
	var accuracy: int = roundi(float(hits) / float(shots) * 100.0) if shots > 0 else 0
	_stats.text = "%04d PTS   %d / %d HITS   %d%%" % [int(_session.get("score")), hits, shots, accuracy]
	if shots == 0:
		_point_time = 0.0
		_reticle.set("hit_time", 0.0)


func _on_hit(points: int) -> void:
	_reticle.set("hit_time", 0.25)
	_point_time = 0.65
	_points.text = "+%d" % points
