extends CanvasLayer

@onready var crosshair: Label = $Crosshair
@onready var mouse_hint: Label = $MouseHint


func _process(_delta: float) -> void:
	var captured: bool = Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
	crosshair.visible = captured
	mouse_hint.visible = not captured and DisplayServer.get_name() != "headless"
