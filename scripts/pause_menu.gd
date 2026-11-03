extends CanvasLayer
## A pause overlay that saves the player's mouse sensitivity on this PC.

const SETTINGS_PATH := "user://settings.cfg"
const MENU_FONT = preload("res://assets/fonts/menu_jp.otf")
const DEFAULT_SENSITIVITY: float = 0.002
const MIN_MULTIPLIER: float = 0.1
const MAX_MULTIPLIER: float = 3.0
const INK := Color(0.035, 0.055, 0.065, 0.98)
const TEXT := Color(0.93, 0.95, 0.93)
const MUTED := Color(0.66, 0.73, 0.73)
const AMBER := Color(1.0, 0.68, 0.30)

var is_open: bool = false
var sensitivity_slider: HSlider
var value_label: Label

var _overlay: Control
var _player: CharacterBody3D
var _weapon: Node3D
var _status_label: Label
var _save_timer: Timer
var _current_multiplier: float = 1.0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_player = get_node("../Player") as CharacterBody3D
	_weapon = get_node("../Player/Head/Camera3D/WeaponRig") as Node3D
	_build_interface()
	_load_settings()
	_overlay.hide()


func _input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and not event.is_echo():
		toggle_menu()
		get_viewport().set_input_as_handled()


func open_menu() -> void:
	if is_open:
		return
	is_open = true
	_cancel_pending_input()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_overlay.show()
	get_tree().paused = true
	sensitivity_slider.grab_focus()


func close_menu() -> void:
	if not is_open:
		return
	_save_timer.stop()
	_save_settings()
	_cancel_pending_input()
	is_open = false
	_overlay.hide()
	get_viewport().gui_release_focus()
	if DisplayServer.get_name() != "headless":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	get_tree().paused = false


func toggle_menu() -> void:
	if is_open:
		close_menu()
	else:
		open_menu()


func set_sensitivity_multiplier(value: float) -> void:
	_apply_sensitivity(value)
	_save_timer.start()


func restore_defaults() -> void:
	set_sensitivity_multiplier(1.0)


func _apply_sensitivity(multiplier: float) -> void:
	if not is_finite(multiplier):
		multiplier = 1.0
	var percentage: float = snappedf(clampf(multiplier, MIN_MULTIPLIER, MAX_MULTIPLIER) * 100.0, 1.0)
	_current_multiplier = percentage / 100.0
	sensitivity_slider.set_value_no_signal(percentage)
	_player.set("mouse_sensitivity", DEFAULT_SENSITIVITY * _current_multiplier)
	value_label.text = "%d%%  /  %.2fx" % [roundi(percentage), _current_multiplier]


func _load_settings() -> void:
	var config := ConfigFile.new()
	var multiplier: float = 1.0
	if config.load(SETTINGS_PATH) == OK:
		var saved: Variant = config.get_value("input", "mouse_sensitivity", DEFAULT_SENSITIVITY)
		if typeof(saved) == TYPE_FLOAT or typeof(saved) == TYPE_INT:
			multiplier = float(saved) / DEFAULT_SENSITIVITY
	_apply_sensitivity(multiplier)


func _save_settings() -> void:
	var config := ConfigFile.new()
	config.load(SETTINGS_PATH)
	config.set_value("input", "mouse_sensitivity", DEFAULT_SENSITIVITY * _current_multiplier)
	var result: Error = config.save(SETTINGS_PATH)
	if is_instance_valid(_status_label):
		_status_label.text = "設定はこのPCに自動保存されます" if result == OK else "設定を保存できませんでした"


func _cancel_pending_input() -> void:
	if is_instance_valid(_weapon) and _weapon.has_method("cancel_pending_input"):
		_weapon.call("cancel_pending_input")


func _build_interface() -> void:
	_overlay = Control.new()
	_overlay.name = "Overlay"
	_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_overlay)
	var theme := Theme.new()
	theme.default_font = MENU_FONT
	theme.default_font_size = 17
	_overlay.theme = theme
	var shade := ColorRect.new()
	shade.color = Color(0.005, 0.012, 0.018, 0.78)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	_overlay.add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay.add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(560.0, 0.0)
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	var panel_style := StyleBoxFlat.new()
	panel_style.bg_color = INK
	panel_style.border_color = Color(0.36, 0.44, 0.43, 0.8)
	panel_style.set_border_width_all(1)
	panel_style.set_corner_radius_all(10)
	panel_style.content_margin_left = 36.0
	panel_style.content_margin_right = 36.0
	panel_style.content_margin_top = 30.0
	panel_style.content_margin_bottom = 30.0
	panel.add_theme_stylebox_override("panel", panel_style)
	center.add_child(panel)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 18)
	panel.add_child(content)
	_label(content, "M1911  /  SETTINGS", 12, AMBER)
	_label(content, "設定", 32, TEXT)
	_label(content, "ゲームは一時停止中です", 14, MUTED)
	var divider := HSeparator.new()
	content.add_child(divider)
	var sensitivity_row := HBoxContainer.new()
	sensitivity_row.add_theme_constant_override("separation", 20)
	content.add_child(sensitivity_row)
	var sensitivity_label: Label = _label(sensitivity_row, "マウス感度", 19, TEXT)
	sensitivity_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	value_label = _label(sensitivity_row, "100%  /  1.00x", 20, AMBER)
	value_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	sensitivity_slider = HSlider.new()
	sensitivity_slider.name = "SensitivitySlider"
	sensitivity_slider.min_value = 10.0
	sensitivity_slider.max_value = 300.0
	sensitivity_slider.step = 1.0
	sensitivity_slider.value = 100.0
	sensitivity_slider.custom_minimum_size.y = 32.0
	sensitivity_slider.focus_mode = Control.FOCUS_ALL
	sensitivity_slider.add_theme_stylebox_override("slider", _track_style(Color(0.12, 0.17, 0.18)))
	sensitivity_slider.add_theme_stylebox_override("grabber_area", _track_style(AMBER.darkened(0.2)))
	sensitivity_slider.add_theme_stylebox_override("grabber_area_highlight", _track_style(AMBER))
	sensitivity_slider.value_changed.connect(_on_slider_changed)
	content.add_child(sensitivity_slider)
	var range_row := HBoxContainer.new()
	content.add_child(range_row)
	var slow: Label = _label(range_row, "ゆっくり  10%", 12, MUTED)
	slow.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(range_row, "速い  300%", 12, MUTED)
	var defaults: Button = _button(content, "感度を標準に戻す  （100%）", false)
	defaults.pressed.connect(restore_defaults)
	_status_label = _label(content, "設定はこのPCに自動保存されます", 12, MUTED)
	var spacer := Control.new()
	spacer.custom_minimum_size.y = 4.0
	content.add_child(spacer)
	var resume: Button = _button(content, "ゲームに戻る", true)
	resume.name = "ResumeButton"
	resume.pressed.connect(_on_resume_pressed)
	var quit_button: Button = _button(content, "ゲームを終了", false)
	quit_button.name = "QuitButton"
	quit_button.pressed.connect(_on_quit_pressed)
	var hint: Label = _label(content, "Esc キーでもゲームに戻れます", 12, MUTED)
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_save_timer = Timer.new()
	_save_timer.name = "SaveDelay"
	_save_timer.one_shot = true
	_save_timer.wait_time = 0.25
	_save_timer.timeout.connect(_save_settings)
	add_child(_save_timer)


func _on_slider_changed(percentage: float) -> void:
	set_sensitivity_multiplier(percentage / 100.0)


func _on_resume_pressed() -> void:
	close_menu()
	get_viewport().set_input_as_handled()


func _on_quit_pressed() -> void:
	_save_timer.stop()
	_save_settings()
	get_tree().quit()


func _track_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(3)
	style.content_margin_top = 4.0
	style.content_margin_bottom = 4.0
	return style


func _button(parent: Control, text: String, primary: bool) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = 44.0
	button.mouse_filter = Control.MOUSE_FILTER_STOP
	button.add_theme_font_size_override("font_size", 16)
	button.add_theme_color_override("font_color", Color(0.06, 0.08, 0.08) if primary else TEXT)
	button.add_theme_color_override("font_hover_color", Color(0.02, 0.04, 0.04) if primary else TEXT)
	button.add_theme_color_override("font_pressed_color", Color(0.02, 0.04, 0.04) if primary else TEXT)
	for state: String in ["normal", "hover", "pressed", "focus"]:
		var style := StyleBoxFlat.new()
		style.bg_color = AMBER if primary else Color(0.10, 0.15, 0.17)
		if state == "hover":
			style.bg_color = style.bg_color.lightened(0.12)
		elif state == "pressed":
			style.bg_color = style.bg_color.darkened(0.12)
		style.border_color = AMBER if state == "focus" else Color(0.28, 0.35, 0.35)
		style.set_border_width_all(1)
		style.set_corner_radius_all(4)
		button.add_theme_stylebox_override(state, style)
	parent.add_child(button)
	return button


func _label(parent: Control, text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	parent.add_child(label)
	return label


func _exit_tree() -> void:
	if is_open and get_tree() != null:
		get_tree().paused = false
