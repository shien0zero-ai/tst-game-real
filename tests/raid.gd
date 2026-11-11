extends SceneTree
## Exercise the playable raid loop against the real map, actors, weapon and UI.

const SAVE_PATH := "user://ashgate_raid_test_v1.json"
const INVENTORY_PATH := "res://scripts/raid_inventory.gd"

var _failures: PackedStringArray = []
var _saved_files: Dictionary = {}
var _main: Node
var _player: CharacterBody3D
var _camera: Camera3D
var _weapon: Node3D
var _inventory: RefCounted
var _world: Node3D
var _stash_after_departure: Dictionary


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	for suffix: String in ["", ".bak", ".tmp"]:
		if FileAccess.file_exists(SAVE_PATH + suffix):
			_saved_files[suffix] = FileAccess.get_file_as_bytes(SAVE_PATH + suffix)
			DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH + suffix))
	var packed := load("res://scenes/raid_main.tscn") as PackedScene
	if packed == null:
		_failures.append("The PvE raid scene loads.")
		await _finish()
		return
	_main = packed.instantiate()
	_main.set("profile_path", SAVE_PATH)
	_main.set("extraction_duration", 0.6)
	root.add_child(_main)
	current_scene = _main
	_player = _main.get_node("Player") as CharacterBody3D
	_camera = _player.get_node("Head/Camera3D") as Camera3D
	_weapon = _camera.get_node("WeaponRig") as Node3D
	_world = _main.get_node("World") as Node3D
	_inventory = _main.get("inventory") as RefCounted
	await _frames(8)
	_expect(_phase() == "base", "The game opens at the persistent base instead of consuming a loadout immediately.")
	_expect(not bool(_player.get("controls_enabled")) and not bool(_weapon.get("controls_enabled")), "The base UI cannot move the player or discharge the weapon.")
	_expect(_inventory != null and bool(_inventory.call("can_deploy")), "The first launch includes a usable starter loadout.")
	for binding: Array in [["interact", KEY_E], ["inventory", KEY_TAB], ["heal", KEY_4]]:
		_expect(_physical_binding(String(binding[0]), int(binding[1])), "The raid control has a physical keyboard binding: " + String(binding[0]))
	_main.call("start_raid")
	await _frames(8)
	_freeze_enemies()
	_expect(_phase() == "raid", "Deploying starts the actual raid.")
	_expect(_main.get_node("Enemies").get_child_count() >= 4, "The map contains several live PvE guards.")
	_expect(_main.get_node("Loot").get_child_count() >= 6, "The map contains searchable supplies.")
	_expect(bool(_player.get("health_enabled")) and not bool(_weapon.get("unlimited_ammo")), "Raids enable player damage and consume finite ammunition.")
	_stash_after_departure = _stash().duplicate(true)
	_test_map_routes()
	await _test_weapon_and_inventory()
	await _test_medical_actions()
	await _test_searching()
	await _test_enemy_and_cover()
	await _test_extraction()
	await _test_death_loss()
	await _finish()


func _test_weapon_and_inventory() -> void:
	var reserve_before: int = int(_weapon.get("reserve_ammo"))
	_send_action("shoot", true)
	await _frames(30)
	_expect(int(_weapon.get("ammo")) == 6 and int(_weapon.get("reserve_ammo")) == reserve_before, "Holding the real trigger fires exactly once and consumes one loaded round.")
	_send_action("shoot", false)
	await _frames(3)
	_weapon.set("ammo", 1)
	_weapon.set("reserve_ammo", 2)
	await _tap("reload")
	_expect(bool(_weapon.get("reloading")) and int(_weapon.get("ammo")) == 1, "A finite-ammo reload takes time before transferring rounds.")
	await _frames(ceili(float(_weapon.get("reload_duration")) * 60.0) + 4)
	_expect(int(_weapon.get("ammo")) == 3 and int(_weapon.get("reserve_ammo")) == 0, "Reload transfers only the two available reserve rounds.")
	await _tap("reload")
	_expect(not bool(_weapon.get("reloading")) and int(_weapon.get("ammo")) == 3, "An empty reserve cannot manufacture ammunition through reload.")
	_weapon.set("ammo", 7)
	_weapon.set("reserve_ammo", reserve_before)
	await _tap("inventory")
	_expect(bool(_main.get("inventory_open")) and not paused, "Tab opens the bag while the raid continues in real time.")
	_expect(not bool(_player.get("controls_enabled")) and not bool(_weapon.get("controls_enabled")), "Bag interactions disable movement and weapon input.")
	var before: float = float(_snapshot().get("time_left", 0.0))
	await _tap("shoot")
	await _frames(20)
	_expect(int(_weapon.get("ammo")) == 7, "Clicking in the bag cannot accidentally fire the pistol.")
	_expect(float(_snapshot().get("time_left", 0.0)) < before, "Opening the bag does not stop the raid timer.")
	await _tap("ui_cancel")
	_expect(not bool(_main.get("inventory_open")) and not paused, "Esc closes the bag without opening the pause menu in the same press.")
	await _tap("ui_cancel")
	_expect(paused, "Esc from normal raid control opens settings and pauses the solo game.")
	before = float(_snapshot().get("time_left", 0.0))
	await _frames(12)
	_expect(is_equal_approx(float(_snapshot().get("time_left", 0.0)), before), "The raid timer remains stopped while settings are open.")
	await _tap("ui_cancel")
	_expect(not paused and bool(_weapon.get("controls_enabled")), "Closing settings restores normal weapon control.")


func _test_medical_actions() -> void:
	_player.call("receive_damage", 50.0, Vector3.ZERO)
	await _frames(8)
	_expect(float(_player.get("health")) < 51.0 and bool(_player.get("bleeding")), "A serious wound reduces health and starts bleeding.")
	var kits: int = int(_inventory.call("get_count", "medkit"))
	await _tap("heal")
	_expect(float(_main.get("heal_remaining")) > 0.0 and not bool(_weapon.get("controls_enabled")), "The medical key starts a timed action and blocks firing.")
	await _frames(16)
	_expect(int(_inventory.call("get_count", "medkit")) == kits, "A medical item is not spent before treatment completes.")
	_player.call("receive_damage", 5.0, Vector3.ZERO)
	await _frames(2)
	_expect(float(_main.get("heal_remaining")) <= 0.0 and int(_inventory.call("get_count", "medkit")) == kits, "Incoming damage interrupts treatment without consuming the kit.")
	await _frames(8)
	var wounded_health: float = float(_player.get("health"))
	await _tap("heal")
	await _frames(ceili(float(_main.get("heal_duration")) * 60.0) + 5)
	_expect(float(_player.get("health")) > wounded_health + 35.0 and not bool(_player.get("bleeding")), "Completing treatment restores health and stops bleeding.")
	_expect(int(_inventory.call("get_count", "medkit")) == kits - 1 and bool(_weapon.get("controls_enabled")), "Completed treatment spends exactly one kit and returns weapon control.")


func _test_searching() -> void:
	var loot: Node3D = _main.get_node("Loot").get_child(0) as Node3D
	loot.set("contents", {"ammo45": 14, "electronics": 2})
	loot.global_position = _player.global_position + Vector3(0, 0, -1.7)
	_player.get_node("Head").look_at(loot.global_position + Vector3(0, 0.4, 0), Vector3.UP)
	await _frames(3)
	var reserve: int = int(_weapon.get("reserve_ammo"))
	await _tap("interact")
	_expect(float(_main.get("search_remaining")) > 0.0, "E starts a timed search of the actual case under the camera.")
	_expect(int(_inventory.call("get_count", "electronics")) == 0, "Searching does not grant loot before its duration finishes.")
	await _frames(ceili(float(_main.get("search_duration")) * 60.0) + 5)
	_expect(int(_inventory.call("get_count", "electronics")) == 2, "A completed search transfers recovered valuables into the finite bag.")
	_expect(int(_weapon.get("reserve_ammo")) == reserve + 14 and int(_inventory.call("get_count", "ammo45")) == 0, "Loose ammunition enters the real reserve instead of a duplicate bag ammo pool.")
	var before: Dictionary = (_inventory.get("carried") as Dictionary).duplicate(true)
	await _tap("interact")
	await _frames(ceili(float(_main.get("search_duration")) * 60.0) + 5)
	_expect(_inventory.get("carried") == before and int(_weapon.get("reserve_ammo")) == reserve + 14, "Searching an emptied case cannot reroll or duplicate its contents.")
	# A full bag and a nearly full reserve must leave excess contents available
	# for another search instead of deleting or secretly carrying them.
	var free_slots: int = int(_inventory.call("get_capacity")) - int(_inventory.call("get_used_slots"))
	_expect(bool(_inventory.call("add_loot", "tools", free_slots * 2)), "The search test can fill every remaining bag slot with complete stacks.")
	_weapon.set("reserve_ammo", 137)
	loot.set("contents", {"ammo45": 9, "parts": 3})
	await _tap("interact")
	await _frames(ceili(float(_main.get("search_duration")) * 60.0) + 5)
	var remaining: Dictionary = loot.get("contents")
	_expect(int(_weapon.get("reserve_ammo")) == 140 and int(remaining.get("ammo45", 0)) == 6, "The reserve limit leaves uncollected ammunition in its original case.")
	_expect(int(_inventory.call("get_count", "parts")) == 0 and int(remaining.get("parts", 0)) == 3, "Loot that cannot fit in the bag remains in the case.")
	_inventory.call("remove_item", "tools", free_slots * 2)
	await _tap("interact")
	await _frames(ceili(float(_main.get("search_duration")) * 60.0) + 5)
	remaining = loot.get("contents")
	_expect(int(_inventory.call("get_count", "parts")) == 3 and int(remaining.get("parts", 0)) == 0 and int(remaining.get("ammo45", 0)) == 6, "Freeing bag space permits recovering the remaining items without duplicating capped ammunition.")
	_weapon.set("reserve_ammo", reserve + 14)
	_player.get_node("Head").rotation = Vector3.ZERO


func _test_map_routes() -> void:
	var spawn: Vector3 = (_world.call("get_spawn_transform") as Transform3D).origin
	var destinations: Array[Dictionary] = _world.call("get_loot_spawns")
	destinations.append({"position": _world.call("get_extraction_position"), "label": "Extraction"})
	for entry: Dictionary in destinations:
		var target: Vector3 = entry["position"]
		var path: PackedVector3Array = _main.call("get_navigation_path", spawn, target)
		var label: String = str(entry.get("label", "Loot"))
		_expect(not path.is_empty(), "A navigable route exists from deployment to " + label)
		if path.is_empty():
			continue
		_expect(Vector2(path[-1].x - target.x, path[-1].z - target.z).length() < 0.1, "The route reaches its actual destination: " + label)
		var previous: Vector3 = spawn
		for point: Vector3 in path:
			_expect(bool(_world.call("_line_walkable", previous, point)), "Navigation does not cut through a thin wall on the way to " + label)
			previous = point


func _test_enemy_and_cover() -> void:
	var enemy: CharacterBody3D = _main.get_node("Enemies").get_child(0) as CharacterBody3D
	var player_position: Vector3 = _player.global_position
	var player_health: float = float(_player.get("health"))
	# Isolate the combat ray above the buildings, retaining the real actors and
	# physics world. Patrol physics is frozen so this does not depend on a route.
	_player.set_physics_process(false)
	_player.global_position = Vector3(0, 20, 35)
	_player.get_node("Head").rotation = Vector3.ZERO
	_camera.rotation = Vector3.ZERO
	enemy.global_position = Vector3(0, 20, 27)
	enemy.rotation.y = PI
	enemy.set("_player", _player)
	await _frames(3)
	_expect(bool(enemy.call("_can_see_player")), "A guard can see the player across an unobstructed firing lane.")
	var blocker := StaticBody3D.new()
	blocker.collision_layer = 1
	blocker.collision_mask = 0
	blocker.position = Vector3(0, 21, 31)
	var shape := BoxShape3D.new()
	shape.size = Vector3(3, 3, 0.5)
	var collision := CollisionShape3D.new()
	collision.shape = shape
	blocker.add_child(collision)
	_main.add_child(blocker)
	await _frames(3)
	_expect(not bool(enemy.call("_can_see_player")), "A solid wall prevents guard detection through cover.")
	for _attempt: int in 8:
		enemy.call("_attempt_shot")
	_expect(is_equal_approx(float(_player.get("health")), player_health), "A guard's attack cannot damage the player through a solid wall.")
	enemy.call("hear_noise", _player.global_position, 30.0)
	_expect(String(enemy.get("state")) == "investigate", "A gunshot or nearby sound can make an occluded guard investigate.")
	blocker.queue_free()
	await _frames(3)
	for _attempt: int in 20:
		enemy.call("_attempt_shot")
	_expect(float(_player.get("health")) < player_health, "An unobstructed guard attack can damage the real player.")
	var kills: int = int(_snapshot().get("kills", 0))
	var cases: int = _main.get_node("Loot").get_child_count()
	enemy.call("register_hit", enemy.global_position + Vector3(0, 1.6, 0), Vector3.BACK)
	await _frames(3)
	_expect(bool(enemy.get("is_dead")) and int(_snapshot().get("kills", 0)) == kills + 1, "A lethal hit records one PvE kill.")
	_expect(_main.get_node("Loot").get_child_count() == cases + 1, "A defeated guard produces one searchable loot pouch.")
	enemy.call("register_hit", enemy.global_position + Vector3(0, 1.6, 0), Vector3.BACK)
	await _frames(2)
	_expect(int(_snapshot().get("kills", 0)) == kills + 1 and _main.get_node("Loot").get_child_count() == cases + 1, "Additional impacts cannot duplicate kill rewards or corpse loot.")
	_player.global_position = player_position
	_player.velocity = Vector3.ZERO
	_player.set("health", player_health)
	_player.set("bleeding", false)
	_player.set_physics_process(true)
	await _frames(8)


func _test_extraction() -> void:
	var extraction: Vector3 = _world.call("get_extraction_position")
	var loaded: int = int(_weapon.get("ammo"))
	var reserve: int = int(_weapon.get("reserve_ammo"))
	_player.global_position = extraction + Vector3(0, 0.1, -4.2)
	_player.velocity = Vector3.ZERO
	await _frames(12)
	_expect(_phase() == "raid" and float(_main.get("extraction_elapsed")) > 0.0, "Standing below the visible gate starts the countdown, including the far end of the marked bay.")
	_player.global_position += Vector3(-6, 0, 0)
	_player.velocity = Vector3.ZERO
	await _frames(3)
	_expect(_phase() == "raid" and is_zero_approx(float(_main.get("extraction_elapsed"))), "Leaving the extraction zone resets its countdown.")
	_player.global_position = extraction + Vector3(0, 0.1, 0)
	_player.velocity = Vector3.ZERO
	await _frames(45)
	_expect(_phase() == "extracted", "Remaining at the gate for the full countdown completes extraction.")
	_expect(int(_stash().get("m1911", 0)) == int(_stash_after_departure.get("m1911", 0)) + 1, "Extraction returns the equipped M1911 to the persistent stash.")
	_expect(int(_stash().get("ammo45", 0)) == int(_stash_after_departure.get("ammo45", 0)) + loaded + reserve, "Extraction saves exactly the ammunition left in the weapon and reserve.")
	_expect(int(_stash().get("electronics", 0)) == 2 and not bool(_inventory.get("raid_active")), "Recovered valuables reach the stash and close the durable active raid.")
	var saved: Dictionary = (_inventory.get("profile") as Dictionary).duplicate(true)
	_main.call("finish_extraction")
	_expect(_inventory.get("profile") == saved, "Repeated extraction notifications cannot duplicate a completed run.")
	var source := load(INVENTORY_PATH) as Script
	var resumed: RefCounted = source.new() as RefCounted
	resumed.set("save_path", SAVE_PATH)
	_expect(bool(resumed.call("load_profile")) and resumed.get("profile") == saved, "The extracted stash is restored exactly by a fresh profile instance.")


func _test_death_loss() -> void:
	_main.call("return_to_base")
	_expect(_phase() == "base", "The result screen can return to the base.")
	_main.call("start_raid")
	await _frames(8)
	_freeze_enemies()
	_expect(_phase() == "raid", "Saved equipment permits another raid.")
	_inventory.call("add_loot", "tools", 2)
	var after_departure: Dictionary = _stash().duplicate(true)
	var deaths: int = int((_inventory.get("profile") as Dictionary).get("deaths", 0))
	_player.call("receive_damage", 1000.0, Vector3.ZERO)
	await _frames(3)
	_expect(_phase() == "dead" and not bool(_weapon.get("controls_enabled")), "Fatal damage ends the raid and disables weapon control.")
	_expect(_stash() == after_departure and (_inventory.get("carried") as Dictionary).is_empty(), "Death loses carried loot and equipped gear while preserving the base stash.")
	_expect(int((_inventory.get("profile") as Dictionary).get("deaths", 0)) == deaths + 1, "The failed raid is recorded once.")
	_player.emit_signal("died")
	await _frames(2)
	_expect(int((_inventory.get("profile") as Dictionary).get("deaths", 0)) == deaths + 1, "A repeated death signal cannot charge another loss.")
	var source := load(INVENTORY_PATH) as Script
	var resumed: RefCounted = source.new() as RefCounted
	resumed.set("save_path", SAVE_PATH)
	_expect(bool(resumed.call("load_profile")) and _stash() == (resumed.get("profile") as Dictionary).get("stash", {}), "Death losses remain after a fresh profile load.")


func _freeze_enemies() -> void:
	for enemy: Node in _main.get_node("Enemies").get_children():
		enemy.set_physics_process(false)


func _physical_binding(action: String, code: int) -> bool:
	if not InputMap.has_action(action):
		return false
	for event: InputEvent in InputMap.action_get_events(action):
		if event is InputEventKey and event.physical_keycode == code:
			return true
	return false


func _snapshot() -> Dictionary:
	return _main.call("get_ui_snapshot")


func _phase() -> String:
	return String(_main.get("phase"))


func _stash() -> Dictionary:
	return (_inventory.get("profile") as Dictionary).get("stash", {})


func _send_action(action: String, pressed: bool) -> void:
	var event := InputEventAction.new()
	event.action = action
	event.pressed = pressed
	Input.parse_input_event(event)


func _tap(action: String) -> void:
	_send_action(action, true)
	await _frames(2)
	_send_action(action, false)
	await _frames(2)


func _frames(count: int) -> void:
	for _frame: int in count:
		await physics_frame


func _finish() -> void:
	paused = false
	for action: String in ["shoot", "aim", "reload", "inventory", "interact", "heal", "ui_cancel"]:
		Input.action_release(action)
	if is_instance_valid(_main):
		_main.queue_free()
		await _frames(2)
	for suffix: String in ["", ".bak", ".tmp"]:
		if FileAccess.file_exists(SAVE_PATH + suffix):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH + suffix))
	for suffix: String in _saved_files:
		var file := FileAccess.open(SAVE_PATH + suffix, FileAccess.WRITE)
		if file == null:
			_failures.append("The previous isolated raid-test profile can be restored: " + suffix)
		else:
			file.store_buffer(_saved_files[suffix])
			file.close()
	if _failures.is_empty():
		print("PASS: live finite-ammo raid, bag/pause input, interrupted treatment, searched loot, guard cover/combat/death, extraction countdown, durable return, and death loss.")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _expect(condition: bool, message: String) -> void:
	if not condition:
		_failures.append(message)
