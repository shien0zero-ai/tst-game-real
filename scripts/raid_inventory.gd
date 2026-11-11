extends RefCounted
## Durable stash and a finite raid bag. The weapon owns loaded and reserve ammo.

const VERSION: int = 1
const DEFAULT_SAVE_PATH := "user://ashgate_profile_v1.json"
const BAG_CAPACITY: int = 12
const MAX_ITEM_COUNT: int = 1000000
const MAX_CREDITS: int = 1000000000
const EXTRACTION_BONUS: int = 300
const ITEM_CATALOG := {
	"m1911": {"name": "M1911", "value": 1500, "stack": 1, "valuable": false},
	"ammo45": {"name": ".45 ACP 弾薬", "value": 10, "stack": 21, "valuable": false},
	"medkit": {"name": "救急キット", "value": 350, "stack": 2, "valuable": false},
	"electronics": {"name": "電子部品", "value": 680, "stack": 3, "valuable": true},
	"parts": {"name": "機械部品", "value": 110, "stack": 8, "valuable": true},
	"food": {"name": "保存食", "value": 80, "stack": 4, "valuable": true},
	"tools": {"name": "工具セット", "value": 260, "stack": 2, "valuable": true},
}
const ITEMS = ITEM_CATALOG
const SHOP := {
	"m1911": {"price": 1800, "count": 1},
	"ammo45": {"price": 250, "count": 21},
	"medkit": {"price": 350, "count": 1},
}

var save_path: String = DEFAULT_SAVE_PATH
var profile: Dictionary = {}
var carried: Dictionary = {}
var raid_active: bool = false
var saved_ok: bool = true
var last_error: String = ""
var last_notice: String = ""
var _save_blocked: bool = false


func _init() -> void:
	profile = _starter_profile()


func load_profile() -> bool:
	carried.clear()
	raid_active = false
	_save_blocked = false
	saved_ok = true
	last_error = ""
	last_notice = ""
	var loaded: Dictionary = _read_profile(save_path)
	var needs_save: bool = loaded.is_empty()
	if loaded.is_empty():
		if FileAccess.file_exists(save_path):
			# Keep a damaged/unknown save before replacing it; a failed backup
			# blocks writes rather than destroying the player's only copy.
			var invalid_path := save_path.get_basename() + ".invalid-%d-%d.json" % [int(Time.get_unix_time_from_system()), Time.get_ticks_usec()]
			var backup_result: Error = DirAccess.copy_absolute(ProjectSettings.globalize_path(save_path), ProjectSettings.globalize_path(invalid_path))
			if backup_result != OK:
				profile = _starter_profile()
				_save_blocked = true
				return _save_failed("以前のセーブデータを保護できないため、保存を停止しました。")
			last_notice = "読み込めないセーブデータを退避しました。"
		loaded = _read_profile(save_path + ".bak")
		if not loaded.is_empty():
			last_notice = "保管庫をバックアップから復元しました。"
		else:
			loaded = _starter_profile()
	profile = loaded
	if bool(profile.get("raid_in_progress", false)):
		# Loadout consumption was already saved at deployment. A process quit
		# cannot return that gear or duplicate items by abandoning a raid.
		profile["raid_in_progress"] = false
		profile["deaths"] = mini(int(profile["deaths"]) + 1, MAX_ITEM_COUNT)
		last_notice = "前回の出撃は中断され、持ち込んだ装備を失いました。"
		needs_save = true
	return save_profile() if needs_save else true


func save_profile() -> bool:
	if _save_blocked:
		return _save_failed("以前のセーブデータを保護できないため、保存できません。")
	var payload: Dictionary = _validated_profile(profile)
	if payload.is_empty() or save_path.is_empty():
		return _save_failed("保管庫のデータを保存できません。")
	var absolute_path := ProjectSettings.globalize_path(save_path)
	var directory_result: Error = DirAccess.make_dir_recursive_absolute(absolute_path.get_base_dir())
	if directory_result != OK:
		return _save_failed("保存先のフォルダーを作成できません。")
	var temporary := save_path + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if file == null:
		return _save_failed("保管庫を書き込めません。")
	file.store_string(JSON.stringify(payload, "\t"))
	file.flush()
	var write_error: Error = file.get_error()
	file.close()
	if write_error != OK:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(temporary))
		return _save_failed("保管庫の書き込みに失敗しました。")
	# Only back up a valid previous generation. An invalid file is protected
	# separately by load_profile and must not replace a good .bak generation.
	if not _read_profile(save_path).is_empty():
		var backup_result: Error = DirAccess.copy_absolute(absolute_path, ProjectSettings.globalize_path(save_path + ".bak"))
		if backup_result != OK:
			DirAccess.remove_absolute(ProjectSettings.globalize_path(temporary))
			return _save_failed("保管庫のバックアップを保存できません。")
	var rename_result: Error = DirAccess.rename_absolute(ProjectSettings.globalize_path(temporary), absolute_path)
	if rename_result != OK:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(temporary))
		return _save_failed("保管庫の保存を完了できません。")
	profile = payload
	saved_ok = true
	last_error = ""
	return true


func can_deploy() -> bool:
	return not raid_active and _stash_count("m1911") >= 1 and _stash_count("ammo45") >= 7


func begin_raid() -> Dictionary:
	if raid_active:
		return _failure("すでに出撃中です。")
	if not can_deploy():
		return _failure("M1911と弾薬7発以上が必要です。")
	var previous: Dictionary = profile.duplicate(true)
	var stash: Dictionary = profile["stash"]
	var rounds: int = mini(35, _stash_count("ammo45"))
	var medkits: int = mini(1, _stash_count("medkit"))
	stash["m1911"] = _stash_count("m1911") - 1
	stash["ammo45"] = _stash_count("ammo45") - rounds
	stash["medkit"] = _stash_count("medkit") - medkits
	profile["raids_started"] = mini(int(profile["raids_started"]) + 1, MAX_ITEM_COUNT)
	profile["raid_in_progress"] = true
	if not save_profile():
		profile = previous
		return _failure("保存できないため出撃できません。 " + last_error)
	carried.clear()
	if medkits > 0:
		carried["medkit"] = medkits
	raid_active = true
	return {"ok": true, "error": "", "loaded_ammo": 7, "reserve_ammo": rounds - 7, "medkits": medkits}


func can_add(item_id: String, count: int = 1) -> bool:
	if not raid_active or not ITEM_CATALOG.has(item_id) or item_id == "ammo45" or count <= 0 or count > MAX_ITEM_COUNT:
		return false
	var proposed: Dictionary = carried.duplicate()
	if get_count(item_id) > MAX_ITEM_COUNT - count:
		return false
	proposed[item_id] = get_count(item_id) + count
	return _used_slots(proposed) <= BAG_CAPACITY


func add_loot(item_id: String, count: int = 1) -> bool:
	if not can_add(item_id, count):
		return false
	carried[item_id] = get_count(item_id) + count
	return true


func remove_item(item_id: String, count: int = 1) -> bool:
	if not raid_active or count <= 0 or get_count(item_id) < count:
		return false
	var remaining: int = get_count(item_id) - count
	if remaining == 0:
		carried.erase(item_id)
	else:
		carried[item_id] = remaining
	return true


func get_count(item_id: String) -> int:
	return _bounded_count(carried.get(item_id, 0), MAX_ITEM_COUNT)


func get_used_slots() -> int:
	return _used_slots(carried)


func get_capacity() -> int:
	return BAG_CAPACITY


func get_carried_rows() -> Array[Dictionary]:
	return _rows(carried, false)


func get_stash_rows() -> Array[Dictionary]:
	return _rows(profile.get("stash", {}), true)


func finish_extraction(loaded_ammo: int, reserve_ammo: int) -> Dictionary:
	if not raid_active:
		return _failure("出撃していません。")
	var previous: Dictionary = profile.duplicate(true)
	var recovered: Dictionary = carried.duplicate()
	var value: int = 0
	var stash: Dictionary = profile["stash"]
	stash["m1911"] = mini(_stash_count("m1911") + 1, MAX_ITEM_COUNT)
	stash["ammo45"] = mini(_stash_count("ammo45") + clampi(loaded_ammo, 0, 7) + clampi(reserve_ammo, 0, MAX_ITEM_COUNT), MAX_ITEM_COUNT)
	for item_id: String in ITEM_CATALOG:
		if item_id == "ammo45":
			continue
		var count: int = get_count(item_id)
		stash[item_id] = mini(_stash_count(item_id) + count, MAX_ITEM_COUNT)
		value += count * int(ITEM_CATALOG[item_id]["value"])
	profile["credits"] = mini(int(profile["credits"]) + EXTRACTION_BONUS, MAX_CREDITS)
	profile["extractions"] = mini(int(profile["extractions"]) + 1, MAX_ITEM_COUNT)
	profile["raid_in_progress"] = false
	if not save_profile():
		profile = previous
		return _failure("持ち帰りを保存できません。 " + last_error)
	carried.clear()
	raid_active = false
	return {"ok": true, "error": "", "items": recovered, "value": value, "bonus": EXTRACTION_BONUS, "credits": int(profile["credits"]), "extractions": int(profile["extractions"])}


func finish_death() -> void:
	if not raid_active:
		return
	carried.clear()
	raid_active = false
	profile["raid_in_progress"] = false
	profile["deaths"] = mini(int(profile["deaths"]) + 1, MAX_ITEM_COUNT)
	# A failed write still leaves the loadout consumed by begin_raid. The old
	# durable in-progress flag records this loss on the next successful load.
	save_profile()


func buy(item_id: String) -> Dictionary:
	if raid_active:
		return _failure("出撃中は購入できません。")
	if not SHOP.has(item_id):
		return _failure("この物資は購入できません。")
	var price: int = int(SHOP[item_id]["price"])
	var count: int = int(SHOP[item_id]["count"])
	if int(profile["credits"]) < price:
		return _failure("所持金が不足しています。")
	if _stash_count(item_id) > MAX_ITEM_COUNT - count:
		return _failure("保管数が上限に達しています。")
	var previous: Dictionary = profile.duplicate(true)
	profile["credits"] = int(profile["credits"]) - price
	profile["stash"][item_id] = _stash_count(item_id) + count
	if not save_profile():
		profile = previous
		return _failure("購入を保存できません。 " + last_error)
	return {"ok": true, "error": "", "item_id": item_id, "count": count, "spent": price}


func sell_valuables() -> Dictionary:
	if raid_active:
		return _failure("出撃中は売却できません。")
	var gained: int = 0
	for item_id: String in ITEM_CATALOG:
		if bool(ITEM_CATALOG[item_id]["valuable"]):
			gained += _stash_count(item_id) * int(ITEM_CATALOG[item_id]["value"])
	if gained == 0:
		return _failure("売却できる回収品がありません。")
	if gained > MAX_CREDITS - int(profile["credits"]):
		return _failure("所持金が上限に達しています。")
	var previous: Dictionary = profile.duplicate(true)
	for item_id: String in ITEM_CATALOG:
		if bool(ITEM_CATALOG[item_id]["valuable"]):
			profile["stash"][item_id] = 0
	profile["credits"] = int(profile["credits"]) + gained
	if not save_profile():
		profile = previous
		return _failure("売却を保存できません。 " + last_error)
	return {"ok": true, "error": "", "gained": gained, "credits": int(profile["credits"])}


func can_claim_recovery_kit() -> bool:
	return not raid_active and not can_deploy() and int(profile["credits"]) < _deployment_purchase_cost()


func claim_recovery_kit() -> bool:
	if not can_claim_recovery_kit():
		return false
	var previous: Dictionary = profile.duplicate(true)
	profile["stash"]["m1911"] = mini(_stash_count("m1911") + 1, MAX_ITEM_COUNT)
	profile["stash"]["ammo45"] = mini(_stash_count("ammo45") + 35, MAX_ITEM_COUNT)
	profile["stash"]["medkit"] = mini(_stash_count("medkit") + 1, MAX_ITEM_COUNT)
	profile["recovery_kits"] = mini(int(profile["recovery_kits"]) + 1, MAX_ITEM_COUNT)
	if not save_profile():
		profile = previous
		return false
	return true


func _deployment_purchase_cost() -> int:
	return (1800 if _stash_count("m1911") == 0 else 0) + (250 if _stash_count("ammo45") < 7 else 0)


func _stash_count(item_id: String) -> int:
	return _bounded_count(profile.get("stash", {}).get(item_id, 0), MAX_ITEM_COUNT)


func _used_slots(contents: Dictionary) -> int:
	var slots: int = 0
	for item_id: String in ITEM_CATALOG:
		if item_id != "ammo45":
			slots += ceili(float(_bounded_count(contents.get(item_id, 0), MAX_ITEM_COUNT)) / float(ITEM_CATALOG[item_id]["stack"]))
	return slots


func _rows(contents: Dictionary, include_empty_equipment: bool) -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	for item_id: String in ITEM_CATALOG:
		if not include_empty_equipment and item_id == "ammo45":
			continue
		var count: int = _bounded_count(contents.get(item_id, 0), MAX_ITEM_COUNT)
		if count == 0 and not (include_empty_equipment and SHOP.has(item_id)):
			continue
		var item: Dictionary = ITEM_CATALOG[item_id]
		rows.append({"id": item_id, "name": String(item["name"]), "count": count, "value": int(item["value"]), "unit_value": int(item["value"]), "total_value": count * int(item["value"]), "stack": int(item["stack"]), "slots": ceili(float(count) / float(item["stack"]))})
	return rows


func _starter_profile() -> Dictionary:
	var stash: Dictionary = {}
	for item_id: String in ITEM_CATALOG:
		stash[item_id] = 0
	stash.merge({"m1911": 2, "ammo45": 84, "medkit": 4}, true)
	return {"version": VERSION, "credits": 1800, "stash": stash, "extractions": 0, "deaths": 0, "raids_started": 0, "raid_in_progress": false, "recovery_kits": 0}


func _read_profile(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parser := JSON.new()
	if parser.parse(FileAccess.get_file_as_string(path)) != OK:
		return {}
	return _validated_profile(parser.data)


func _validated_profile(value: Variant) -> Dictionary:
	if not value is Dictionary or not value.get("stash") is Dictionary:
		return {}
	if typeof(value.get("version")) not in [TYPE_INT, TYPE_FLOAT] or not is_finite(float(value["version"])) or float(value["version"]) != VERSION:
		return {}
	var stash: Dictionary = {}
	for item_id: String in ITEM_CATALOG:
		stash[item_id] = _bounded_count(value["stash"].get(item_id, 0), MAX_ITEM_COUNT)
	return {"version": VERSION, "credits": _bounded_count(value.get("credits", 0), MAX_CREDITS), "stash": stash, "extractions": _bounded_count(value.get("extractions", 0), MAX_ITEM_COUNT), "deaths": _bounded_count(value.get("deaths", 0), MAX_ITEM_COUNT), "raids_started": _bounded_count(value.get("raids_started", 0), MAX_ITEM_COUNT), "raid_in_progress": value.get("raid_in_progress", false) == true, "recovery_kits": _bounded_count(value.get("recovery_kits", 0), MAX_ITEM_COUNT)}


func _bounded_count(value: Variant, maximum: int) -> int:
	if typeof(value) not in [TYPE_INT, TYPE_FLOAT] or not is_finite(float(value)):
		return 0
	return int(clampf(float(value), 0.0, float(maximum)))


func _save_failed(message: String) -> bool:
	saved_ok = false
	last_error = message
	return false


func _failure(message: String) -> Dictionary:
	return {"ok": false, "error": message, "loaded_ammo": 0, "reserve_ammo": 0, "gained": 0}
