extends SceneTree

## DeepEye B asset contract test. Run headless:
##   godot --headless --path competition/deepeye/simulator --script res://tests/test_asset_contract.gd
## Non-zero exit means a failure. This test is B-owned (simulator/tests/test_asset_contract.gd).
## It re-derives every measurement from actual mesh faces; catalog values come from
## simulator/assets/scene_catalog.json provenance (closed-form or independent Python
## replica of the generator) and are cross-checked here against the engine mesh.
## Human contract DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
## c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.

const AssetLibrary := preload("res://world/asset_library.gd")

const TOLERANCE_M := 2e-6
const WELD_SCALE := 1000000.0
const OBSTACLE_KINDS := ["water", "hard_rock", "fault", "void", "casing"]
const DRILL_ROTATION_BOUND_RADIUS_M := 0.52
const SCENE_TRIANGLE_BUDGET := 300000

const OBSTACLE_DECLARED := {
    "water": {"size": Vector3(6.0, 4.0, 2.0), "min_ratio": Vector3(0.90, 0.999, 0.90)},
    "hard_rock": {"size": Vector3(3.0, 3.0, 3.0), "min_ratio": Vector3(0.70, 0.999, 0.70)},
    "fault": {"size": Vector3(8.0, 1.0, 6.0), "min_ratio": Vector3(0.99999, 0.99999, 0.99999)},
    "void": {"size": Vector3(4.0, 3.0, 3.0), "min_ratio": Vector3(0.99999, 0.99999, 0.99999)},
    "casing": {"size": Vector3(0.8, 0.8, 8.0), "min_ratio": Vector3(0.985, 0.985, 0.99999)},
}

## Volume provenance: water/hard_rock/void are the deterministic star-mesh volumes
## computed by the independent Python replica (double precision, divergence theorem)
## of the generator in world/obstacle_geometry.gd; fault and casing are closed-form
## prisms (casing: 48-gon area x 8 m). The same values are recorded in
## simulator/assets/scene_catalog.json.
const OBSTACLE_VOLUMES := {
    "water": {"volume_m3": 23.7359, "tolerance_ratio": 0.01},
    "hard_rock": {"volume_m3": 9.8210, "tolerance_ratio": 0.015},
    "fault": {"volume_m3": 48.0, "tolerance_ratio": 0.0001},
    "void": {"volume_m3": 18.7154, "tolerance_ratio": 0.01},
    "casing": {"volume_m3": 4.0098, "tolerance_ratio": 0.005},
}

var _checks := 0
var _failures := 0

func _initialize() -> void:
    print("test_asset_contract: DeepEye B factory contract test")
    print("task=DEEPEYE-IMPLEMENTATION-20261014/v1 work=B-ASSETS-FACTORY-FOUNDATION-20261015-01-v1")
    print("godot=" + str(Engine.get_version_info().get("string", "unknown")))
    _test_drill()
    for kind in OBSTACLE_KINDS:
        _test_obstacle_kind(kind)
    _test_obstacle_unknown_kind()
    _test_frame()
    _test_30_instances()
    print("RESULT checks=" + str(_checks) + " failures=" + str(_failures))
    quit(1 if _failures > 0 else 0)

func _check(condition: bool, label: String) -> void:
    _checks += 1
    if condition:
        return
    _failures += 1
    printerr("FAIL: " + label)

func _check_close(actual: float, expected: float, tolerance: float, label: String) -> void:
    _check(absf(actual - expected) <= tolerance, label + " actual=" + str(actual) + " expected=" + str(expected))

func _test_drill() -> void:
    var drill: Node3D = AssetLibrary.create_drill()
    _check(drill != null, "drill created")
    if drill == null:
        return
    _check_children(drill, "drill")
    var measured := _measure(drill)
    var size: Vector3 = measured["size"]
    _check_close(size.z, 0.80, TOLERANCE_M, "drill rigid length 0.80 m")
    _check(size.x <= 0.24 + TOLERANCE_M and size.y <= 0.24 + TOLERANCE_M, "drill diameter <= 0.24 m")
    _check(size.x >= 0.239 and size.y >= 0.239, "drill diameter reaches 0.24 m discretization limit")
    _check(float(measured["max_radius_about_z_m"]) <= 0.12 + TOLERANCE_M, "drill radial envelope <= 0.12 m")
    _check_close(float(measured["max_radius_about_z_m"]), 0.12, 0.001, "drill maximum radius 0.12 m")
    _check(absf(float(measured["min"].z) + 0.40) <= TOLERANCE_M and absf(float(measured["max"].z) - 0.40) <= TOLERANCE_M, "drill z extent [-0.40, 0.40]")
    var pivot := float(measured["pivot_bound_radius_m"])
    _check(pivot <= DRILL_ROTATION_BOUND_RADIUS_M + TOLERANCE_M, "drill pivot radius within contract rotation bound 0.52 m")
    _check(pivot >= 0.39, "drill pivot radius plausible for 0.80 m body")
    _check(absf(pivot - DRILL_ROTATION_BOUND_RADIUS_M) > 1e-6, "drill pivot radius is measured, not the stamped 0.52 m bound")
    _check_metadata(drill, measured, "drill")
    var metadata_pivot := float(drill.get_meta(&"pivot_bound_radius_m"))
    _check_close(metadata_pivot, pivot, 1e-9, "drill metadata pivot radius equals measured transformed-vertex radius")
    var meshes := _visual_meshes(drill)
    _check(meshes.size() >= 10, "drill has cutter head, body, joint, collar, blades and cutters (>= 10 meshes)")
    _check(drill.get_node_or_null("Visual/HeadPDC") != null, "drill cutter head node present")
    _check(drill.get_node_or_null("Visual/BodyMatrix") != null, "drill metal matrix body node present")
    _check(drill.get_node_or_null("Visual/Joint") != null, "drill joint node present")
    _check(drill.get_node_or_null("Visual/Collar") != null, "drill collar node present")
    _check(drill.find_children("Blade*", "MeshInstance3D", true, false).size() == 6, "drill has six visual-only blades")
    _check(drill.find_children("CutterStud*", "MeshInstance3D", true, false).size() == 18, "drill has eighteen PDC cutter studs")
    var unique_colors := {}
    for mesh_instance in meshes:
        var material := mesh_instance.material_override as StandardMaterial3D
        if material != null:
            unique_colors[material.albedo_color.to_html(false)] = true
    _check(unique_colors.size() >= 3, "drill exposes at least three distinguishable materials")
    print("MEASURE asset_id=drill_pdc_v1 size=" + str(size) + " pivot_radius_m=" + str(pivot) + " max_radius_about_z_m=" + str(measured["max_radius_about_z_m"]) + " triangles=" + str(_count_triangles(drill)))

func _test_obstacle_kind(kind: String) -> void:
    var obstacle: Node3D = AssetLibrary.create_obstacle(kind)
    _check(obstacle != null, "obstacle '" + kind + "' created")
    if obstacle == null:
        return
    _check_children(obstacle, kind)
    var measured := _measure(obstacle)
    var declared: Dictionary = OBSTACLE_DECLARED[kind]
    var declared_size: Vector3 = declared["size"]
    var min_ratio: Vector3 = declared["min_ratio"]
    var size: Vector3 = measured["size"]
    _check(size.x <= declared_size.x + TOLERANCE_M, kind + " x extent inside declared envelope")
    _check(size.y <= declared_size.y + TOLERANCE_M, kind + " y extent inside declared envelope")
    _check(size.z <= declared_size.z + TOLERANCE_M, kind + " z extent inside declared envelope")
    _check(size.x >= declared_size.x * min_ratio.x - TOLERANCE_M, kind + " x extent not collapsed")
    _check(size.y >= declared_size.y * min_ratio.y - TOLERANCE_M, kind + " y extent not collapsed")
    _check(size.z >= declared_size.z * min_ratio.z - TOLERANCE_M, kind + " z extent not collapsed")
    _check_metadata(obstacle, measured, kind)
    var topology := _closed_solid_report(_visual_meshes(obstacle))
    _check(int(topology["boundary_edges"]) == 0, kind + " mesh is closed (all edges paired)")
    _check(int(topology["degenerate_triangles"]) == 0, kind + " mesh has no degenerate triangles")
    var volume := float(topology["volume_m3"])
    _check(volume > 0.0, kind + " mesh has nonzero positive volume")
    var expected: Dictionary = OBSTACLE_VOLUMES[kind]
    var tolerance := float(expected["volume_m3"]) * float(expected["tolerance_ratio"])
    _check(absf(volume - float(expected["volume_m3"])) <= tolerance, kind + " mesh volume matches catalog provenance actual=" + str(volume))
    print("MEASURE asset_id=obstacle_" + kind + "_v1 size=" + str(size) + " volume_m3=" + str(volume) + " pivot_radius_m=" + str(measured["pivot_bound_radius_m"]) + " triangles=" + str(_count_triangles(obstacle)))

func _test_obstacle_unknown_kind() -> void:
    var obstacle: Node3D = AssetLibrary.create_obstacle("bogus_kind")
    _check(obstacle == null, "unknown obstacle kind returns null")

func _test_frame() -> void:
    var frame: Node3D = AssetLibrary.create_frame()
    _check(frame != null, "frame created")
    if frame == null:
        return
    _check_children(frame, "frame")
    var measured := _measure(frame)
    _check_close(float(measured["min"].x), -15.0, TOLERANCE_M, "frame min x")
    _check_close(float(measured["min"].y), -15.0, TOLERANCE_M, "frame min y")
    _check_close(float(measured["min"].z), -15.0, TOLERANCE_M, "frame min z")
    _check_close(float(measured["max"].x), 15.0, TOLERANCE_M, "frame max x")
    _check_close(float(measured["max"].y), 15.0, TOLERANCE_M, "frame max y")
    _check_close(float(measured["max"].z), 15.0, TOLERANCE_M, "frame max z")
    _check_metadata(frame, measured, "frame")
    var meshes := _visual_meshes(frame)
    _check(meshes.size() == 12, "frame shows exactly 12 visible edges (meshes=" + str(meshes.size()) + ")")
    for mesh_instance in meshes:
        _check(String(mesh_instance.name).begins_with("Edge_A"), "frame mesh named as edge: " + str(mesh_instance.name))
        var mesh := mesh_instance.mesh
        if mesh == null:
            _check(false, "frame edge has mesh: " + str(mesh_instance.name))
            continue
        _check(_count_mesh_triangles(mesh) == 12, "frame edge is a closed box prism (12 triangles): " + str(mesh_instance.name))
        var aabb := mesh.get_aabb()
        var long_extent := maxf(aabb.size.x, maxf(aabb.size.y, aabb.size.z))
        var short_extent := minf(aabb.size.x, minf(aabb.size.y, aabb.size.z))
        _check_close(long_extent, 30.0, 1e-4, "frame edge full length 30 m: " + str(mesh_instance.name))
        _check(short_extent <= 0.13, "frame edge cross-section thin: " + str(mesh_instance.name))
    var collision := frame.get_node_or_null("Collision")
    _check(collision != null and collision is StaticBody3D, "frame collision child is StaticBody3D")
    if collision != null:
        _check(collision.get_child_count() == 12, "frame collision envelope has 12 edge shapes")
    _check(int(measured["mesh_count"]) == 12, "frame visual node count is exactly 12")
    print("MEASURE asset_id=frame_workspace_v1 size=" + str(measured["size"]) + " pivot_radius_m=" + str(measured["pivot_bound_radius_m"]) + " triangles=" + str(_count_triangles(frame)))

func _check_children(asset: Node3D, label: String) -> void:
    _check(asset.get_child_count() == 2, label + " has exactly two children")
    var visual := asset.get_node_or_null("Visual")
    var collision := asset.get_node_or_null("Collision")
    _check(visual != null, label + " child Visual present")
    _check(collision != null, label + " child Collision present")
    if collision != null:
        _check(collision is StaticBody3D, label + " Collision is StaticBody3D")
        _check(collision.collision_layer == 0 and collision.collision_mask == 0, label + " collision disabled in viewer (layer/mask 0)")
        _check(bool(collision.get_meta(&"disabled_in_viewer", false)), label + " collision flagged disabled_in_viewer")
        var shape_nodes := 0
        for child in collision.get_children():
            if child is CollisionShape3D:
                shape_nodes += 1
                _check(child.disabled, label + " collision shape disabled: " + str(child.name))
        _check(shape_nodes >= 1, label + " collision envelope defines at least one shape")
    _check_asset_has_no_truth_api(asset, label)

func _check_asset_has_no_truth_api(asset: Node3D, label: String) -> void:
    var forbidden := ["get_truth", "query_truth", "truth_state", "reveal_truth", "world_truth"]
    var clean := true
    for node in _all_nodes(asset):
        _check(node.get_script() == null, label + " node has no script attached: " + str(node.name))
        for method in forbidden:
            if node.has_method(method):
                clean = false
        if node is Area3D:
            clean = false
    _check(clean, label + " exposes no authority or truth API")

func _check_metadata(asset: Node3D, measured: Dictionary, label: String) -> void:
    _check(asset.has_meta(&"asset_contract_version"), label + " metadata asset_contract_version present")
    _check(int(asset.get_meta(&"asset_contract_version", -1)) == 1, label + " asset_contract_version == 1")
    _check(asset.has_meta(&"source_license"), label + " metadata source_license present")
    _check(String(asset.get_meta(&"source_license", "")) != "", label + " source_license non-empty")
    _check(asset.has_meta(&"geometry_bounds_m"), label + " metadata geometry_bounds_m present")
    var bounds: Dictionary = asset.get_meta(&"geometry_bounds_m", {})
    _check(bounds.has("min") and bounds.has("max") and bounds.has("size"), label + " geometry_bounds_m has min/max/size")
    _check(asset.has_meta(&"pivot_bound_radius_m"), label + " metadata pivot_bound_radius_m present")
    var pivot := float(asset.get_meta(&"pivot_bound_radius_m", -1.0))
    _check(pivot > 0.0, label + " pivot_bound_radius_m positive")
    _check_close(pivot, float(measured["pivot_bound_radius_m"]), 1e-6, label + " pivot_bound_radius_m equals measured vertices")
    _check(bool(asset.get_meta(&"envelope_ok", false)), label + " factory envelope self-check passed")

func _visual_meshes(asset: Node3D) -> Array:
    var meshes := []
    var visual := asset.get_node_or_null("Visual")
    if visual == null:
        return meshes
    for node in visual.find_children("*", "MeshInstance3D", true, false):
        meshes.append(node)
    return meshes

func _all_nodes(root_node: Node) -> Array:
    var nodes := [root_node]
    for child in root_node.find_children("*", "", true, false):
        nodes.append(child)
    return nodes

func _measure(asset: Node3D) -> Dictionary:
    var minimum := Vector3(INF, INF, INF)
    var maximum := Vector3(-INF, -INF, -INF)
    var pivot_radius := 0.0
    var axis_radius := 0.0
    var mesh_count := 0
    for node in asset.find_children("*", "MeshInstance3D", true, false):
        var mesh_instance := node as MeshInstance3D
        if mesh_instance.mesh == null:
            continue
        mesh_count += 1
        var xform := _relative_transform(asset, mesh_instance)
        for vertex in mesh_instance.mesh.get_faces():
            var transformed: Vector3 = xform * vertex
            minimum = Vector3(minf(minimum.x, transformed.x), minf(minimum.y, transformed.y), minf(minimum.z, transformed.z))
            maximum = Vector3(maxf(maximum.x, transformed.x), maxf(maximum.y, transformed.y), maxf(maximum.z, transformed.z))
            pivot_radius = maxf(pivot_radius, transformed.length())
            axis_radius = maxf(axis_radius, sqrt(transformed.x * transformed.x + transformed.y * transformed.y))
    return {
        "min": minimum, "max": maximum, "size": maximum - minimum,
        "pivot_bound_radius_m": pivot_radius, "max_radius_about_z_m": axis_radius, "mesh_count": mesh_count,
    }

func _relative_transform(asset: Node3D, node: Node3D) -> Transform3D:
    var xform := node.transform
    var parent := node.get_parent()
    while parent != null and parent != asset:
        if parent is Node3D:
            xform = (parent as Node3D).transform * xform
        parent = parent.get_parent()
    return xform

func _weld_id(map: Dictionary, vertex: Vector3) -> int:
    var key := Vector3i(roundi(vertex.x * WELD_SCALE), roundi(vertex.y * WELD_SCALE), roundi(vertex.z * WELD_SCALE))
    if not map.has(key):
        map[key] = map.size()
    return int(map[key])

func _count_mesh_triangles(mesh: Mesh) -> int:
    return mesh.get_faces().size() / 3

func _count_triangles(asset: Node3D) -> int:
    var total := 0
    for node in asset.find_children("*", "MeshInstance3D", true, false):
        var mesh_instance := node as MeshInstance3D
        if mesh_instance.mesh != null:
            total += _count_mesh_triangles(mesh_instance.mesh)
    return total

func _closed_solid_report(mesh_instances: Array) -> Dictionary:
    var boundary_edges := 0
    var degenerate := 0
    var volume := 0.0
    for mesh_instance in mesh_instances:
        var mesh: Mesh = mesh_instance.mesh
        if mesh == null:
            continue
        var faces := mesh.get_faces()
        var welded := {}
        var edges := {}
        for face_index in range(0, faces.size(), 3):
            var triangle := PackedInt32Array()
            for offset in 3:
                triangle.push_back(_weld_id(welded, faces[face_index + offset]))
            var a := triangle[0]
            var b := triangle[1]
            var c := triangle[2]
            if a == b or b == c or c == a:
                degenerate += 1
                continue
            var triangle_ids := [a, b, c]
            for edge_index in 3:
                var u: int = triangle_ids[edge_index]
                var v: int = triangle_ids[(edge_index + 1) % 3]
                var low := mini(u, v)
                var high := maxi(u, v)
                var key := str(low) + ":" + str(high)
                var entry: Array = edges.get(key, [0, 0])
                entry[0] = int(entry[0]) + 1
                entry[1] = int(entry[1]) + (1 if u == low else -1)
                edges[key] = entry
            var p0 := faces[face_index]
            var p1 := faces[face_index + 1]
            var p2 := faces[face_index + 2]
            volume += p0.dot(p1.cross(p2)) / 6.0
        for key in edges.keys():
            var entry: Array = edges[key]
            if int(entry[0]) != 2 or int(entry[1]) != 0:
                boundary_edges += 1
    return {"boundary_edges": boundary_edges, "degenerate_triangles": degenerate, "volume_m3": volume}

func _test_30_instances() -> void:
    var holder := Node3D.new()
    holder.name = "ThirtyInstanceProbe"
    root.add_child(holder)
    var created := 0
    for index in 30:
        var kind: String = OBSTACLE_KINDS[index % OBSTACLE_KINDS.size()]
        var obstacle: Node3D = AssetLibrary.create_obstacle(kind)
        if obstacle == null:
            _check(false, "30-instance obstacle created: " + kind)
            continue
        holder.add_child(obstacle)
        created += 1
    _check(created == 30, "30 obstacle instances load together")
    var drill: Node3D = AssetLibrary.create_drill()
    holder.add_child(drill)
    var frame: Node3D = AssetLibrary.create_frame()
    holder.add_child(frame)
    var total_triangles := 0
    var total_meshes := 0
    for node in holder.find_children("*", "MeshInstance3D", true, false):
        var mesh_instance := node as MeshInstance3D
        if mesh_instance.mesh != null:
            total_triangles += _count_mesh_triangles(mesh_instance.mesh)
            total_meshes += 1
    _check(total_triangles > 0, "30-instance probe triangle count measured")
    _check(total_triangles <= SCENE_TRIANGLE_BUDGET, "asset-only triangles within 300k scene budget: " + str(total_triangles))
    _check(holder.get_child_count() == 32, "probe holds 30 obstacles + drill + frame")
    print("MEASURE thirty_instance_probe objects=32 meshes=" + str(total_meshes) + " triangles=" + str(total_triangles))