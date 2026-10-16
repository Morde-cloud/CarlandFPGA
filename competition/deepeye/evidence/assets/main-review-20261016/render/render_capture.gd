extends SceneTree
## Private B asset inspection fixture harness (evidence only; no product code).
## Work B-ASSETS-MAIN-RENDER-20261016-04, task DEEPEYE-IMPLEMENTATION-20261014/v1.
## Renders five asset inspection PNGs through the real Godot 4.7.2 renderer using the
## main-reviewed correction-03 asset sources copied byte-identically into this private project.
## Fixture label: B asset inspection fixture; not runtime/gameplay acceptance
## Inspection fixture only: no gameplay, runtime, collision, truth, performance/FPS
## or G01 acceptance is claimed.

const FIXTURE_LABEL := "B asset inspection fixture; not runtime/gameplay acceptance"
const VIEW_W := 1280
const VIEW_H := 720
const KIND_IDS := ["water", "hard_rock", "fault", "void", "casing"]
const OBSTACLES_PER_KIND := 6
const HEAD_PREFIXES := ["HeadPDC", "Blade", "CutterStud"]
const FLOOR_Y := -15.0
const PACK_X_LIMIT := 14.4
const PACK_Z_LIMIT := 14.4

var _report: Dictionary = {}
var _shots: Array = []
var _lib: GDScript
var _camera: Camera3D


func _initialize() -> void:
	print("RENDER_HARNESS_START fixture_label=", FIXTURE_LABEL)
	var vinfo: Dictionary = Engine.get_version_info()
	_report["fixture_label"] = FIXTURE_LABEL
	_report["task_id"] = "DEEPEYE-IMPLEMENTATION-20261014"
	_report["task_version"] = 1
	_report["work_id"] = "B-ASSETS-MAIN-RENDER-20261016-04"
	_report["engine_version_info"] = vinfo
	_report["engine_version_string"] = str(vinfo.get("string", ""))
	_report["cmdline_args"] = Array(OS.get_cmdline_args())
	_report["display_server"] = DisplayServer.get_name()
	_report["video_adapter_name"] = str(RenderingServer.get_video_adapter_name())
	_report["video_adapter_vendor"] = str(RenderingServer.get_video_adapter_vendor())
	_report["video_adapter_api_version"] = str(RenderingServer.get_video_adapter_api_version())
	_report["video_driver_info"] = str(OS.get_video_adapter_driver_info())
	_report["os_name"] = OS.get_name()
	_report["os_version"] = OS.get_version()
	_report["rendering_method_setting"] = str(ProjectSettings.get_setting("rendering/renderer/rendering_method"))
	if RenderingServer.has_method("get_current_rendering_method"):
		_report["active_rendering_method"] = str(RenderingServer.get_current_rendering_method())
	if RenderingServer.has_method("get_current_rendering_driver_name"):
		_report["active_rendering_driver"] = str(RenderingServer.get_current_rendering_driver_name())
	_report["project_dir"] = ProjectSettings.globalize_path("res://")
	_report["started_utc"] = Time.get_datetime_string_from_system(true, false)
	print("engine_version=", _report["engine_version_string"])
	print("video_adapter=", _report["video_adapter_name"], " vendor=", _report["video_adapter_vendor"], " api=", _report["video_adapter_api_version"])
	print("video_driver_info=", _report["video_driver_info"])
	print("active_rendering_method=", str(_report.get("active_rendering_method", "n/a")), " active_rendering_driver=", str(_report.get("active_rendering_driver", "n/a")))
	print("cmdline_args=", str(_report["cmdline_args"]))
	root.size = Vector2i(VIEW_W, VIEW_H)
	DisplayServer.window_set_position(Vector2i(-3200, 120))
	print("requested_window_position=(-3200,120) requested_window_size=(1280,720)")
	_main.call_deferred()


func _main() -> void:
	await process_frame
	await process_frame
	var wpos: Vector2i = DisplayServer.window_get_position()
	var wsize: Vector2i = DisplayServer.window_get_size()
	_report["window_position_actual"] = _v2i(wpos)
	_report["window_size_actual"] = _v2i(wsize)
	_report["viewport_size"] = _v2i(Vector2i(root.get_visible_rect().size))
	print("window_actual position=", str(wpos), " size=", str(wsize), " viewport=", str(root.get_visible_rect().size))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://png"))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://results"))
	_lib = load("res://world/asset_library.gd") as GDScript
	if _lib == null:
		_fail_main("asset_library_load_failed")
		return
	_setup_world_environment()
	_setup_overlay()
	_camera = Camera3D.new()
	_camera.name = "FixtureCamera"
	_camera.fov = 60.0
	_camera.near = 0.05
	_camera.far = 500.0
	root.add_child(_camera)
	_camera.current = true
	var camera_fill := DirectionalLight3D.new()
	camera_fill.name = "MainInspectionFill"
	camera_fill.light_energy = 0.8
	camera_fill.shadow_enabled = false
	_camera.add_child(camera_fill)
	var ok := true
	var reason := ""
	var r1: Dictionary = await _shot_01_drill_scale()
	if not bool(r1.get("ok", false)):
		ok = false
		reason = "shot_01:" + str(r1.get("error", "unknown"))
	if ok:
		var r2: Dictionary = await _shot_02_drill_head_detail()
		if not bool(r2.get("ok", false)):
			ok = false
			reason = "shot_02:" + str(r2.get("error", "unknown"))
	if ok:
		var r3: Dictionary = await _shot_03_obstacle_gallery()
		if not bool(r3.get("ok", false)):
			ok = false
			reason = "shot_03:" + str(r3.get("error", "unknown"))
	if ok:
		var r45: Dictionary = await _shot_04_05_world()
		if not bool(r45.get("ok", false)):
			ok = false
			reason = "shot_04_05:" + str(r45.get("error", "unknown"))
	_report["shots"] = _shots
	_report["status"] = "ok" if ok else ("failed:" + reason)
	_report["finished_utc"] = Time.get_datetime_string_from_system(true, false)
	_write_report()
	_write_measurements()
	print("RENDER_HARNESS_DONE status=", _report["status"], " shots=", _shots.size())
	quit(0 if ok else 3)


func _setup_world_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.07, 0.08, 0.10)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.62, 0.66, 0.74)
	env.ambient_light_energy = 1.15
	var we := WorldEnvironment.new()
	we.name = "FixtureWorldEnvironment"
	we.environment = env
	root.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "FixtureSun"
	sun.rotation_degrees = Vector3(-52.0, -38.0, 0.0)
	sun.light_energy = 1.25
	sun.shadow_enabled = false
	root.add_child(sun)


func _setup_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.name = "FixtureOverlay"
	root.add_child(layer)
	var top := ColorRect.new()
	top.name = "OrientationTopMagenta"
	top.color = Color(1.0, 0.0, 1.0)
	top.set_anchors_preset(Control.PRESET_TOP_WIDE)
	top.offset_bottom = 8.0
	layer.add_child(top)
	var bottom := ColorRect.new()
	bottom.name = "OrientationBottomCyan"
	bottom.color = Color(0.0, 1.0, 1.0)
	bottom.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	bottom.offset_top = -8.0
	layer.add_child(bottom)
	var label := Label.new()
	label.name = "FixtureLabel"
	label.text = FIXTURE_LABEL
	label.position = Vector2(16.0, 14.0)
	label.add_theme_font_size_override("font_size", 20)
	label.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
	label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0))
	label.add_theme_constant_override("outline_size", 6)
	layer.add_child(label)


func _shot_01_drill_scale() -> Dictionary:
	var drill: Node3D = _lib.create_drill()
	if drill == null:
		return {"ok": false, "error": "create_drill_null"}
	drill.name = "Drill_ActualScale_Oblique"
	root.add_child(drill)
	var box := _aabb_of(drill)
	var fit := _fit_camera(box, Vector3(1.0, 0.5, 0.8), 1.18)
	var measured: Dictionary = _lib.measure_visual(drill)
	var mesh_names: Array = []
	for node in _mesh_instances(drill):
		var mi := node as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		mesh_names.append(String(mi.name))
	var record: Dictionary = await _capture("01_drill_actual_scale_oblique")
	record["purpose"] = "entire drill at actual scale, side/oblique: collar, joint, body matrix, PDC head, 6 blades, 18 cutter studs"
	record["render_frame_sync"] = "await process_frame x4 + RenderingServer.frame_post_draw"
	record["objects"] = [{
		"asset_id": str(drill.get_meta(&"asset_id", "drill_pdc_v1")),
		"node": String(drill.name),
		"position_m": _v3(drill.position),
		"rotation_deg": _v3(drill.rotation_degrees),
	}]
	record["bounds_m"] = _aabb_dict(box)
	record["measured_visual"] = _measure_dict(measured)
	record["mesh_node_names"] = mesh_names
	record["mesh_instance_count"] = mesh_names.size()
	record["camera"] = fit
	record["ok"] = bool(record.get("save_png_ok", false))
	if not bool(record["ok"]):
		record["error"] = "save_png_failed:" + str(record.get("save_png_error", -1))
	_shots.append(record)
	var axis_names := ["plus_x", "minus_x", "plus_y", "minus_y", "plus_z", "minus_z"]
	var axis_directions := [Vector3.RIGHT, Vector3.LEFT, Vector3.UP, Vector3.DOWN, Vector3.BACK, Vector3.FORWARD]
	for axis_index in range(6):
		var direction: Vector3 = axis_directions[axis_index]
		var axis_fit := _fit_camera(box, direction, 1.18)
		var axis_record: Dictionary = await _capture("06_drill_axis_" + axis_names[axis_index])
		axis_record["purpose"] = "six-axis whole drill inspection, actual scale, no geometry/material changes"
		axis_record["camera"] = axis_fit
		axis_record["bounds_m"] = _aabb_dict(box)
		axis_record["ok"] = bool(axis_record.get("save_png_ok", false))
		_shots.append(axis_record)
		if not bool(axis_record["ok"]):
			drill.queue_free()
			return {"ok": false, "error": "six_axis_save_failed"}
	drill.queue_free()
	await process_frame
	return {"ok": bool(record["ok"]), "error": str(record.get("error", ""))}


func _shot_02_drill_head_detail() -> Dictionary:
	var drill: Node3D = _lib.create_drill()
	if drill == null:
		return {"ok": false, "error": "create_drill_null"}
	drill.name = "Drill_HeadDetail"
	root.add_child(drill)
	var detail_box := _aabb_of_named(drill, HEAD_PREFIXES)
	if detail_box.size == Vector3.ZERO:
		return {"ok": false, "error": "detail_bounds_empty"}
	var fill := DirectionalLight3D.new()
	fill.name = "HeadDetailFillLight"
	fill.light_energy = 1.6
	fill.shadow_enabled = false
	root.add_child(fill)
	fill.look_at_from_position(Vector3(0.55, 0.42, 1.55), Vector3(0.0, 0.0, 0.24), Vector3.UP)
	_camera.fov = 50.0
	var fit := _fit_camera(detail_box, Vector3(0.0, 0.0, 1.0), 1.02)
	_camera.fov = 60.0
	var blade_nodes: Array = []
	var stud_nodes: Array = []
	for node in _mesh_instances(drill):
		var mi := node as MeshInstance3D
		if mi == null:
			continue
		var n := String(mi.name)
		if n.begins_with("Blade"):
			blade_nodes.append(n)
		elif n.begins_with("CutterStud"):
			stud_nodes.append(n)
	blade_nodes.sort()
	stud_nodes.sort()
	var record: Dictionary = await _capture("02_drill_head_detail_6blades_18studs")
	record["purpose"] = "front/head close detail: axial view of the 6-blade/18-stud head; exact node counts recorded separately, occlusion is possible"
	record["render_frame_sync"] = "await process_frame x4 + RenderingServer.frame_post_draw"
	record["detail_bounds_m"] = _aabb_dict(detail_box)
	record["blade_nodes"] = blade_nodes
	record["stud_nodes"] = stud_nodes
	record["scene_lights"] = "one fixture sun plus one temporary fill light aimed at the head from the camera side (fixture scene only; asset mesh/material unchanged)"
	record["blade_count"] = blade_nodes.size()
	record["stud_count"] = stud_nodes.size()
	record["camera"] = fit
	record["ok"] = bool(record.get("save_png_ok", false))
	if not bool(record["ok"]):
		record["error"] = "save_png_failed:" + str(record.get("save_png_error", -1))
	_shots.append(record)
	fill.queue_free()
	drill.queue_free()
	await process_frame
	return {"ok": bool(record["ok"]), "error": str(record.get("error", ""))}


func _shot_03_obstacle_gallery() -> Dictionary:
	var gallery := Node3D.new()
	gallery.name = "ObstacleKindGallery"
	root.add_child(gallery)
	var objects: Array = []
	var x_cursor := 0.0
	for kind_v in KIND_IDS:
		var kind := str(kind_v)
		var obstacle: Node3D = _lib.create_obstacle(kind)
		if obstacle == null:
			return {"ok": false, "error": "create_obstacle_null_" + kind}
		var rotation_deg := Vector3.ZERO
		if kind == "casing":
			rotation_deg = Vector3(90.0, 0.0, 0.0)
		obstacle.rotation_degrees = rotation_deg
		var box := _aabb_relative(obstacle)
		var half_x := box.size.x * 0.5
		var half_y := box.size.y * 0.5
		obstacle.position = Vector3(x_cursor + half_x, half_y, 0.0)
		obstacle.name = "Gallery_" + kind
		gallery.add_child(obstacle)
		var label := Label3D.new()
		label.name = "KindLabel_" + kind
		label.text = kind
		label.font_size = 48
		label.pixel_size = 0.025
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.modulate = Color(1.0, 0.95, 0.7)
		label.position = Vector3(0.0, box.position.y + box.size.y + 1.0, 0.0)
		obstacle.add_child(label)
		objects.append({
			"kind": kind,
			"node": String(obstacle.name),
			"position_m": _v3(obstacle.position),
			"rotation_deg": _v3(rotation_deg),
			"local_bounds_m": _aabb_dict(box),
			"asset_id": str(obstacle.get_meta(&"asset_id", "")),
			"asset_contract_version": int(obstacle.get_meta(&"asset_contract_version", 0)),
			"source_license": str(obstacle.get_meta(&"source_license", "")),
			"pivot_bound_radius_m": float(obstacle.get_meta(&"pivot_bound_radius_m", 0.0)),
			"measured_vertex_count": int(obstacle.get_meta(&"measured_vertex_count", 0)),
			"geometry_bounds_m": _meta_bounds_dict(obstacle),
			"envelope_ok": bool(obstacle.get_meta(&"envelope_ok", false)),
			"label_node": String(label.name),
		})
		x_cursor += 2.0 * half_x + 1.2
	var gbox := _aabb_of(gallery)
	gallery.position = Vector3(-(gbox.position.x + gbox.size.x * 0.5), 0.0, -(gbox.position.z + gbox.size.z * 0.5))
	gbox = _aabb_of(gallery)
	var fit := _fit_camera(gbox, Vector3(0.18, 0.42, 1.0), 1.22)
	var record: Dictionary = await _capture("03_obstacle_kind_gallery_5kinds")
	record["purpose"] = "gallery of all five obstacle kinds with distinct Label3D labels and recorded placement transforms; source meshes and materials unchanged"
	record["render_frame_sync"] = "await process_frame x4 + RenderingServer.frame_post_draw"
	record["objects"] = objects
	record["gallery_bounds_m"] = _aabb_dict(gbox)
	record["camera"] = fit
	record["casing_display_note"] = "casing placed with a 90 deg X placement rotation so the 0.8 m x 8 m pipe stands vertically for inspection (placement transform only; mesh/material unchanged)"
	record["ok"] = bool(record.get("save_png_ok", false))
	if not bool(record["ok"]):
		record["error"] = "save_png_failed:" + str(record.get("save_png_error", -1))
	_shots.append(record)
	gallery.queue_free()
	await process_frame
	return {"ok": bool(record["ok"]), "error": str(record.get("error", ""))}


func _pack_world_layout() -> Dictionary:
	var specs: Array = []
	for kind_v in KIND_IDS:
		for j in OBSTACLES_PER_KIND:
			specs.append({"kind": str(kind_v), "index": j})
	specs.append({"kind": "drill", "index": 0})
	for gap_v in [1.2, 1.0, 0.8, 0.6, 0.45, 0.3, 0.2]:
		var attempt := _try_pack(specs, float(gap_v))
		if bool(attempt.get("ok", false)):
			return attempt
	var fallback := _try_pack(specs, 0.15)
	fallback["fallback_used"] = true
	return fallback


func _try_pack(specs: Array, gap: float) -> Dictionary:
	var items: Array = []
	for spec_v in specs:
		var spec: Dictionary = spec_v
		var kind := str(spec["kind"])
		var idx := int(spec["index"])
		var prototype: Node3D = null
		if kind == "drill":
			prototype = _lib.create_drill()
		else:
			prototype = _lib.create_obstacle(kind)
		if prototype == null:
			return {"ok": false, "reason": "prototype_null_" + kind, "gap_m": gap, "placements": [], "extent_x_m": 0.0, "extent_z_m": 0.0}
		var rotation_deg := Vector3.ZERO
		if kind == "casing":
			rotation_deg = Vector3(90.0, 0.0, 0.0)
		prototype.rotation_degrees = rotation_deg
		var box := _aabb_relative(prototype)
		prototype.free()
		items.append({"kind": kind, "index": idx, "rotation_deg": rotation_deg, "box": box})
	var rows: Array = []
	var current: Array = []
	var width := 0.0
	for item_v in items:
		var item: Dictionary = item_v
		var box: AABB = item["box"]
		var w := box.size.x
		if w > 2.0 * PACK_X_LIMIT:
			return {"ok": false, "reason": "item_too_wide:" + str(item["kind"]), "gap_m": gap, "placements": [], "extent_x_m": 0.0, "extent_z_m": 0.0}
		if current.size() > 0 and width + gap + w > 2.0 * PACK_X_LIMIT:
			rows.append(current)
			current = []
			width = 0.0
		if current.size() > 0:
			width += gap
		current.append(item)
		width += w
	if current.size() > 0:
		rows.append(current)
	var row_depths: Array = []
	var total_depth := 0.0
	for row_v in rows:
		var row: Array = row_v
		var depth := 0.0
		for item_v in row:
			var item: Dictionary = item_v
			var box: AABB = item["box"]
			depth = maxf(depth, box.size.z)
		row_depths.append(depth)
		total_depth += depth
	var row_count := rows.size()
	var z_gap := 0.0
	if row_count > 1:
		var leftover := 2.0 * PACK_Z_LIMIT - total_depth
		if leftover < gap * float(row_count - 1) - 0.0001:
			return {"ok": false, "reason": "depth_exceeded", "gap_m": gap, "placements": [], "extent_x_m": 0.0, "extent_z_m": 0.0}
		z_gap = minf(3.0, leftover / float(row_count - 1))
	elif total_depth > 2.0 * PACK_Z_LIMIT + 0.0001:
		return {"ok": false, "reason": "depth_exceeded", "gap_m": gap, "placements": [], "extent_x_m": 0.0, "extent_z_m": 0.0}
	var placements: Array = []
	var z_cursor := -PACK_Z_LIMIT
	if row_count == 1:
		z_cursor = -total_depth * 0.5
	for r in row_count:
		var row: Array = rows[r]
		var depth: float = row_depths[r]
		var natural := gap * float(row.size() - 1)
		for item_v in row:
			var item: Dictionary = item_v
			var box: AABB = item["box"]
			natural += box.size.x
		var x_gap := gap
		var width_final := natural
		if row.size() > 1:
			var extra := (2.0 * PACK_X_LIMIT - natural) / float(row.size() - 1)
			x_gap = minf(4.0, gap + extra)
			width_final = natural + (x_gap - gap) * float(row.size() - 1)
		var x_cursor := -width_final * 0.5
		for item_v in row:
			var item: Dictionary = item_v
			var box: AABB = item["box"]
			var pos := Vector3(x_cursor + box.size.x * 0.5, FLOOR_Y + box.size.y * 0.5, z_cursor + box.size.z * 0.5)
			placements.append({
				"kind": str(item["kind"]),
				"index": int(item["index"]),
				"position": pos,
				"rotation_deg": item["rotation_deg"],
				"local_bounds": box,
			})
			x_cursor += box.size.x + x_gap
		z_cursor += depth + z_gap
	var max_x := -INF
	var max_z := -INF
	for p_v in placements:
		var p: Dictionary = p_v
		var pos: Vector3 = p["position"]
		var lb: AABB = p["local_bounds"]
		max_x = maxf(max_x, pos.x + lb.size.x * 0.5)
		max_z = maxf(max_z, pos.z + lb.size.z * 0.5)
	return {"ok": true, "reason": "", "gap_m": gap, "z_gap_m": z_gap, "placements": placements, "extent_x_m": max_x, "extent_z_m": max_z}

func _shot_04_05_world() -> Dictionary:
	var pack := _pack_world_layout()
	if not bool(pack.get("ok", false)):
		return {"ok": false, "error": "pack_failed:" + str(pack.get("reason", "unknown"))}
	var placements: Array = pack["placements"]
	var world := Node3D.new()
	world.name = "WorldGrid"
	root.add_child(world)
	var frame: Node3D = _lib.create_frame()
	if frame == null:
		return {"ok": false, "error": "create_frame_null"}
	frame.name = "FrameWorkspace"
	world.add_child(frame)
	var objects: Array = []
	for p_v in placements:
		var p: Dictionary = p_v
		var kind := str(p["kind"])
		var node: Node3D = null
		if kind == "drill":
			node = _lib.create_drill()
			node.name = "Drill_WorldOverview"
		else:
			node = _lib.create_obstacle(kind)
			node.name = "Obstacle_" + kind + "_" + str(int(p["index"]))
		if node == null:
			return {"ok": false, "error": "create_null_" + kind}
		var pos: Vector3 = p["position"]
		var rot: Vector3 = p["rotation_deg"]
		node.position = pos
		node.rotation_degrees = rot
		world.add_child(node)
		objects.append({
			"kind": kind,
			"index": int(p["index"]),
			"node": String(node.name),
			"position_m": _v3(pos),
			"rotation_deg": _v3(rot),
		})
	var wbox := _aabb_of(world)
	var fit4 := _fit_camera(wbox, Vector3(-0.5, 0.9, 0.8), 1.12)
	var record4: Dictionary = await _capture("04_world_overview_30obstacles_drill_frame")
	record4["purpose"] = "full world overview: 30 obstacles (5 kinds x 6), the drill, and the 12-edge workspace frame cube [-15,15]^3"
	record4["render_frame_sync"] = "await process_frame x4 + RenderingServer.frame_post_draw"
	record4["objects"] = objects
	record4["object_count"] = objects.size() + 1
	record4["world_bounds_m"] = _aabb_dict(wbox)
	record4["pack"] = {
		"gap_m": float(pack["gap_m"]),
		"extent_x_m": float(pack["extent_x_m"]),
		"extent_z_m": float(pack["extent_z_m"]),
		"fallback_used": bool(pack.get("fallback_used", false)),
		"row_gap_m": float(pack.get("z_gap_m", 0.0)),
		"floor_y_m": FLOOR_Y,
	}
	record4["measurements"] = _measure_world(world)
	record4["camera"] = fit4
	record4["ok"] = bool(record4.get("save_png_ok", false))
	if not bool(record4["ok"]):
		record4["error"] = "save_png_failed:" + str(record4.get("save_png_error", -1))
	_shots.append(record4)
	var fit5 := _fit_camera(wbox, Vector3(0.9, 0.34, -0.55), 1.04)
	var record5: Dictionary = await _capture("05_world_alt_angle_hollow_edge_cube")
	record5["purpose"] = "alternate angle of the same 32 objects; camera-only change; the frame shows 12 edge prisms with no face surfaces (hollow edge-only cube)"
	record5["render_frame_sync"] = "await process_frame x4 + RenderingServer.frame_post_draw"
	record5["objects_same_as"] = "04_world_overview_30obstacles_drill_frame"
	record5["camera"] = fit5
	record5["ok"] = bool(record5.get("save_png_ok", false))
	if not bool(record5["ok"]):
		record5["error"] = "save_png_failed:" + str(record5.get("save_png_error", -1))
	_shots.append(record5)
	var ok := bool(record4["ok"]) and bool(record5["ok"])
	return {"ok": ok, "error": "" if ok else "save_png_failed"}


func _capture(shot_name: String) -> Dictionary:
	for i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	var img: Image = root.get_texture().get_image()
	var record: Dictionary = {"shot": shot_name, "fixture_label": FIXTURE_LABEL}
	if img == null:
		record["error"] = "viewport_image_null"
		record["save_png_ok"] = false
		print("CAPTURE_FAILED shot=", shot_name, " reason=viewport_image_null")
		return record
	var flipped := false
	if not _is_magenta(img.get_pixel(int(img.get_width() / 2), 3)) and _is_magenta(img.get_pixel(int(img.get_width() / 2), img.get_height() - 4)):
		img.flip_y()
		flipped = true
	record["flipped_y"] = flipped
	record.merge(_image_stats(img))
	var out_path := ProjectSettings.globalize_path("res://png/" + shot_name + ".png")
	var err := img.save_png(out_path)
	record["path"] = out_path
	record["image_width"] = img.get_width()
	record["image_height"] = img.get_height()
	record["expected_viewport"] = [VIEW_W, VIEW_H]
	record["save_png_error"] = int(err)
	record["save_png_ok"] = bool(err == OK)
	print("CAPTURED shot=", shot_name, " path=", out_path, " ok=", str(err == OK), " size=", str(img.get_width()), "x", str(img.get_height()), " flipped_y=", str(flipped), " stats=", JSON.stringify(_image_stats(img)))
	return record


func _image_stats(img: Image) -> Dictionary:
	var w := img.get_width()
	var h := img.get_height()
	var step_x := maxi(1, int(w / 160))
	var step_y := maxi(1, int(h / 90))
	var count := 0
	var lum_sum := 0.0
	var lum_sq := 0.0
	var near_black := 0
	var distinct := {}
	var y := 0
	while y < h:
		var x := 0
		while x < w:
			var c := img.get_pixel(x, y)
			var lum := c.r * 0.2126 + c.g * 0.7152 + c.b * 0.0722
			lum_sum += lum
			lum_sq += lum * lum
			if lum < 0.02:
				near_black += 1
			distinct[int(c.r * 255.0) * 65536 + int(c.g * 255.0) * 256 + int(c.b * 255.0)] = true
			count += 1
			x += step_x
		y += step_y
	var mean := lum_sum / float(count)
	var stddev := sqrt(maxf(lum_sq / float(count) - mean * mean, 0.0))
	var near_black_fraction := float(near_black) / float(count)
	return {
		"samples": count,
		"distinct_colors_sample": distinct.size(),
		"mean_luminance": mean,
		"stddev_luminance": stddev,
		"near_black_fraction": near_black_fraction,
		"content_nonblank": (distinct.size() >= 64 and stddev >= 0.02 and near_black_fraction < 0.98),
	}


func _is_magenta(c: Color) -> bool:
	return c.r > 0.5 and c.b > 0.5 and c.g < 0.35


func _fit_camera(bounds: AABB, direction: Vector3, margin: float) -> Dictionary:
	var center := bounds.get_center()
	var radius := maxf(bounds.size.length() * 0.5, 0.05)
	var vfov := deg_to_rad(_camera.fov)
	var dist := radius / maxf(sin(vfov * 0.5), 0.0001) * margin
	_camera.global_position = center + direction.normalized() * dist
	_camera.look_at(center, Vector3.FORWARD if absf(direction.normalized().dot(Vector3.UP)) > 0.99 else Vector3.UP)
	return {
		"eye_m": _v3(_camera.global_position),
		"target_m": _v3(center),
		"distance_m": dist,
		"bounds_radius_m": radius,
		"fov_deg": _camera.fov,
		"direction": _v3(direction.normalized()),
	}


func _mesh_instances(node: Node) -> Array:
	return node.find_children("*", "MeshInstance3D", true, false)


func _aabb_corners(b: AABB) -> Array:
	var out: Array = []
	for i in 8:
		out.append(b.position + Vector3(
			b.size.x * float(i & 1),
			b.size.y * float((i >> 1) & 1),
			b.size.z * float((i >> 2) & 1)))
	return out


func _aabb_of(node: Node) -> AABB:
	var mn := Vector3(INF, INF, INF)
	var mx := Vector3(-INF, -INF, -INF)
	var found := false
	for node_v in _mesh_instances(node):
		var mi := node_v as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		var xf := mi.global_transform
		for c_v in _aabb_corners(mi.mesh.get_aabb()):
			var w: Vector3 = xf * c_v
			mn = Vector3(minf(mn.x, w.x), minf(mn.y, w.y), minf(mn.z, w.z))
			mx = Vector3(maxf(mx.x, w.x), maxf(mx.y, w.y), maxf(mx.z, w.z))
			found = true
	if not found:
		return AABB()
	return AABB(mn, mx - mn)


func _aabb_relative(asset: Node3D) -> AABB:
	var mn := Vector3(INF, INF, INF)
	var mx := Vector3(-INF, -INF, -INF)
	var found := false
	for node_v in _mesh_instances(asset):
		var mi := node_v as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		var chain: Array = []
		var walk: Node = mi
		while walk != null and walk != asset:
			chain.append((walk as Node3D).transform)
			walk = walk.get_parent()
		var xf := Transform3D(asset.transform.basis, Vector3.ZERO)
		for i in range(chain.size() - 1, -1, -1):
			xf = xf * chain[i]
		for c_v in _aabb_corners(mi.mesh.get_aabb()):
			var w: Vector3 = xf * c_v
			mn = Vector3(minf(mn.x, w.x), minf(mn.y, w.y), minf(mn.z, w.z))
			mx = Vector3(maxf(mx.x, w.x), maxf(mx.y, w.y), maxf(mx.z, w.z))
			found = true
	if not found:
		return AABB()
	return AABB(mn, mx - mn)


func _aabb_of_named(asset: Node3D, prefixes: Array) -> AABB:
	var mn := Vector3(INF, INF, INF)
	var mx := Vector3(-INF, -INF, -INF)
	var found := false
	for node_v in _mesh_instances(asset):
		var mi := node_v as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		var n := String(mi.name)
		var matched := false
		for p_v in prefixes:
			if n.begins_with(str(p_v)):
				matched = true
				break
		if not matched:
			continue
		var xf := mi.global_transform
		for c_v in _aabb_corners(mi.mesh.get_aabb()):
			var w: Vector3 = xf * c_v
			mn = Vector3(minf(mn.x, w.x), minf(mn.y, w.y), minf(mn.z, w.z))
			mx = Vector3(maxf(mx.x, w.x), maxf(mx.y, w.y), maxf(mx.z, w.z))
			found = true
	if not found:
		return AABB()
	return AABB(mn, mx - mn)


func _measure_world(world: Node) -> Dictionary:
	var totals := {
		"objects": 0,
		"node_total": 0,
		"mesh_instance_total": 0,
		"triangle_total": 0,
		"collision_shape_total": 0,
		"static_body_total": 0,
	}
	var per_object: Array = []
	for child_v in world.get_children():
		var child := child_v as Node3D
		if child == null:
			continue
		var mesh_count := 0
		var tri_count := 0
		for node_v in _mesh_instances(child):
			var mi := node_v as MeshInstance3D
			if mi == null or mi.mesh == null:
				continue
			mesh_count += 1
			tri_count += int(round(float(mi.mesh.get_faces().size()) / 3.0))
		var shape_count := child.find_children("*", "CollisionShape3D", true, false).size()
		var body_count := child.find_children("*", "StaticBody3D", true, false).size()
		var node_count := 1 + child.find_children("*", "", true, false).size()
		per_object.append({
			"node": String(child.name),
			"asset_id": str(child.get_meta(&"asset_id", "")),
			"mesh_instances": mesh_count,
			"triangles": tri_count,
			"collision_shapes": shape_count,
			"static_bodies": body_count,
			"node_total": node_count,
		})
		totals["objects"] += 1
		totals["node_total"] += node_count
		totals["mesh_instance_total"] += mesh_count
		totals["triangle_total"] += tri_count
		totals["collision_shape_total"] += shape_count
		totals["static_body_total"] += body_count
	return {"totals": totals, "per_object": per_object}


func _aabb_dict(b: AABB) -> Dictionary:
	return {"min_m": _v3(b.position), "max_m": _v3(b.end), "size_m": _v3(b.size), "center_m": _v3(b.get_center())}


func _measure_dict(m: Dictionary) -> Dictionary:
	return {
		"min_m": _v3(m["min"]),
		"max_m": _v3(m["max"]),
		"size_m": _v3(m["size"]),
		"center_m": _v3(m["center"]),
		"pivot_bound_radius_m": float(m["pivot_bound_radius_m"]),
		"max_radius_about_z_m": float(m["max_radius_about_z_m"]),
		"vertex_count": int(m["vertex_count"]),
		"mesh_count": int(m["mesh_count"]),
	}


func _meta_bounds_dict(node: Node) -> Dictionary:
	var raw: Dictionary = node.get_meta(&"geometry_bounds_m", {})
	if raw.is_empty():
		return {}
	return {"min_m": _v3(raw.get("min", Vector3.ZERO)), "max_m": _v3(raw.get("max", Vector3.ZERO)), "size_m": _v3(raw.get("size", Vector3.ZERO))}


func _v3(v: Vector3) -> Array:
	return [v.x, v.y, v.z]


func _v2i(v: Vector2i) -> Array:
	return [v.x, v.y]


func _write_report() -> void:
	var text := JSON.stringify(_report, "  ")
	var path := ProjectSettings.globalize_path("res://results/render_report.json")
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://results"))
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("RENDER_REPORT_WRITE_FAILED path=", path)
		return
	f.store_string(text)
	f.close()
	print("RENDER_REPORT_WRITTEN path=", path, " bytes=", text.length())


func _write_measurements() -> void:
	var out := {
		"task_id": "DEEPEYE-IMPLEMENTATION-20261014",
		"task_version": 1,
		"work_id": "B-ASSETS-MAIN-RENDER-20261016-04",
		"fixture_label": FIXTURE_LABEL,
	}
	for record_v in _shots:
		var record: Dictionary = record_v
		var shot := str(record.get("shot", ""))
		if shot.begins_with("01_"):
			out["drill_actual_scale"] = {
				"bounds_m": record.get("bounds_m"),
				"measured_visual": record.get("measured_visual"),
				"mesh_node_names": record.get("mesh_node_names"),
				"mesh_instance_count": record.get("mesh_instance_count"),
			}
		elif shot.begins_with("02_"):
			out["drill_head_detail"] = {
				"detail_bounds_m": record.get("detail_bounds_m"),
				"blade_count": record.get("blade_count"),
				"stud_count": record.get("stud_count"),
				"blade_nodes": record.get("blade_nodes"),
				"stud_nodes": record.get("stud_nodes"),
			}
		elif shot.begins_with("03_"):
			out["gallery"] = {
				"objects": record.get("objects"),
				"gallery_bounds_m": record.get("gallery_bounds_m"),
			}
		elif shot.begins_with("04_"):
			out["world"] = {
				"measurements": record.get("measurements"),
				"pack": record.get("pack"),
				"object_count": record.get("object_count"),
			}
	var text := JSON.stringify(out, "  ")
	var path := ProjectSettings.globalize_path("res://results/render_measurements.json")
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("RENDER_MEASUREMENTS_WRITE_FAILED path=", path)
		return
	f.store_string(text)
	f.close()
	print("RENDER_MEASUREMENTS_WRITTEN path=", path, " bytes=", text.length())


func _fail_main(reason: String) -> void:
	_report["status"] = "failed:" + reason
	_report["shots"] = _shots
	_report["finished_utc"] = Time.get_datetime_string_from_system(true, false)
	print("RENDER_HARNESS_FAILED reason=", reason)
	_write_report()
	quit(3)