extends CanvasLayer
## The depot briefing, stash, live raid inventory, and extraction results.

const UI_FONT = preload("res://assets/fonts/menu_jp.otf")
const RETICLE = preload("res://scripts/reticle.gd")
const INK := Color(0.026, 0.034, 0.033, 0.96)
const PANEL := Color(0.044, 0.055, 0.051, 0.95)
const LINE := Color(0.24, 0.29, 0.25, 0.9)
const TEXT := Color(0.91, 0.92, 0.86)
const MUTED := Color(0.57, 0.63, 0.57)
const AMBER := Color(0.91, 0.69, 0.35)
const GREEN := Color(0.49, 0.68, 0.49)
const RED := Color(0.89, 0.31, 0.24)

var _session: Node
var _weapon: Node
var _snapshot: Dictionary = {}
var _poll_remaining: float = 0.0
var _base: Control
var _raid: Control
var _bag: Control
var _outcome: Control
var _damage_shade: ColorRect
var _reticle: Control
var _base_cash: Label
var _base_message: Label
var _stash_list: VBoxContainer
var _deploy: Button
var _recover: Button
var _supply_buttons: Dictionary = {}
var _objective: Label
var _clock: Label
var _kills: Label
var _heading: Label
var _extraction_distance: Label
var _health: Label
var _health_bar: ProgressBar
var _stamina_bar: ProgressBar
var _bleeding: Label
var _ammo: Label
var _reserve: Label
var _weapon_status: Label
var _interaction_panel: PanelContainer
var _interaction: Label
var _activity_panel: PanelContainer
var _activity: Label
var _activity_bar: ProgressBar
var _message: Label
var _threat: Label
var _bag_list: VBoxContainer
var _bag_usage: Label
var _bag_heal: Button
var _bag_message: Label
var _outcome_overline: Label
var _outcome_title: Label
var _outcome_message: Label
var _outcome_value: Label
var _outcome_rows: VBoxContainer
var _stash_signature: String = ""
var _bag_signature: String = ""
var _result_signature: String = ""


class DepotDiagram extends Control:

	var map_font: Font

	func _ready() -> void:
		resized.connect(queue_redraw)

	func _draw() -> void:
		var area := Rect2(Vector2(5, 5), size - Vector2(10, 10))
		draw_rect(area, Color(0.035, 0.046, 0.041))
		for i in range(1, 8):
			var px: float = area.position.x + area.size.x * i / 8.0
			var py: float = area.position.y + area.size.y * i / 8.0
			draw_line(Vector2(px, area.position.y), Vector2(px, area.end.y), Color(0.12, 0.16, 0.13), 1)
			draw_line(Vector2(area.position.x, py), Vector2(area.end.x, py), Color(0.12, 0.16, 0.13), 1)
		var buildings := [
			[Rect2(0.35, 0.28, 0.30, 0.38), "貨物倉庫"],
			[Rect2(0.10, 0.29, 0.18, 0.20), "事務所"],
			[Rect2(0.72, 0.43, 0.19, 0.20), "整備棟"]]
		for building: Array in buildings:
			var normalized: Rect2 = building[0]
			var rect := Rect2(area.position + normalized.position * area.size, normalized.size * area.size)
			draw_rect(rect, Color(0.17, 0.21, 0.17))
			draw_rect(rect, Color(0.41, 0.45, 0.35), false, 1)
			if map_font != null:
				draw_string(map_font, rect.position + Vector2(7, rect.size.y * 0.5 + 4), str(building[1]), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, TEXT)
		for column in 3:
			var container := Rect2(area.position + area.size * Vector2(0.10 + column * 0.067, 0.10), area.size * Vector2(0.045, 0.13))
			draw_rect(container, Color(0.27, 0.30, 0.22))
		var start: Vector2 = area.position + area.size * Vector2(0.12, 0.88)
		var finish: Vector2 = area.position + area.size * Vector2(0.88, 0.12)
		draw_circle(start, 5, AMBER)
		draw_circle(finish, 6, GREEN)
		draw_arc(finish, 11, 0, TAU, 32, Color(0.49, 0.68, 0.49, 0.45), 1)
		if map_font != null:
			draw_string(map_font, start + Vector2(10, 4), "進入", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, AMBER)
			draw_string(map_font, finish + Vector2(-66, -12), "退避門", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, GREEN)
			draw_string(map_font, area.position + Vector2(area.size.x * 0.50 - 5, 16), "N ↑", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, MUTED)
		draw_rect(area, LINE, false, 1)


func _ready() -> void:
	layer = 10
	process_mode = Node.PROCESS_MODE_ALWAYS
	_session = get_parent()
	_weapon = _session.get_node_or_null("Player/Head/Camera3D/WeaponRig")
	_build()
	if _session.has_signal("ui_changed"):
		_session.connect("ui_changed", _request_refresh)
	if is_instance_valid(_weapon) and _weapon.has_signal("target_hit"):
		_weapon.connect("target_hit", _on_target_hit)
	_refresh()


func _input(event: InputEvent) -> void:
	if get_tree().paused or event.is_echo() or str(_snapshot.get("phase", "base")) != "raid":
		return
	if InputMap.has_action("inventory") and event.is_action_pressed("inventory"):
		_invoke("toggle_inventory")
		get_viewport().set_input_as_handled()
	elif bool(_snapshot.get("inventory_open", false)) and event.is_action_pressed("ui_cancel"):
		_invoke("close_inventory")
		get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	_poll_remaining -= delta
	if _poll_remaining <= 0.0:
		_poll_remaining = 0.1
		_refresh()


func _build() -> void:
	var root := Control.new()
	root.name = "RaidInterface"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var theme := Theme.new()
	theme.default_font = UI_FONT
	theme.default_font_size = 16
	root.theme = theme
	add_child(root)
	_damage_shade = ColorRect.new()
	_damage_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_damage_shade.color = Color(0.55, 0.025, 0.015, 0)
	_damage_shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_damage_shade)
	_build_raid(root)
	_build_base(root)
	_build_bag(root)
	_build_outcome(root)


func _build_base(root: Control) -> void:
	_base = _screen(root, "BaseScreen", 0.89)
	var margin := _full_margin(_base, 24)
	var column := _vbox(margin, 14)
	var header := _hbox(column, 24)
	var brand := _vbox(header, 0)
	brand.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(brand, "ASHGATE", 42, TEXT)
	_label(brand, "SINGLE PLAYER  /  DEPOT 04", 11, AMBER)
	var account := _vbox(header, 3)
	_label(account, "保管資金", 12, MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_base_cash = _label(account, "0 CR", 25, TEXT)
	_base_cash.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	var body := _hbox(column, 22)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var left := _vbox(body, 14)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_stretch_ratio = 1.28
	var mission_panel := _container_panel(left, PANEL, 18)
	mission_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	var mission := _vbox(mission_panel, 8)
	var mission_heading := _hbox(mission, 12)
	_label(mission_heading, "DEPOT 04", 26, TEXT).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(mission_heading, "貨物倉庫地区", 13, MUTED)
	var diagram := DepotDiagram.new()
	diagram.map_font = UI_FONT
	diagram.custom_minimum_size = Vector2(400, 142)
	diagram.size_flags_vertical = Control.SIZE_EXPAND_FILL
	diagram.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mission.add_child(diagram)
	_label(mission, "南西から進入。北東の緑灯が退避門の目印。", 13, AMBER)
	var briefing := _label(mission, "倉庫を探索し、物資を回収して脱出する。\n生還すれば物資を保管。死亡すると携行品を失う。", 14, TEXT)
	briefing.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var equipment_panel := _container_panel(left, PANEL, 15)
	var equipment := _vbox(equipment_panel, 5)
	_label(equipment, "持ち込む装備", 12, MUTED)
	_label(equipment, "M1911  /  .45 ACP 最大35発  /  救急キット 最大1個", 15, TEXT)
	_label(equipment, "保管品から出撃時に持ち出します。", 11, MUTED)
	_deploy = _button(left, "DEPOT 04へ出撃", true, 52)
	_deploy.name = "DeployButton"
	_deploy.pressed.connect(func(): _invoke("start_raid"))
	var secondary := _hbox(left, 10)
	var practice := _button(secondary, "射撃場で練習", false, 34)
	practice.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	practice.pressed.connect(func(): _invoke("launch_practice"))
	var quit_button := _button(secondary, "ゲームを終了", false, 34)
	quit_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	quit_button.pressed.connect(func(): get_tree().quit())
	var right_panel := _container_panel(body, PANEL, 16)
	right_panel.custom_minimum_size.x = 410
	right_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var right := _vbox(right_panel, 8)
	_label(right, "倉庫", 23, TEXT)
	_label(right, "脱出して持ち帰った装備と物資", 12, MUTED)
	var scroll := _scroll(right, 120)
	_stash_list = _vbox(scroll, 5)
	_stash_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_separator(right)
	_label(right, "補給品を購入", 12, MUTED)
	for id: String in ["m1911", "ammo45", "medkit"]:
		var button := _button(right, "", false, 34)
		button.pressed.connect(_buy.bind(id))
		_supply_buttons[id] = button
	var sell := _button(right, "回収品をまとめて売却", false, 34)
	sell.pressed.connect(func(): _invoke("sell_valuables"))
	_recover = _button(right, "緊急補給を受け取る", false, 34)
	_recover.pressed.connect(func(): _invoke("claim_recovery_kit"))
	_base_message = _label(column, "出撃の準備ができています。", 13, MUTED)
	_base_message.custom_minimum_size.y = 20
	_base_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func _build_raid(root: Control) -> void:
	_raid = Control.new()
	_raid.name = "RaidHUD"
	_raid.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_raid.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(_raid)
	var objective_box := _vbox(_positioned_panel(_raid, Vector2(24, 24), Vector2(330, 116)), 4)
	_label(objective_box, "DEPOT 04  /  RAID", 11, AMBER)
	_objective = _label(objective_box, "北東の退避門から脱出", 15, TEXT)
	_objective.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_objective.custom_minimum_size = Vector2(294, 38)
	_extraction_distance = _label(objective_box, "北東の退避門", 11, MUTED)
	_heading = _label(_positioned_panel(_raid, Vector2(-72, 24), Vector2(144, 38), Control.PRESET_CENTER_TOP), "N  000°", 14, MUTED)
	_heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var timing := _vbox(_positioned_panel(_raid, Vector2(-230, 24), Vector2(206, 98), Control.PRESET_TOP_RIGHT), 2)
	_label(timing, "残り時間", 11, MUTED)
	_clock = _label(timing, "10:00", 29, TEXT)
	_kills = _label(timing, "敵排除  0", 12, MUTED)
	var vitals := _vbox(_positioned_panel(_raid, Vector2(24, -190), Vector2(255, 128), Control.PRESET_BOTTOM_LEFT), 4)
	var health_row := _hbox(vitals, 10)
	_label(health_row, "体力", 12, MUTED).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_health = _label(health_row, "100 / 100", 19, TEXT)
	_health_bar = _progress(vitals, GREEN, 7)
	_bleeding = _label(vitals, "", 12, RED)
	_label(vitals, "STAMINA", 9, MUTED)
	_stamina_bar = _progress(vitals, AMBER, 4)
	var ammo_box := _vbox(_positioned_panel(_raid, Vector2(-265, -178), Vector2(241, 116), Control.PRESET_BOTTOM_RIGHT), 1)
	_weapon_status = _label(ammo_box, "M1911  /  .45 ACP", 11, AMBER)
	var ammo_row := _hbox(ammo_box, 10)
	_ammo = _label(ammo_row, "07", 43, TEXT)
	_reserve = _label(ammo_row, "/ 28", 23, MUTED)
	_reserve.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_label(ammo_box, "左 射撃   右 照準   R 装填   N 確認", 10, MUTED)
	var hints := _label(_positioned_panel(_raid, Vector2(24, -48), Vector2(770, 30), Control.PRESET_BOTTOM_LEFT, 8), "WASD 移動    E 調べる    TAB 所持品    4 回復    SHIFT 走る    ESC 設定", 11, MUTED)
	hints.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_interaction_panel = _positioned_panel(_raid, Vector2(-250, -114), Vector2(500, 43), Control.PRESET_CENTER_BOTTOM)
	_interaction = _label(_interaction_panel, "", 17, TEXT)
	_interaction.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_activity_panel = _positioned_panel(_raid, Vector2(-210, -179), Vector2(420, 57), Control.PRESET_CENTER_BOTTOM)
	var activity_box := _vbox(_activity_panel, 6)
	_activity = _label(activity_box, "", 13, AMBER)
	_activity.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_activity_bar = _progress(activity_box, AMBER, 5)
	_message = _label(_raid, "", 16, TEXT)
	_set_anchor_rect(_message, Control.PRESET_CENTER_TOP, Vector2(-290, 130), Vector2(580, 32))
	_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_threat = _label(_raid, "", 12, RED)
	_set_anchor_rect(_threat, Control.PRESET_CENTER_TOP, Vector2(-240, 100), Vector2(480, 25))
	_threat.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_reticle = Control.new()
	_reticle.set_script(RETICLE)
	_reticle.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_reticle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_raid.add_child(_reticle)


func _build_bag(root: Control) -> void:
	_bag = _screen(root, "InventoryScreen", 0.48)
	var margin := _full_margin(_bag, 52)
	var row := _hbox(margin, 24)
	var panel := _container_panel(row, INK, 22)
	panel.custom_minimum_size.x = 510
	var bag_box := _vbox(panel, 13)
	var heading := _hbox(bag_box, 16)
	_label(heading, "携行品", 27, TEXT).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_bag_usage = _label(heading, "0 / 12", 15, AMBER)
	_label(bag_box, "出撃中も周囲の時間は進みます。", 12, AMBER)
	var scroll := _scroll(bag_box, 200)
	_bag_list = _vbox(scroll, 7)
	_bag_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_separator(bag_box)
	_bag_message = _label(bag_box, "", 13, MUTED)
	_bag_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_bag_heal = _button(bag_box, "救急キットで治療  [4]", false, 41)
	_bag_heal.pressed.connect(func(): _invoke("start_heal"))
	var close := _button(bag_box, "所持品を閉じる  [TAB / ESC]", true, 43)
	close.name = "CloseInventoryButton"
	close.pressed.connect(func(): _invoke("close_inventory"))
	var instructions := _vbox(row, 10)
	instructions.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(instructions, "持ち帰るまでが任務", 24, TEXT)
	_label(instructions, "物資は退避門から脱出すると倉庫へ保管されます。\n死亡した場合、今回の装備と携行品は失われます。", 16, TEXT).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_label(instructions, "退避地点：北東の退避門\n緑色の灯りの下で待機すると脱出できます。", 15, MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_label(instructions, "弾薬は予備弾として別に携行します。\n回復中に攻撃を受けると、治療が中断されます。", 14, MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART


func _build_outcome(root: Control) -> void:
	_outcome = _screen(root, "OutcomeScreen", 0.85)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_outcome.add_child(center)
	var panel := _container_panel(center, INK, 30)
	panel.custom_minimum_size = Vector2(620, 0)
	var box := _vbox(panel, 13)
	_outcome_overline = _label(box, "RAID COMPLETE", 12, GREEN)
	_outcome_title = _label(box, "生還", 42, TEXT)
	_outcome_message = _label(box, "", 16, TEXT)
	_outcome_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_outcome_message.custom_minimum_size.x = 550
	_outcome_value = _label(box, "", 21, AMBER)
	var results_scroll := _scroll(box, 200)
	_outcome_rows = _vbox(results_scroll, 5)
	_outcome_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_separator(box)
	var home := _button(box, "拠点へ戻る", true, 48)
	home.name = "ReturnToBaseButton"
	home.pressed.connect(func(): _invoke("return_to_base"))
	_label(box, "保管品を整理して、次の出撃に備えてください。", 12, MUTED)


func _refresh() -> void:
	if not is_instance_valid(_session) or not _session.has_method("get_ui_snapshot"):
		return
	var next: Variant = _session.call("get_ui_snapshot")
	if not next is Dictionary:
		return
	_snapshot = next
	var phase: String = str(_snapshot.get("phase", "base"))
	var bag_open: bool = phase == "raid" and bool(_snapshot.get("inventory_open", false))
	_base.visible = phase == "base"
	_raid.visible = phase == "raid"
	_bag.visible = bag_open
	_outcome.visible = phase == "extracted" or phase == "dead"
	_damage_shade.color.a = clampf(float(_snapshot.get("damage_flash", 0.0)), 0, 1) * 0.19 if phase == "raid" else 0.0
	_refresh_base()
	_refresh_raid(bag_open)
	_refresh_bag()
	_refresh_outcome(phase)


func _refresh_base() -> void:
	var credits: int = int(_snapshot.get("credits", 0))
	_base_cash.text = "%s CR" % _number(credits)
	var can_deploy: bool = bool(_snapshot.get("can_deploy", false))
	_deploy.disabled = not can_deploy
	_deploy.text = "DEPOT 04へ出撃" if can_deploy else "装備と弾薬が必要です"
	_recover.visible = not can_deploy and bool(_snapshot.get("can_recover", true))
	var prices: Dictionary = _snapshot.get("supply_prices", {"m1911": 1800, "ammo45": 250, "medkit": 350})
	var names := {"m1911": "M1911 ×1", "ammo45": ".45 ACP ×21", "medkit": "救急キット ×1"}
	for id: String in _supply_buttons:
		var price: int = int(prices.get(id, 0))
		var button: Button = _supply_buttons[id]
		button.text = "%s を購入    %s CR" % [names[id], _number(price)]
		button.disabled = credits < price
	var message: String = str(_snapshot.get("message", ""))
	if not bool(_snapshot.get("saved_ok", true)):
		message = "進行状況を保存できませんでした。空き容量と保存先を確認してください。"
	_base_message.text = message if not message.is_empty() else ("出撃の準備ができています。" if can_deploy else "倉庫の装備と弾薬を確認するか、補給品を購入してください。")
	var rows: Array = _snapshot.get("stash_rows", [])
	var signature: String = JSON.stringify(rows)
	if signature != _stash_signature:
		_stash_signature = signature
		_render_rows(_stash_list, rows, false)


func _refresh_raid(bag_open: bool) -> void:
	_objective.text = str(_snapshot.get("objective", "物資を回収し、北東の退避門へ"))
	var extraction_distance: float = float(_snapshot.get("extraction_distance", -1.0))
	_extraction_distance.text = "退避門まで  %dm  /  緑の灯り" % ceili(extraction_distance) if extraction_distance >= 0 else "北東の退避門  /  緑の灯り"
	var seconds: int = maxi(0, ceili(float(_snapshot.get("time_left", 0))))
	_clock.text = "%02d:%02d" % [seconds / 60, seconds % 60]
	_clock.add_theme_color_override("font_color", RED if seconds < 120 else TEXT)
	_kills.text = "敵排除  %d" % int(_snapshot.get("kills", 0))
	var heading: float = float(_snapshot.get("heading_degrees", -1.0))
	if heading < 0:
		var actor := _session.get_node_or_null("Player") as Node3D
		heading = fposmod(-rad_to_deg(actor.rotation.y), 360.0) if actor != null else 0.0
	var cardinals := ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
	_heading.text = "%s  %03d°" % [cardinals[int(floor((heading + 22.5) / 45.0)) % 8], roundi(heading) % 360]
	var health: float = float(_snapshot.get("health", 100))
	var maximum: float = maxf(1, float(_snapshot.get("max_health", 100)))
	_health.text = "%03d / %03d" % [roundi(health), roundi(maximum)]
	_health.add_theme_color_override("font_color", RED if health <= 30 else TEXT)
	_health_bar.value = clampf(health / maximum * 100.0, 0, 100)
	_stamina_bar.value = clampf(float(_snapshot.get("stamina", 100)), 0, 100)
	_bleeding.text = "出血中  /  4で治療" if bool(_snapshot.get("bleeding", false)) else ""
	_ammo.text = "%02d" % int(_snapshot.get("ammo", 0))
	_reserve.text = "/ %02d" % int(_snapshot.get("reserve", 0))
	var inspecting: bool = bool(_snapshot.get("is_inspecting", _weapon.get("is_inspecting") if is_instance_valid(_weapon) else false))
	var aiming: bool = bool(_snapshot.get("is_aiming", _weapon.get("is_aiming") if is_instance_valid(_weapon) else false))
	var reloading: bool = bool(_snapshot.get("reloading", false))
	_weapon_status.text = "銃を確認中" if inspecting else ("装填中…" if reloading else "M1911  /  .45 ACP")
	if int(_snapshot.get("ammo", 0)) == 0 and not inspecting and not reloading:
		_weapon_status.text = "弾切れ  /  Rで装填" if int(_snapshot.get("reserve", 0)) > 0 else "弾薬なし"
	var prompt: String = str(_snapshot.get("interaction_prompt", ""))
	_interaction_panel.visible = not bag_open and not prompt.is_empty() and not inspecting
	_interaction.text = prompt
	var activity: String = str(_snapshot.get("activity_label", ""))
	var progress: float = float(_snapshot.get("activity_progress", 0.0))
	if activity.is_empty() and float(_snapshot.get("extract_progress", 0)) > 0:
		activity = "退避門で待機中"
		progress = float(_snapshot.get("extract_progress", 0))
	elif activity.is_empty() and float(_snapshot.get("healing_progress", 0)) > 0:
		activity = "治療中…"
		progress = float(_snapshot.get("healing_progress", 0))
	_activity_panel.visible = not activity.is_empty()
	_activity.text = activity
	_activity_bar.value = clampf(progress * 100.0, 0, 100)
	_message.text = str(_snapshot.get("message", ""))
	var threat: Variant = _snapshot.get("threat", "")
	_threat.text = "周囲に敵影" if threat is bool and threat else (str(threat) if not threat is bool else "")
	var weapon_enabled: bool = bool(_weapon.get("controls_enabled")) if is_instance_valid(_weapon) else true
	_reticle.visible = not bag_open and not get_tree().paused and not inspecting and weapon_enabled
	_reticle.set("aiming", aiming)
	_reticle.set("spread", 6.0 + float(_snapshot.get("recoil", 0.0)) * 12.0)


func _refresh_bag() -> void:
	var rows: Array = _snapshot.get("carried_rows", [])
	var signature: String = JSON.stringify(rows)
	if signature != _bag_signature:
		_bag_signature = signature
		_render_rows(_bag_list, rows, true)
	_bag_usage.text = "%d / %d スロット" % [int(_snapshot.get("used_slots", 0)), int(_snapshot.get("bag_capacity", 12))]
	var medkits: int = 0
	var total_value: int = 0
	for row: Dictionary in rows:
		if str(row.get("id", "")) == "medkit":
			medkits = int(row.get("count", 0))
		total_value += int(row.get("total_value", int(row.get("value", 0)) * int(row.get("count", 0))))
	var can_heal: bool = medkits > 0 and (float(_snapshot.get("health", 100)) < float(_snapshot.get("max_health", 100)) or bool(_snapshot.get("bleeding", false)))
	_bag_heal.disabled = not can_heal or float(_snapshot.get("healing_progress", 0)) > 0
	_bag_message.text = "予備弾薬 %d発  /  回収品の推定価値 %s CR" % [int(_snapshot.get("reserve", 0)), _number(total_value)]


func _refresh_outcome(phase: String) -> void:
	var extracted: bool = phase == "extracted"
	_outcome_overline.text = "EXTRACTED" if extracted else "RAID LOST"
	_outcome_overline.add_theme_color_override("font_color", GREEN if extracted else RED)
	_outcome_title.text = "生還" if extracted else "帰還できなかった"
	_outcome_title.add_theme_color_override("font_color", TEXT if extracted else RED)
	_outcome_message.text = str(_snapshot.get("result_message", "回収した物資を倉庫へ保管しました。" if extracted else "携行していた装備・物資を失いました。\n倉庫の保管品は残っています。"))
	_outcome_value.visible = extracted
	_outcome_value.text = "持ち帰った物資の価値  %s CR" % _number(int(_snapshot.get("extracted_value", 0)))
	var rows: Array = _snapshot.get("result_rows", [])
	_outcome_rows.get_parent().visible = extracted and not rows.is_empty()
	var signature: String = JSON.stringify(rows)
	if signature != _result_signature:
		_result_signature = signature
		_render_rows(_outcome_rows, rows, false, false)


func _render_rows(container: VBoxContainer, rows: Array, can_drop: bool, show_empty: bool = true) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()
	if rows.is_empty():
		if show_empty:
			_label(container, "保管品はありません。" if not can_drop else "まだ物資を回収していません。", 13, MUTED)
		return
	for entry: Variant in rows:
		if not entry is Dictionary:
			continue
		var data: Dictionary = entry
		var id: String = str(data.get("id", ""))
		var panel := _container_panel(container, Color(0.065, 0.080, 0.068, 0.95), 9)
		var row := _hbox(panel, 12)
		var indicator := ColorRect.new()
		indicator.color = AMBER if id in ["electronics", "parts", "food", "tools"] else GREEN
		indicator.custom_minimum_size = Vector2(3, 26)
		indicator.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(indicator)
		var name_box := _vbox(row, 1)
		name_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_label(name_box, str(data.get("name", id)), 14, TEXT)
		var value: int = int(data.get("total_value", int(data.get("value", 0)) * int(data.get("count", 0))))
		if value > 0:
			_label(name_box, "%s CR" % _number(value), 10, MUTED)
		_label(row, "×%d" % int(data.get("count", 0)), 16, TEXT).size_flags_vertical = Control.SIZE_SHRINK_CENTER
		if can_drop:
			var drop := _button(row, "捨てる", false, 28)
			drop.add_theme_font_size_override("font_size", 11)
			drop.pressed.connect(_drop.bind(id))


func _invoke(method: String) -> void:
	if is_instance_valid(_session) and _session.has_method(method):
		_session.call(method)
		_refresh()


func _buy(id: String) -> void:
	if is_instance_valid(_session) and _session.has_method("buy_supply"):
		_session.call("buy_supply", id)
		_refresh()


func _drop(id: String) -> void:
	if is_instance_valid(_session) and _session.has_method("drop_carried"):
		_session.call("drop_carried", id)
		_refresh()


func _request_refresh() -> void:
	_poll_remaining = 0.0


func _on_target_hit(_points: int) -> void:
	if is_instance_valid(_reticle):
		_reticle.set("hit_time", 0.25)


func _screen(parent: Control, node_name: String, shade_alpha: float) -> Control:
	var screen := Control.new()
	screen.name = node_name
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.mouse_filter = Control.MOUSE_FILTER_STOP
	parent.add_child(screen)
	var shade := ColorRect.new()
	shade.color = Color(0.012, 0.019, 0.016, shade_alpha)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	screen.add_child(shade)
	return screen


func _full_margin(parent: Control, inset: int) -> MarginContainer:
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, inset)
	parent.add_child(margin)
	return margin


func _container_panel(parent: Control, color: Color, padding: int) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _style(color, LINE, padding))
	parent.add_child(panel)
	return panel


func _positioned_panel(parent: Control, offset: Vector2, dimensions: Vector2, preset: int = Control.PRESET_TOP_LEFT, padding: int = 12) -> PanelContainer:
	var panel := _container_panel(parent, Color(0.025, 0.036, 0.030, 0.84), padding)
	_set_anchor_rect(panel, preset, offset, dimensions)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return panel


func _set_anchor_rect(control: Control, preset: int, offset: Vector2, dimensions: Vector2) -> void:
	# Offsets remain relative to the selected anchor when the viewport resizes.
	control.set_anchors_preset(preset)
	control.offset_left = offset.x
	control.offset_top = offset.y
	control.offset_right = offset.x + dimensions.x
	control.offset_bottom = offset.y + dimensions.y


func _style(color: Color, border: Color, padding: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(2)
	style.content_margin_left = padding
	style.content_margin_right = padding
	style.content_margin_top = padding
	style.content_margin_bottom = padding
	return style


func _label(parent: Control, text: String, font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	parent.add_child(label)
	return label


func _button(parent: Control, text: String, primary: bool, height: float) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size.y = height
	button.mouse_filter = Control.MOUSE_FILTER_STOP
	button.add_theme_font_size_override("font_size", 15)
	button.add_theme_color_override("font_color", Color(0.04, 0.05, 0.04) if primary else TEXT)
	button.add_theme_color_override("font_hover_color", Color(0.02, 0.03, 0.02) if primary else TEXT)
	button.add_theme_color_override("font_pressed_color", Color(0.02, 0.03, 0.02) if primary else TEXT)
	button.add_theme_color_override("font_disabled_color", Color(0.40, 0.45, 0.39))
	for state: String in ["normal", "hover", "pressed", "focus", "disabled"]:
		var color: Color = AMBER if primary else Color(0.085, 0.11, 0.088)
		if state == "hover":
			color = color.lightened(0.13)
		elif state == "pressed":
			color = color.darkened(0.12)
		elif state == "disabled":
			color = Color(0.07, 0.085, 0.071)
		button.add_theme_stylebox_override(state, _style(color, AMBER if state == "focus" else LINE, 8))
	parent.add_child(button)
	return button


func _vbox(parent: Control, separation: int) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", separation)
	parent.add_child(box)
	return box


func _hbox(parent: Control, separation: int) -> HBoxContainer:
	var box := HBoxContainer.new()
	box.add_theme_constant_override("separation", separation)
	parent.add_child(box)
	return box


func _scroll(parent: Control, minimum_height: int) -> ScrollContainer:
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size.y = minimum_height
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(scroll)
	return scroll


func _separator(parent: Control) -> void:
	var line := HSeparator.new()
	line.add_theme_color_override("separator", LINE)
	parent.add_child(line)


func _progress(parent: Control, color: Color, height: float) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.max_value = 100
	bar.custom_minimum_size.y = height
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.add_theme_stylebox_override("background", _style(Color(0.10, 0.13, 0.10), Color(0, 0, 0, 0), 0))
	bar.add_theme_stylebox_override("fill", _style(color, Color(0, 0, 0, 0), 0))
	parent.add_child(bar)
	return bar


func _number(value: int) -> String:
	var digits := str(absi(value))
	var result := ""
	for index in digits.length():
		if index > 0 and (digits.length() - index) % 3 == 0:
			result += ","
		result += digits[index]
	return ("-" if value < 0 else "") + result
