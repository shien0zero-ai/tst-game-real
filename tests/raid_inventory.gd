extends SceneTree
## Check durable loadouts, bounded loot, extraction, death, and resupply.

const SAVE_PATH := "user://ashgate_inventory_test_v1.json"
const INVENTORY_PATH := "res://scripts/raid_inventory.gd"

var _failures: PackedStringArray = []
var _saved_files: Dictionary = {}


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	for suffix: String in ["", ".bak", ".tmp"]:
		if FileAccess.file_exists(SAVE_PATH + suffix):
			_saved_files[suffix] = FileAccess.get_file_as_bytes(SAVE_PATH + suffix)
	_test_durable_departure()
	_test_bag_capacity()
	_test_extraction_and_trading()
	_test_death_and_recovery()
	_test_save_failure_rollback()
	_test_backup_recovery()
	_restore_save()
	if _failures.is_empty():
		print("PASS: durable loadouts, stack capacity, extraction persistence, death loss, trading, and recovery-kit guards.")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _new_inventory(fresh: bool = true) -> RefCounted:
	if fresh:
		_remove_test_files()
	var source: Script = load(INVENTORY_PATH) as Script
	if source == null:
		_failures.append("The raid inventory script loads.")
		return null
	var inventory: RefCounted = source.new() as RefCounted
	inventory.set("save_path", SAVE_PATH)
	_expect(bool(inventory.call("load_profile")), "A profile can be loaded from the isolated save path.")
	return inventory


func _test_durable_departure() -> void:
	var inventory: RefCounted = _new_inventory()
	if inventory == null:
		return
	var before: Dictionary = _stash(inventory).duplicate(true)
	var result: Dictionary = inventory.call("begin_raid")
	_expect(bool(result.get("ok", false)), "A starter profile can deploy.")
	var rounds: int = int(result.get("loaded_ammo", 0)) + int(result.get("reserve_ammo", 0))
	_expect(rounds > 0 and int(result.get("loaded_ammo", 0)) <= 7, "The loadout supplies a bounded real magazine and reserve.")
	_expect(int(_stash(inventory).get("m1911", 0)) == int(before.get("m1911", 0)) - 1, "Departure removes one equipped pistol from the stash.")
	_expect(int(_stash(inventory).get("ammo45", 0)) == int(before.get("ammo45", 0)) - rounds, "Departure removes exactly the loaded and reserve rounds.")
	_expect(int(_stash(inventory).get("medkit", 0)) == int(before.get("medkit", 0)) - 1 and int(inventory.call("get_count", "medkit")) == 1, "The medical item moves from the stash into the raid bag.")
	var saved: Variant = JSON.parse_string(FileAccess.get_file_as_string(SAVE_PATH))
	_expect(saved is Dictionary, "Departure writes a durable profile before gameplay starts.")
	var after_departure: Dictionary = _stash(inventory).duplicate(true)
	# A new instance models closing the game during a raid, rather than extraction.
	var resumed: RefCounted = _new_inventory(false)
	if resumed == null:
		return
	_expect(_stash(resumed) == after_departure, "Restarting during a raid cannot return the consumed loadout.")
	_expect((resumed.get("carried") as Dictionary).is_empty(), "An interrupted raid cannot recover unsaved bag contents.")
	_expect(not bool(resumed.get("raid_active")), "An interrupted raid does not silently resume with fresh equipment.")


func _test_bag_capacity() -> void:
	var inventory: RefCounted = _new_inventory()
	if inventory == null:
		return
	var start: Dictionary = inventory.call("begin_raid")
	_expect(bool(start.get("ok", false)), "The capacity test starts with a real loadout.")
	var capacity: int = int(inventory.call("get_capacity"))
	var used: int = int(inventory.call("get_used_slots"))
	var tools_to_fill: int = (capacity - used) * 2
	_expect(capacity > 0 and tools_to_fill > 0, "The bag has a finite usable capacity.")
	_expect(bool(inventory.call("add_loot", "tools", tools_to_fill)), "Whole stacks fit up to the bag's advertised capacity.")
	_expect(int(inventory.call("get_used_slots")) == capacity, "The filled bag reports its actual occupied slots.")
	var bag_before: Dictionary = (inventory.get("carried") as Dictionary).duplicate(true)
	_expect(not bool(inventory.call("add_loot", "electronics", 1)), "An additional stack is rejected when the bag is full.")
	_expect(inventory.get("carried") == bag_before, "A rejected pickup does not overwrite or consume carried loot.")
	_expect(not bool(inventory.call("add_loot", "unknown_item", 1)), "Unknown loot cannot enter the bag.")
	_expect(not bool(inventory.call("add_loot", "parts", -1)), "Negative loot amounts cannot manufacture capacity or items.")
	_expect(not bool(inventory.call("add_loot", "ammo45", 21)), "The bag cannot create a second, separately counted ammunition reserve.")
	_expect(bool(inventory.call("remove_item", "tools", tools_to_fill)), "Dropping loot frees its actual stacks.")
	_expect(int(inventory.call("get_used_slots")) == used, "Freed slots return to the original count.")
	_expect(bool(inventory.call("add_loot", "electronics", 1)), "A valid pickup works after freeing space.")
	_expect(not bool(inventory.call("remove_item", "electronics", 2)), "Removing more items than carried is rejected.")
	_expect(int(inventory.call("get_count", "electronics")) == 1, "Rejected removal leaves the existing item intact.")


func _test_extraction_and_trading() -> void:
	var inventory: RefCounted = _new_inventory()
	if inventory == null:
		return
	var start: Dictionary = inventory.call("begin_raid")
	_expect(bool(start.get("ok", false)), "The extraction test starts with a real loadout.")
	var after_departure: Dictionary = _stash(inventory).duplicate(true)
	_expect(bool(inventory.call("add_loot", "electronics", 2)), "Valuable recovered items can be carried.")
	_expect(bool(inventory.call("add_loot", "food", 3)), "Supplies can be carried with valuables.")
	_expect(bool(inventory.call("add_loot", "m1911", 1)), "A recovered weapon fits in the bag independently of the equipped pistol.")
	var result: Dictionary = inventory.call("finish_extraction", 3, 14)
	_expect(bool(result.get("ok", false)), "Extraction deposits the actual remaining loadout and loot.")
	_expect(int(_stash(inventory).get("m1911", 0)) == int(after_departure.get("m1911", 0)) + 2, "Extraction returns one equipped pistol plus the recovered pistol.")
	_expect(int(_stash(inventory).get("ammo45", 0)) == int(after_departure.get("ammo45", 0)) + 17, "Extraction returns exactly the remaining magazine and reserve rounds.")
	_expect(int(_stash(inventory).get("electronics", 0)) == 2 and int(_stash(inventory).get("food", 0)) == 3, "Recovered supplies persist in the stash without automatic sale.")
	_expect((inventory.get("carried") as Dictionary).is_empty() and not bool(inventory.get("raid_active")), "A completed extraction empties the raid bag and closes the active raid.")
	var completed_profile: Dictionary = (inventory.get("profile") as Dictionary).duplicate(true)
	var duplicate: Dictionary = inventory.call("finish_extraction", 7, 999)
	_expect(not bool(duplicate.get("ok", false)) and inventory.get("profile") == completed_profile, "Finishing the same raid again cannot duplicate weapons, ammo, loot, or money.")
	var resumed: RefCounted = _new_inventory(false)
	if resumed == null:
		return
	_expect(resumed.get("profile") == completed_profile, "A new inventory instance restores the extracted stash exactly.")
	var equipment_before: Dictionary = _stash(resumed).duplicate(true)
	var credits_before: int = _credits(resumed)
	var sold: Dictionary = resumed.call("sell_valuables")
	_expect(bool(sold.get("ok", false)) and int(sold.get("gained", 0)) > 0, "Recovered valuables can be sold for credits.")
	_expect(_credits(resumed) == credits_before + int(sold.get("gained", 0)), "The sale credits exactly its reported value.")
	for item: String in ["m1911", "ammo45", "medkit"]:
		_expect(int(_stash(resumed).get(item, 0)) == int(equipment_before.get(item, 0)), "Selling valuables preserves equipment: " + item)
	_expect(int(_stash(resumed).get("electronics", 0)) == 0 and int(_stash(resumed).get("food", 0)) == 0, "Sold valuables leave the stash.")
	var credits_after_sale: int = _credits(resumed)
	resumed.call("sell_valuables")
	_expect(_credits(resumed) == credits_after_sale, "Selling an empty valuables stash cannot pay twice.")
	var ammo_before: int = int(_stash(resumed).get("ammo45", 0))
	var credits_before_buy: int = _credits(resumed)
	var purchase: Dictionary = resumed.call("buy", "ammo45")
	_expect(bool(purchase.get("ok", false)), "Credits can buy the advertised ammunition pack.")
	_expect(int(_stash(resumed).get("ammo45", 0)) == ammo_before + 21 and _credits(resumed) == credits_before_buy - 250, "An ammunition purchase spends its price and delivers exactly one pack.")


func _test_death_and_recovery() -> void:
	var inventory: RefCounted = _new_inventory()
	if inventory == null:
		return
	var start: Dictionary = inventory.call("begin_raid")
	_expect(bool(start.get("ok", false)), "The death test starts with a consumed loadout.")
	var after_departure: Dictionary = _stash(inventory).duplicate(true)
	var deaths_before: int = int((inventory.get("profile") as Dictionary).get("deaths", 0))
	inventory.call("add_loot", "electronics", 2)
	inventory.call("finish_death")
	_expect(_stash(inventory) == after_departure, "Death does not return the equipped weapon, ammunition, or carried loot.")
	_expect((inventory.get("carried") as Dictionary).is_empty(), "Death discards the raid bag.")
	_expect(int((inventory.get("profile") as Dictionary).get("deaths", 0)) == deaths_before + 1, "Death is recorded once.")
	inventory.call("finish_death")
	_expect(int((inventory.get("profile") as Dictionary).get("deaths", 0)) == deaths_before + 1, "Repeated death notifications cannot count or charge another raid.")
	var resumed: RefCounted = _new_inventory(false)
	if resumed == null:
		return
	_expect(_stash(resumed) == after_departure, "Death losses remain after reloading the profile.")
	var profile: Dictionary = resumed.get("profile")
	profile["credits"] = 0
	profile["stash"] = {"m1911": 0, "ammo45": 0, "medkit": 0, "electronics": 0, "parts": 0, "food": 0, "tools": 0}
	resumed.set("profile", profile)
	_expect(bool(resumed.call("save_profile")), "A depleted test profile can be saved.")
	var denied: Dictionary = resumed.call("buy", "m1911")
	_expect(not bool(denied.get("ok", false)), "An unaffordable purchase cannot grant a free weapon.")
	_expect(bool(resumed.call("can_claim_recovery_kit")), "A depleted player can obtain basic equipment instead of being permanently locked out.")
	_expect(bool(resumed.call("claim_recovery_kit")), "The recovery kit restores a usable basic loadout.")
	_expect(bool(resumed.call("can_deploy")), "Recovered basic equipment permits another raid.")
	var recovery_stash: Dictionary = _stash(resumed).duplicate(true)
	_expect(not bool(resumed.call("claim_recovery_kit")) and _stash(resumed) == recovery_stash, "Recovery supplies cannot be repeatedly farmed while a usable loadout exists.")


func _stash(inventory: RefCounted) -> Dictionary:
	return (inventory.get("profile") as Dictionary).get("stash", {})


func _credits(inventory: RefCounted) -> int:
	return int((inventory.get("profile") as Dictionary).get("credits", 0))


func _test_save_failure_rollback() -> void:
	var inventory: RefCounted = _new_inventory()
	if inventory == null:
		return
	# A directory cannot be atomically replaced by a profile file. This models
	# an unwritable save without depending on the host user's Unix permissions.
	var blocked_path: String = SAVE_PATH + ".blocked"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(blocked_path))
	var before: Dictionary = (inventory.get("profile") as Dictionary).duplicate(true)
	inventory.set("save_path", blocked_path)
	var denied: Dictionary = inventory.call("begin_raid")
	_expect(not bool(denied.get("ok", false)), "A failed durable save prevents deployment.")
	_expect(inventory.get("profile") == before and not bool(inventory.get("raid_active")), "Failed deployment restores the exact previous stash and raid counters.")
	inventory.set("save_path", SAVE_PATH)
	var started: Dictionary = inventory.call("begin_raid")
	_expect(bool(started.get("ok", false)), "Deployment works after the storage failure is resolved.")
	inventory.call("add_loot", "electronics", 2)
	before = (inventory.get("profile") as Dictionary).duplicate(true)
	var carried: Dictionary = (inventory.get("carried") as Dictionary).duplicate(true)
	inventory.set("save_path", blocked_path)
	denied = inventory.call("finish_extraction", 3, 9)
	_expect(not bool(denied.get("ok", false)), "A failed extraction save does not claim a successful return.")
	_expect(inventory.get("profile") == before and inventory.get("carried") == carried and bool(inventory.get("raid_active")), "Failed extraction retains the active loadout and loot for a safe retry.")
	inventory.set("save_path", SAVE_PATH)
	var extracted: Dictionary = inventory.call("finish_extraction", 3, 9)
	_expect(bool(extracted.get("ok", false)) and int(_stash(inventory).get("electronics", 0)) == 2, "Retrying extraction deposits the recovered loot exactly once.")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(blocked_path + ".tmp"))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(blocked_path))


func _test_backup_recovery() -> void:
	var inventory: RefCounted = _new_inventory()
	if inventory == null:
		return
	var old_profile: Dictionary = (inventory.get("profile") as Dictionary).duplicate(true)
	inventory.call("buy", "ammo45")
	# The valid previous generation remains usable when the primary disappears.
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH))
	var recovered: RefCounted = _new_inventory(false)
	if recovered == null:
		return
	_expect(recovered.get("profile") == old_profile, "A missing primary profile recovers its valid previous generation.")
	_expect(FileAccess.file_exists(SAVE_PATH), "Recovered backup data is written back as a valid primary profile.")
	var resumed: RefCounted = _new_inventory(false)
	_expect(resumed != null and resumed.get("profile") == recovered.get("profile"), "The recovered profile survives a second launch without another reset.")


func _remove_test_files() -> void:
	for suffix: String in ["", ".bak", ".tmp"]:
		if FileAccess.file_exists(SAVE_PATH + suffix):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH + suffix))


func _restore_save() -> void:
	_remove_test_files()
	for suffix: String in _saved_files:
		var file: FileAccess = FileAccess.open(SAVE_PATH + suffix, FileAccess.WRITE)
		if file == null:
			_failures.append("The previous isolated test profile can be restored: " + suffix)
		else:
			file.store_buffer(_saved_files[suffix])
			file.close()


func _expect(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
