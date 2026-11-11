extends Node3D
## A single-player deployment is committed before entering the world.
## Only a successful extraction returns the weapon and remaining supplies.

signal ui_changed

const INVENTORY = preload("res://scripts/raid_inventory.gd")
const ENEMY = preload("res://scripts/raid_enemy.gd")
const LOOT = preload("res://scripts/raid_loot.gd")
const MAX_RESERVE: int = 140

@export var profile_path: String = "user://ashgate_profile_v1.json"
@export var raid_duration: float = 600.0
@export var extraction_duration: float = 6.0
@export var search_duration: float = 1.1
@export var heal_duration: float = 2.4

@onready var player = $Player
@onready var weapon = $Player/Head/Camera3D/WeaponRig
@onready var world = $World

var inventory = INVENTORY.new()
var phase: String = "base"
var inventory_open: bool = false
var time_left: float = 600.0
var kills: int = 0
var shots: int = 0
var hits: int = 0
var extraction_elapsed: float = 0.0
var heal_remaining: float = 0.0
var search_remaining: float = 0.0
var damage_flash: float = 0.0
var hit_flash: float = 0.0
var result_message: String = ""
var extracted_value: int = 0
var result_rows: Array = []
var _message: String = ""
var _message_remaining: float = 0.0
var _noise_remaining: float = 0.0
var _search_target: Node3D
var _interaction_target: Node3D
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	DisplayServer.window_set_title("ASHGATE / DEPOT 04 — Solo PvE")
	inventory.save_path = profile_path
	inventory.load_profile()
	_rng.randomize()
	weapon.shot_fired.connect(_on_shot_fired)
	weapon.target_hit.connect(_on_target_hit)
	player.damaged.connect(_on_player_damaged)
	player.died.connect(_on_player_died)
	player.set_spawn_transform(world.get_spawn_transform())
	player.respawn()
	_set_controls(false)
	weapon.hide()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_message = inventory.last_notice if inventory.saved_ok else inventory.last_error
	ui_changed.emit()


func _unhandled_input(event: InputEvent) -> void:
	if phase != "raid" or get_tree().paused or event.is_echo():
		return
	if event.is_action_pressed("heal"):
		start_heal()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("interact") and not inventory_open:
		if search_remaining > 0.0:
			_cancel_activity()
		elif is_instance_valid(_interaction_target):
			search_container(_interaction_target)
		get_viewport().set_input_as_handled()


func _physics_process(delta: float) -> void:
	damage_flash = maxf(0.0, damage_flash - delta * 2.5)
	hit_flash = maxf(0.0, hit_flash - delta * 4.0)
	_noise_remaining = maxf(0.0, _noise_remaining - delta)
	if _message_remaining > 0.0:
		_message_remaining = maxf(0.0, _message_remaining - delta)
		if _message_remaining == 0.0:
			_message = ""
	if phase != "raid":
		return
	time_left = maxf(0.0, time_left - delta)
	if time_left <= 0.0:
		_end_death("制限時間内に脱出できませんでした。\n携行していた装備・物資を失いました。")
		return
	_update_interaction()
	if heal_remaining > 0.0:
		heal_remaining = maxf(0.0, heal_remaining - delta)
		if heal_remaining == 0.0:
			if inventory.remove_item("medkit", 1):
				player.heal(45.0)
				_toast("治療が完了しました。出血を止め、体力を回復しました。")
			_update_controls()
	if search_remaining > 0.0:
		if not _can_search(_search_target):
			_cancel_activity()
			_toast("調査を中断しました。ケースの近くで調べてください。")
		else:
			search_remaining = maxf(0.0, search_remaining - delta)
			if search_remaining == 0.0:
				_take_loot(_search_target)
				_search_target = null
				_update_controls()
	var exit_position: Vector3 = world.get_extraction_position()
	var offset: Vector3 = player.global_position - exit_position
	# Match the marked bay, including the space immediately below the gate.
	if absf(offset.x) <= 4.5 and absf(offset.z) <= 4.4 and absf(offset.y) < 2.0:
		extraction_elapsed += delta
		if extraction_elapsed >= extraction_duration:
			finish_extraction()
	else:
		extraction_elapsed = 0.0


func start_raid() -> bool:
	if phase != "base":
		return false
	var kit: Dictionary = inventory.begin_raid()
	if not bool(kit.get("ok", false)):
		_toast(str(kit.get("error", "出撃できません。")))
		return false
	_clear_actors()
	phase = "raid"
	inventory_open = false
	time_left = raid_duration
	kills = 0
	shots = 0
	hits = 0
	extraction_elapsed = 0.0
	damage_flash = 0.0
	hit_flash = 0.0
	result_rows.clear()
	result_message = ""
	extracted_value = 0
	_cancel_activity()
	player.set_spawn_transform(world.get_spawn_transform())
	player.respawn()
	player.health_enabled = true
	player.collision_mask = 5
	weapon.reset_weapon()
	weapon.unlimited_ammo = false
	weapon.ammo = int(kit["loaded_ammo"])
	weapon.reserve_ammo = int(kit["reserve_ammo"])
	weapon.show()
	_spawn_actors()
	_update_controls()
	_toast("物資を回収し、北東の緑の退避門へ。Eで調査 / TABでバッグ / 4で治療", 8.0)
	ui_changed.emit()
	return true


func return_to_base() -> void:
	if phase != "extracted" and phase != "dead":
		return
	phase = "base"
	inventory_open = false
	_clear_actors()
	player.health_enabled = false
	player.respawn()
	weapon.hide()
	_set_controls(false)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_message = "回収品を売却して補給品を購入できます。" if inventory.saved_ok else inventory.last_error
	_message_remaining = 0.0
	ui_changed.emit()


func _spawn_actors() -> void:
	var index: int = 0
	for entry: Dictionary in world.get_enemy_spawns():
		var enemy = ENEMY.new()
		enemy.name = "Guard%02d" % index
		enemy.session = self
		enemy.enemy_id = index
		enemy.display_name = str(entry.get("name", "警備員"))
		enemy.patrol_route = entry.get("route", PackedVector3Array())
		enemy.position = entry["position"]
		$Enemies.add_child(enemy)
		index += 1
	for entry: Dictionary in world.get_loot_spawns():
		var item = LOOT.new()
		item.name = "Case%02d" % $Loot.get_child_count()
		item.display_name = str(entry.get("label", "物資ケース"))
		item.loot_kind = str(entry.get("kind", "supplies"))
		item.contents = _roll_loot(item.loot_kind)
		item.position = entry["position"]
		$Loot.add_child(item)


func _clear_actors() -> void:
	_interaction_target = null
	_search_target = null
	for parent: Node in [$Enemies, $Loot]:
		for child: Node in parent.get_children():
			parent.remove_child(child)
			child.queue_free()


func _roll_loot(kind: String) -> Dictionary:
	match kind:
		"medical": return {"medkit": _rng.randi_range(1, 2), "food": 1}
		"ammo": return {"ammo45": _rng.randi_range(14, 28), "parts": 1}
		"weapon": return {"m1911": 1, "ammo45": 7}
		"valuable": return {"electronics": _rng.randi_range(1, 2), "tools": 1}
		"corpse":
			var drops := {"ammo45": _rng.randi_range(7, 14), "parts": 1}
			if _rng.randf() < 0.25:
				drops["medkit"] = 1
			if _rng.randf() < 0.20:
				drops["m1911"] = 1
			return drops
		_: return {"parts": _rng.randi_range(2, 6), "food": _rng.randi_range(1, 2), "tools": 1}


func _update_interaction() -> void:
	_interaction_target = null
	if inventory_open or heal_remaining > 0.0 or search_remaining > 0.0:
		return
	var camera: Camera3D = player.camera
	var query := PhysicsRayQueryParameters3D.create(camera.global_position, camera.global_position - camera.global_basis.z * 3.5, 9)
	query.exclude = [player.get_rid()]
	var result: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	var collider: Object = result.get("collider")
	if collider is Node3D and collider.has_method("get_prompt"):
		_interaction_target = collider as Node3D


func _can_search(target: Node3D) -> bool:
	if not is_instance_valid(target) or not target.is_inside_tree() or not target.has_method("get_interaction_point"):
		return false
	var origin: Vector3 = player.camera.global_position
	var point: Vector3 = target.get_interaction_point()
	if origin.distance_to(point) > 3.5:
		return false
	var query := PhysicsRayQueryParameters3D.create(origin, point, 9)
	query.exclude = [player.get_rid()]
	var result: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	return result.is_empty() or result.get("collider") == target


func search_container(target: Node3D) -> bool:
	if phase != "raid" or inventory_open or heal_remaining > 0.0 or search_remaining > 0.0 or not _can_search(target):
		return false
	if target.is_empty():
		_toast("このケースは空です。")
		return false
	_search_target = target
	search_remaining = search_duration
	weapon.cancel_pending_input()
	weapon.cancel_reload()
	_update_controls()
	return true


func _take_loot(target: Node3D) -> void:
	if not is_instance_valid(target):
		return
	var found: Array[String] = []
	var blocked: bool = false
	for item_id: String in target.contents.keys():
		var available: int = int(target.contents[item_id])
		var taken: int = 0
		if item_id == "ammo45":
			taken = mini(available, maxi(0, MAX_RESERVE - weapon.reserve_ammo))
			weapon.reserve_ammo += taken
		else:
			for _unit in range(available):
				if not inventory.add_loot(item_id, 1):
					break
				taken += 1
		target.contents[item_id] = available - taken
		if taken > 0:
			found.append("%s ×%d" % [INVENTORY.ITEMS[item_id]["name"], taken])
		if taken < available:
			blocked = true
	target.searched = true
	var description: String = " / ".join(found)
	if blocked:
		description += "  空き容量が不足しています。残りはケースにあります。"
	_toast(description if not description.is_empty() else "ケースは空でした。", 6.0)
	ui_changed.emit()


func start_heal() -> bool:
	if phase != "raid":
		return false
	if heal_remaining > 0.0:
		_cancel_activity()
		_toast("治療を中断しました。")
		return false
	if inventory.get_count("medkit") < 1:
		_toast("救急キットを持っていません。")
		return false
	if player.health >= player.max_health and not player.bleeding:
		_toast("治療の必要はありません。")
		return false
	_cancel_activity()
	heal_remaining = heal_duration
	weapon.cancel_pending_input()
	weapon.cancel_reload()
	_update_controls()
	return true


func _cancel_activity() -> void:
	heal_remaining = 0.0
	search_remaining = 0.0
	_search_target = null
	if is_instance_valid(player) and is_instance_valid(weapon):
		_update_controls()


func toggle_inventory() -> void:
	if phase != "raid" or get_tree().paused:
		return
	inventory_open = not inventory_open
	_cancel_activity()
	weapon.cancel_pending_input()
	_update_controls()
	ui_changed.emit()


func close_inventory() -> void:
	if inventory_open:
		toggle_inventory()


func drop_carried(item_id: String) -> void:
	if phase == "raid" and inventory_open and inventory.remove_item(item_id, 1):
		_toast("%sを1個捨てました。" % str(INVENTORY.ITEMS[item_id]["name"]))
		ui_changed.emit()


func can_pause() -> bool:
	return phase == "raid" and not inventory_open


func _set_controls(enabled: bool) -> void:
	player.controls_enabled = enabled
	weapon.controls_enabled = enabled
	if not enabled:
		weapon.cancel_pending_input()


func _update_controls() -> void:
	var active: bool = phase == "raid" and not inventory_open
	player.controls_enabled = active
	weapon.controls_enabled = active and heal_remaining <= 0.0 and search_remaining <= 0.0
	player.movement_multiplier = 0.45 if heal_remaining > 0.0 or search_remaining > 0.0 else 1.0
	if DisplayServer.get_name() != "headless":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if active else Input.MOUSE_MODE_VISIBLE


func finish_extraction() -> bool:
	if phase != "raid":
		return false
	weapon.cancel_reload()
	var recovered_rows: Array = inventory.get_carried_rows()
	var outcome: Dictionary = inventory.finish_extraction(weapon.ammo, weapon.reserve_ammo)
	if not bool(outcome.get("ok", false)):
		extraction_elapsed = 0.0
		_toast(str(outcome.get("error", "持ち帰りを保存できません。")), 8.0)
		return false
	phase = "extracted"
	inventory_open = false
	result_rows = recovered_rows
	extracted_value = int(outcome["value"])
	result_message = "装備と残弾、回収した物資を倉庫へ保管しました。\n脱出報酬 +%d CR" % int(outcome["bonus"])
	_end_controls()
	return true


func _on_player_died() -> void:
	_end_death("携行していた装備・物資を失いました。\n倉庫に保管していた物資は残っています。")


func _end_death(description: String) -> void:
	if phase != "raid":
		return
	phase = "dead"
	inventory_open = false
	result_rows.clear()
	result_message = description
	inventory.finish_death()
	if not inventory.saved_ok:
		result_message += "\n" + inventory.last_error
	_end_controls()


func _end_controls() -> void:
	_cancel_activity()
	_set_controls(false)
	player.health_enabled = false
	weapon.cancel_reload()
	weapon.hide()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	ui_changed.emit()


func _on_player_damaged(_amount: float) -> void:
	damage_flash = 1.0
	if heal_remaining > 0.0 or search_remaining > 0.0:
		_cancel_activity()
		_toast("攻撃を受け、作業を中断しました。")


func _on_shot_fired() -> void:
	if phase != "raid":
		return
	shots += 1
	_noise_remaining = 1.5
	for enemy: Node in $Enemies.get_children():
		enemy.hear_noise(player.global_position, 32.0)


func _on_target_hit(_points: int) -> void:
	hits += 1
	hit_flash = 1.0


func on_enemy_killed(enemy: Node3D) -> void:
	if phase != "raid":
		return
	kills += 1
	_spawn_corpse_loot.call_deferred(enemy.global_position)
	_toast("敵を排除しました。落とした物資をEで回収できます。")


func _spawn_corpse_loot(origin: Vector3) -> void:
	if phase != "raid":
		return
	var item = LOOT.new()
	item.display_name = "警備員のバッグ"
	item.loot_kind = "corpse"
	item.is_corpse = true
	item.contents = _roll_loot("corpse")
	item.position = origin + Vector3(0.45, 0.02, 0)
	$Loot.add_child(item)


func get_player_noise() -> float:
	if phase != "raid":
		return 0.0
	if _noise_remaining > 0.0:
		return 2.0
	var speed := Vector2(player.velocity.x, player.velocity.z).length()
	return 1.0 if speed > 5.0 else (0.4 if speed > 0.8 else 0.0)


func get_navigation_path(from: Vector3, to: Vector3) -> PackedVector3Array:
	return world.find_path(from, to)


func buy_supply(item_id: String) -> void:
	if phase != "base":
		return
	var result: Dictionary = inventory.buy(item_id)
	_toast("補給品を倉庫に追加しました。" if bool(result.get("ok", false)) else str(result.get("error", "購入できません。")))
	ui_changed.emit()


func sell_valuables() -> void:
	if phase != "base":
		return
	var result: Dictionary = inventory.sell_valuables()
	_toast("回収品を売却しました。 +%d CR" % int(result.get("gained", 0)) if bool(result.get("ok", false)) else str(result.get("error", "売却できません。")))
	ui_changed.emit()


func claim_recovery_kit() -> void:
	if phase != "base":
		return
	_toast("最低限の再出撃用キットを受け取りました。" if inventory.claim_recovery_kit() else "購入できる装備を確認してください。")
	ui_changed.emit()


func launch_practice() -> void:
	if phase == "base":
		get_tree().change_scene_to_file("res://scenes/main.tscn")


func _toast(text: String, duration: float = 4.0) -> void:
	_message = text
	_message_remaining = duration


func get_ui_snapshot() -> Dictionary:
	if not is_instance_valid(player) or not is_instance_valid(weapon) or not is_instance_valid(world):
		return {"phase": "base", "can_deploy": false, "message": "保管庫を読み込み中…"}
	var activity: String = ""
	var progress: float = 0.0
	if heal_remaining > 0.0:
		activity = "治療中…  /  4で中断"
		progress = 1.0 - heal_remaining / heal_duration
	elif search_remaining > 0.0:
		activity = "ケースを調査中…  /  Eで中断"
		progress = 1.0 - search_remaining / search_duration
	elif extraction_elapsed > 0.0:
		activity = "脱出まで %.1f 秒  /  緑の灯りの下で待機" % maxf(0, extraction_duration - extraction_elapsed)
		progress = extraction_elapsed / extraction_duration
	var prices: Dictionary = {}
	for id: String in INVENTORY.SHOP:
		prices[id] = INVENTORY.SHOP[id]["price"]
	return {
		"phase": phase, "inventory_open": inventory_open,
		"health": player.health, "max_health": player.max_health, "stamina": player.stamina, "bleeding": player.bleeding,
		"ammo": weapon.ammo, "reserve": weapon.reserve_ammo, "capacity": weapon.capacity,
		"kills": kills, "time_left": time_left, "objective": "物資を回収し、北東の退避門へ",
		"heading_degrees": fposmod(-rad_to_deg(player.rotation.y), 360.0),
		"extraction_distance": player.global_position.distance_to(world.get_extraction_position()),
		"interaction_prompt": _interaction_target.get_prompt() if is_instance_valid(_interaction_target) else "",
		"extract_progress": extraction_elapsed / extraction_duration,
		"healing_progress": 1.0 - heal_remaining / heal_duration if heal_remaining > 0.0 else 0.0,
		"activity_label": activity, "activity_progress": progress,
		"threat": "銃声は周囲の敵を引き寄せます" if _noise_remaining > 0.0 else "",
		"message": _message, "saved_ok": inventory.saved_ok,
		"credits": int(inventory.profile.get("credits", 0)), "stash_rows": inventory.get_stash_rows(),
		"carried_rows": inventory.get_carried_rows(), "used_slots": inventory.get_used_slots(), "bag_capacity": inventory.get_capacity(),
		"can_deploy": inventory.can_deploy(), "can_recover": inventory.can_claim_recovery_kit(), "supply_prices": prices,
		"result_message": result_message, "extracted_value": extracted_value, "result_rows": result_rows,
		"is_aiming": weapon.is_aiming, "is_inspecting": weapon.is_inspecting, "reloading": weapon.reloading,
		"recoil": weapon.recoil_amount, "damage_flash": damage_flash, "hit_flash": hit_flash,
	}
