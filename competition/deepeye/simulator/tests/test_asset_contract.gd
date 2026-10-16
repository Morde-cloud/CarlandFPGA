extends SceneTree

## DeepEye B asset contract test. Run headless:
##   godot --headless --path competition/deepeye/simulator --script res://tests/test_asset_contract.gd
## Non-zero exit means a failure. This test is B-owned (simulator/tests/test_asset_contract.gd).
## It re-derives every measurement from actual mesh faces; catalog values come from
## simulator/assets/scene_catalog.json provenance (closed-form, independent Python
## replica or real-engine MEASURE lines) and are cross-checked here against the
## engine mesh. Correction-02 (B-ASSETS-RUNTIME-CORRECTION-20261016-02-v1): the
## closed-solid volume and per-face orientation use the explicit Godot clockwise
## front-face convention, opposite-winding negative controls are asserted, and
## every probe/factory instance is freed deterministically before quit.
## Correction-03 (B-ASSETS-RUNTIME-CORRECTION-20261016-03-v1): the independent
## B-main review assets-main-review-03 measured the transformed faces and found
## (a) the casing visual CylinderMesh at nominal radius 0.4 m encodes 384 face
## vertices outside the disabled CylinderShape3D radius 0.4 m envelope by up to
## 5.470416716468751e-05 m and (b) all 18 cutter studs used a left-handed frame
## (det=-1), flipping every transformed face orientation and the clockwise
## volume negative. This test now checks, on the ACTUAL transformed mesh faces:
## one disabled convex shape (box/cylinder/capsule, shape-local coordinates)
## contains every triangle; every visual part has det>0; every closed individual
## mesh has directed paired edges and nonzero positive clockwise volume after
## transform (overlapping parts allowed; no union watertightness claimed); and
## negative controls (an enlarged casing and a mirrored stud) must FAIL these
## checks.
## Human contract DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
## c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.

const AssetLibrary := preload("res://world/asset_library.gd")

const TOLERANCE_M := 2e-6
const WELD_SCALE := 1000000.0
const OBSTACLE_KINDS := ["water", "hard_rock", "fault", "void", "casing"]
const DRILL_ROTATION_BOUND_RADIUS_M := 0.52
const SCENE_TRIANGLE_BUDGET := 300000
## Zero-area guard: cross-product length (twice the triangle area) at or below
## this counts as a degenerate face in the closed-solid report.
const FACE_CROSS_EPSILON_M2 := 1e-9
## Correction-03 containment slack: engine float32 noise stays far below this;
## a transformed triangle counts as contained when its best shape-local signed
## distance (max over its three vertices, min over the disabled shapes) is <= slack.
const CONTAINMENT_SLACK_M := 2e-6
## B-ASSETS-CONTAIN05 fix: the casing visual CylinderMesh encodes at this radius
## (0.0002 m inside the nominal 0.4 m). Engine snapping of CylinderMesh vertices
## to the 1e-4 m grid can move a ring vertex outward by up to sqrt(2)*5e-5 m, so
## every encoded casing vertex is bounded at <= 0.3998 + sqrt(2)*5e-5 =
## 0.39987071 m, i.e. >= 1.29e-4 m inside the disabled collision radius 0.4 m.
## The nominal 0.8 m diameter stays as the declared envelope only.
const CASING_VISUAL_RADIUS_M := 0.3998
const CASING_VISUAL_DIAMETER_M := 0.7996
const CASING_MIN_INSIDE_MARGIN_M := 0.0001

const OBSTACLE_DECLARED := {
    "water": {"size": Vector3(6.0, 4.0, 2.0), "min_ratio": Vector3(0.90, 0.999, 0.90)},
    "hard_rock": {"size": Vector3(3.0, 3.0, 3.0), "min_ratio": Vector3(0.70, 0.999, 0.70)},
    "fault": {"size": Vector3(8.0, 1.0, 6.0), "min_ratio": Vector3(0.99999, 0.99999, 0.99999)},
    "void": {"size": Vector3(4.0, 3.0, 3.0), "min_ratio": Vector3(0.99999, 0.99999, 0.99999)},
    "casing": {"size": Vector3(0.8, 0.8, 8.0), "min_ratio": Vector3(0.985, 0.985, 0.99999)},
}

## Volume provenance: water/hard_rock/void are the deterministic star-mesh volumes
## computed by the independent Python replica (double precision, divergence theorem)
## of the generator in world/obstacle_geometry.gd; fault is a closed-form box
## prism; casing is the real-engine value measured 2026-10-16 at the correction-03
## encoded visual radius 0.3998 m (the nominal 0.8 m diameter stays a
## declared-envelope value). The same values are recorded in
## simulator/assets/scene_catalog.json.
## Convention: every volume here is the explicit Godot clockwise front-face signed
## volume -sum(p0.dot(p1.cross(p2))) / 6 over the stored triangle order, positive
## for an outward-wound closed solid. The custom star meshes are index-wound
## clockwise in world/obstacle_geometry.gd (correction-02); BoxMesh and
## CylinderMesh primitives already encode clockwise front faces.
const OBSTACLE_VOLUMES := {
    "water": {"volume_m3": 23.7359, "tolerance_ratio": 0.01},
    "hard_rock": {"volume_m3": 9.8210, "tolerance_ratio": 0.015},
    "fault": {"volume_m3": 48.0, "tolerance_ratio": 0.0001},
    "void": {"volume_m3": 18.7154, "tolerance_ratio": 0.01},
    "casing": {"volume_m3": 4.0060, "tolerance_ratio": 0.005},
}

var _checks := 0
var _failures := 0

func _initialize() -> void:
    print("test_asset_contract: DeepEye B factory contract test")
    print("task=DEEPEYE-IMPLEMENTATION-20261014/v1 work=B-ASSETS-RUNTIME-CORRECTION-20261016-03-v1")
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
    _check(size.x >= 0.239 and size.y >= 0.239, "drill diameter reaches the encoded 0.239 m band")
    _check(float(measured["max_radius_about_z_m"]) <= 0.12 + TOLERANCE_M, "drill radial envelope <= 0.12 m")
    _check(float(measured["max_radius_about_z_m"]) <= 0.12 - 5e-5, "drill encoded radial margin at least 5e-5 m inside nominal 0.12 m")
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
    var shapes := _collision_shapes(drill)
    var all_shapes_disabled := true
    for shape in shapes:
        if not bool(shape["disabled"]):
            all_shapes_disabled = false
    _check(shapes.size() == 1 and String(shapes[0]["type"]) == "CapsuleShape3D", "drill transformed containment uses exactly one convex capsule shape")
    _check(all_shapes_disabled, "drill transformed containment shapes are disabled")
    var containment := _containment_report(meshes, drill, shapes, CONTAINMENT_SLACK_M)
    _check(int(containment["triangles_total"]) == _count_triangles(drill), "drill containment sampled every transformed triangle")
    _check(int(containment["triangles_violating"]) == 0, "every transformed drill triangle is inside the disabled capsule (worst=" + str(containment["worst_distance_m"]) + " m at " + str(containment["worst_mesh"]) + ")")
    for mesh_instance in meshes:
        var part := _transformed_solid_report(mesh_instance, drill)
        _check(float(part["determinant"]) > 0.0, "drill part right-handed basis det>0: " + str(mesh_instance.name) + " det=" + str(part["determinant"]))
        _check(int(part["boundary_edges"]) == 0 and int(part["degenerate_triangles"]) == 0, "drill part transformed edges paired and nondegenerate: " + str(mesh_instance.name))
        _check(float(part["volume_m3"]) > 0.0 and int(part["faces_total"]) > 0, "drill part positive clockwise volume after transform: " + str(mesh_instance.name) + " volume=" + str(part["volume_m3"]))
        _check(int(part["orientation_violations"]) == 0, "drill part transformed faces stay outward: " + str(mesh_instance.name))
    var stud := drill.get_node_or_null("Visual/CutterStud_0_0") as MeshInstance3D
    _check(stud != null, "drill cutter stud node present for the mirrored negative control")
    if stud != null:
        var control_root := Node3D.new()
        var mirrored := MeshInstance3D.new()
        mirrored.mesh = stud.mesh
        var stud_xform := _relative_transform(drill, stud)
        var mirrored_basis := stud_xform.basis
        mirrored_basis.z = -mirrored_basis.z
        mirrored.transform = Transform3D(mirrored_basis, stud_xform.origin)
        control_root.add_child(mirrored)
        var mirrored_report := _transformed_solid_report(mirrored, control_root)
        _check(float(mirrored_report["determinant"]) < 0.0, "mirrored stud negative control fails det>0 (rejected left-handed frame reproduced)")
        _check(float(mirrored_report["volume_m3"]) < 0.0, "mirrored stud negative control fails positive clockwise volume")
        _check(int(mirrored_report["orientation_violations"]) == int(mirrored_report["faces_total"]) and int(mirrored_report["faces_total"]) > 0, "mirrored stud negative control fails outward orientation on every transformed face")
        control_root.free()
    print("MEASURE asset_id=drill_pdc_v1 size=" + str(size) + " pivot_radius_m=" + str(pivot) + " max_radius_about_z_m=" + str(measured["max_radius_about_z_m"]) + " triangles=" + str(_count_triangles(drill)))
    drill.free()

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
    var visual_meshes := _visual_meshes(obstacle)
    _check(visual_meshes.size() >= 1, kind + " has at least one visual mesh")
    var topology := _closed_solid_report(visual_meshes)
    _check(int(topology["boundary_edges"]) == 0, kind + " mesh is closed (all edges paired)")
    _check(int(topology["degenerate_triangles"]) == 0, kind + " mesh has no degenerate triangles")
    _check(int(topology["degenerate_by_area"]) == 0, kind + " mesh has no zero-area faces")
    _check(int(topology["faces_clockwise_front"]) == int(topology["faces_total"]) and int(topology["faces_total"]) > 0, kind + " every face uses the Godot clockwise front-face winding (no mixed winding)")
    _check(int(topology["orientation_violations"]) == 0, kind + " every face is outward-facing under the clockwise front convention")
    for mesh_instance in visual_meshes:
        var visual_mesh: Mesh = (mesh_instance as MeshInstance3D).mesh
        var normals_report := _normal_outward_report(visual_mesh)
        _check(int(normals_report["total"]) > 0 and int(normals_report["outward"]) == int(normals_report["total"]), kind + " stored vertex normals point outward (" + str(normals_report["outward"]) + " of " + str(normals_report["total"]) + ")")
    var volume := float(topology["volume_m3"])
    _check(volume > 0.0, kind + " mesh has nonzero positive clockwise volume")
    var expected: Dictionary = OBSTACLE_VOLUMES[kind]
    var tolerance := float(expected["volume_m3"]) * float(expected["tolerance_ratio"])
    _check(absf(volume - float(expected["volume_m3"])) <= tolerance, kind + " mesh volume matches catalog provenance actual=" + str(volume))
    if visual_meshes.size() >= 1:
        var reversed := _reversed_winding_instance(visual_meshes[0])
        var negative := _closed_solid_report([reversed])
        _check(int(negative["faces_counterclockwise"]) == int(negative["faces_total"]) and int(negative["faces_clockwise_front"]) == 0, kind + " opposite-winding negative control reverses every face")
        _check(int(negative["orientation_violations"]) == int(negative["faces_total"]) and int(negative["faces_total"]) > 0, kind + " opposite-winding negative control fails outward orientation on every face")
        _check_close(float(negative["volume_m3"]), -volume, tolerance, kind + " opposite-winding negative control flips the signed volume")
        reversed.free()
    var shapes := _collision_shapes(obstacle)
    var all_shapes_disabled := true
    for shape in shapes:
        if not bool(shape["disabled"]):
            all_shapes_disabled = false
    _check(shapes.size() >= 1 and all_shapes_disabled, kind + " transformed containment uses only disabled convex shapes")
    var containment := _containment_report(visual_meshes, obstacle, shapes, CONTAINMENT_SLACK_M)
    _check(int(containment["triangles_total"]) == _count_triangles(obstacle), kind + " containment sampled every transformed triangle")
    _check(int(containment["triangles_violating"]) == 0, kind + " every transformed triangle is inside a disabled convex shape (worst=" + str(containment["worst_distance_m"]) + " m at " + str(containment["worst_mesh"]) + ")")
    for mesh_instance in visual_meshes:
        var part := _transformed_solid_report(mesh_instance, obstacle)
        _check(float(part["determinant"]) > 0.0, kind + " part right-handed basis det>0: " + str(mesh_instance.name))
        _check(int(part["boundary_edges"]) == 0 and int(part["degenerate_triangles"]) == 0, kind + " part transformed edges paired and nondegenerate: " + str(mesh_instance.name))
        _check(float(part["volume_m3"]) > 0.0 and int(part["faces_total"]) > 0, kind + " part positive clockwise volume after transform: " + str(mesh_instance.name) + " volume=" + str(part["volume_m3"]))
        _check(int(part["orientation_violations"]) == 0, kind + " part transformed faces stay outward: " + str(mesh_instance.name))
    if kind == "casing":
        _check(float(measured["max_radius_about_z_m"]) <= 0.4 - CASING_MIN_INSIDE_MARGIN_M, "casing encoded visual radius stays >= 1e-4 m inside the disabled collision radius 0.4 m actual=" + str(measured["max_radius_about_z_m"]))
        _check(float(measured["max_radius_about_z_m"]) >= 0.399, "casing encoded visual radius not collapsed actual=" + str(measured["max_radius_about_z_m"]))
        _check(size.x >= 0.799 and size.x <= CASING_VISUAL_DIAMETER_M + TOLERANCE_M, "casing encoded visual diameter is 0.7996 m (0.4 mm inside the nominal 0.8 m), actual=" + str(size.x))
        _check(shapes.size() == 1 and String(shapes[0]["type"]) == "CylinderShape3D" and absf(float(shapes[0]["radius"]) - 0.4) <= 1e-6 and absf(float(shapes[0]["height"]) - 8.0) <= 1e-6, "casing disabled collision keeps the original conservative CylinderShape radius 0.4 m, length 8 m")
        _check(is_equal_approx(CASING_VISUAL_RADIUS_M, CASING_VISUAL_DIAMETER_M * 0.5), "casing encode-radius constant matches the documented 0.7996 m diameter")
        print("MEASURE asset_id=obstacle_casing_v1_encoded max_radius_about_z_m=" + str(measured["max_radius_about_z_m"]) + " inside_collision_margin_m=" + str(0.4 - float(measured["max_radius_about_z_m"])))
        var enlarged := Node3D.new()
        var enlarged_mesh_instance := MeshInstance3D.new()
        enlarged_mesh_instance.name = "SolidMesh"
        var enlarged_cylinder := CylinderMesh.new()
        enlarged_cylinder.top_radius = 0.4005
        enlarged_cylinder.bottom_radius = 0.4005
        enlarged_cylinder.height = 8.0
        enlarged_cylinder.radial_segments = 48
        enlarged_cylinder.rings = 1
        enlarged_cylinder.cap_top = true
        enlarged_cylinder.cap_bottom = true
        enlarged_mesh_instance.mesh = enlarged_cylinder
        enlarged_mesh_instance.transform = Transform3D(Basis(Vector3.RIGHT, PI / 2.0), Vector3.ZERO)
        enlarged.add_child(enlarged_mesh_instance)
        var enlarged_shape_node := CollisionShape3D.new()
        enlarged_shape_node.name = "EnvelopeCylinder"
        var enlarged_shape := CylinderShape3D.new()
        enlarged_shape.radius = 0.4
        enlarged_shape.height = 8.0
        enlarged_shape_node.shape = enlarged_shape
        enlarged_shape_node.disabled = true
        enlarged_shape_node.transform = Transform3D(Basis(Vector3.RIGHT, PI / 2.0), Vector3.ZERO)
        enlarged.add_child(enlarged_shape_node)
        var enlarged_shapes := _collision_shapes(enlarged)
        var enlarged_containment := _containment_report([enlarged_mesh_instance], enlarged, enlarged_shapes, CONTAINMENT_SLACK_M)
        _check(int(enlarged_containment["triangles_violating"]) > 0, "enlarged casing negative control is detected by containment (violations=" + str(enlarged_containment["triangles_violating"]) + ")")
        _check(float(enlarged_containment["worst_distance_m"]) > CONTAINMENT_SLACK_M, "enlarged casing negative control worst distance exceeds the slack")
        enlarged.free()
    print("MEASURE asset_id=obstacle_" + kind + "_v1 size=" + str(size) + " volume_m3=" + str(volume) + " pivot_radius_m=" + str(measured["pivot_bound_radius_m"]) + " triangles=" + str(_count_triangles(obstacle)))
    obstacle.free()

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
        var mesh: Mesh = mesh_instance.mesh
        if mesh == null:
            _check(false, "frame edge has mesh: " + str(mesh_instance.name))
            continue
        _check(_count_mesh_triangles(mesh) == 12, "frame edge is a closed box prism (12 triangles): " + str(mesh_instance.name))
        var aabb: AABB = mesh.get_aabb()
        var long_extent := maxf(aabb.size.x, maxf(aabb.size.y, aabb.size.z))
        var short_extent := minf(aabb.size.x, minf(aabb.size.y, aabb.size.z))
        _check_close(long_extent, 30.0, 1e-4, "frame edge full length 30 m: " + str(mesh_instance.name))
        _check(short_extent <= 0.13, "frame edge cross-section thin: " + str(mesh_instance.name))
    var collision := frame.get_node_or_null("Collision")
    _check(collision != null and collision is StaticBody3D, "frame collision child is StaticBody3D")
    if collision != null:
        _check(collision.get_child_count() == 12, "frame collision envelope has 12 edge shapes")
    _check(int(measured["mesh_count"]) == 12, "frame visual node count is exactly 12")
    var shapes := _collision_shapes(frame)
    var all_shapes_disabled := true
    for shape in shapes:
        if not bool(shape["disabled"]):
            all_shapes_disabled = false
    _check(shapes.size() == 12 and all_shapes_disabled, "frame transformed containment uses exactly 12 disabled box shapes")
    var containment := _containment_report(meshes, frame, shapes, CONTAINMENT_SLACK_M)
    _check(int(containment["triangles_total"]) == _count_triangles(frame), "frame containment sampled every transformed triangle")
    _check(int(containment["triangles_violating"]) == 0, "every transformed frame triangle is inside its disabled box shape (worst=" + str(containment["worst_distance_m"]) + " m)")
    for mesh_instance in meshes:
        var part := _transformed_solid_report(mesh_instance, frame)
        _check(float(part["determinant"]) > 0.0, "frame edge right-handed basis det>0: " + str(mesh_instance.name))
        _check(int(part["boundary_edges"]) == 0 and int(part["degenerate_triangles"]) == 0, "frame edge transformed edges paired and nondegenerate: " + str(mesh_instance.name))
        _check(float(part["volume_m3"]) > 0.0 and int(part["faces_total"]) > 0, "frame edge positive clockwise volume after transform: " + str(mesh_instance.name) + " volume=" + str(part["volume_m3"]))
        _check(int(part["orientation_violations"]) == 0, "frame edge transformed faces stay outward: " + str(mesh_instance.name))
    print("MEASURE asset_id=frame_workspace_v1 size=" + str(measured["size"]) + " pivot_radius_m=" + str(measured["pivot_bound_radius_m"]) + " triangles=" + str(_count_triangles(frame)))
    frame.free()

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

## Closed-solid report in mesh-local space. Every obstacle mesh here is
## origin-centred and star-shaped about its own origin, so under Godot's
## clockwise front-face convention a correctly wound outward face has its
## geometric cross product (p1 - p0) x (p2 - p0) pointing inward (dot with the
## centroid sum < 0). volume_m3 is the explicit clockwise signed volume
## -sum(p0.dot(p1.cross(p2))) / 6: positive for an outward closed solid.
## volume_ccw_m3 keeps the raw mathematical counter-clockwise accumulation for
## provenance. boundary_edges and degenerate_triangles are unchanged checks;
## degenerate_by_area is an independent zero-area guard on the cross product.
func _closed_solid_report(mesh_instances: Array) -> Dictionary:
    var boundary_edges := 0
    var degenerate := 0
    var degenerate_by_area := 0
    var faces_clockwise := 0
    var faces_counterclockwise := 0
    var faces_total := 0
    var orientation_violations := 0
    var volume_ccw := 0.0
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
            var cross := (p1 - p0).cross(p2 - p0)
            if cross.length() <= FACE_CROSS_EPSILON_M2:
                degenerate_by_area += 1
                continue
            faces_total += 1
            var face_ccw_volume := p0.dot(p1.cross(p2)) / 6.0
            volume_ccw += face_ccw_volume
            if face_ccw_volume > 0.0:
                faces_counterclockwise += 1
            else:
                faces_clockwise += 1
            if cross.dot(p0 + p1 + p2) >= 0.0:
                orientation_violations += 1
        for key in edges.keys():
            var entry: Array = edges[key]
            if int(entry[0]) != 2 or int(entry[1]) != 0:
                boundary_edges += 1
    return {
        "boundary_edges": boundary_edges,
        "degenerate_triangles": degenerate,
        "degenerate_by_area": degenerate_by_area,
        "faces_total": faces_total,
        "faces_clockwise_front": faces_clockwise,
        "faces_counterclockwise": faces_counterclockwise,
        "orientation_violations": orientation_violations,
        "volume_ccw_m3": volume_ccw,
        "volume_m3": -volume_ccw,
    }

func _reversed_winding_instance(source_mesh_instance: MeshInstance3D) -> MeshInstance3D:
    var source: Mesh = source_mesh_instance.mesh
    var faces := source.get_faces()
    var vertices := PackedVector3Array()
    vertices.resize(faces.size())
    for face_index in range(0, faces.size(), 3):
        vertices[face_index] = faces[face_index]
        vertices[face_index + 1] = faces[face_index + 2]
        vertices[face_index + 2] = faces[face_index + 1]
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    var instance := MeshInstance3D.new()
    instance.mesh = mesh
    return instance

func _normal_outward_report(mesh: Mesh) -> Dictionary:
    var arrays := mesh.surface_get_arrays(0)
    var normals = arrays[Mesh.ARRAY_NORMAL]
    var vertices = arrays[Mesh.ARRAY_VERTEX]
    if not (normals is PackedVector3Array) or not (vertices is PackedVector3Array):
        return {"total": 0, "outward": 0}
    var normal_array: PackedVector3Array = normals
    var vertex_array: PackedVector3Array = vertices
    var total := mini(normal_array.size(), vertex_array.size())
    var outward := 0
    for index in total:
        if normal_array[index].dot(vertex_array[index]) > 0.0:
            outward += 1
    return {"total": total, "outward": outward}


## Correction-03 transformed-face checks (B-ASSETS-CONTAIN05 / B-ASSETS-HAND06).
## Shape-local signed distance for the disabled convex presentation shapes,
## matching the B-main independent review math: Godot box distance is the max
## per-axis half-extent excess; capsule and cylinder axes are local +Y. Negative
## means inside. Non-convex or unknown shape types return INF so they can never
## silently satisfy containment.
func _shape_distance(point_asset_space: Vector3, shape_info: Dictionary) -> float:
    var xform: Transform3D = shape_info["transform"]
    var local: Vector3 = xform.affine_inverse() * point_asset_space
    var shape_type := String(shape_info["type"])
    if shape_type == "BoxShape3D":
        var size: Vector3 = shape_info["size"]
        return maxf(absf(local.x) - size.x * 0.5, maxf(absf(local.y) - size.y * 0.5, absf(local.z) - size.z * 0.5))
    var radial := sqrt(local.x * local.x + local.z * local.z)
    if shape_type == "CylinderShape3D":
        return maxf(radial - float(shape_info["radius"]), absf(local.y) - float(shape_info["height"]) * 0.5)
    if shape_type == "CapsuleShape3D":
        var radius := float(shape_info["radius"])
        var mid := maxf(absf(local.y) - (float(shape_info["height"]) * 0.5 - radius), 0.0)
        return sqrt(radial * radial + mid * mid) - radius
    return INF

func _collision_shapes(asset: Node3D) -> Array:
    var shapes := []
    for node in asset.find_children("*", "CollisionShape3D", true, false):
        var shape_node := node as CollisionShape3D
        var shape := shape_node.shape
        var info := {
            "path": str(asset.get_path_to(shape_node)),
            "transform": _relative_transform(asset, shape_node),
            "disabled": shape_node.disabled,
        }
        if shape is BoxShape3D:
            info["type"] = "BoxShape3D"
            info["size"] = shape.size
        elif shape is CapsuleShape3D:
            info["type"] = "CapsuleShape3D"
            info["radius"] = shape.radius
            info["height"] = shape.height
        elif shape is CylinderShape3D:
            info["type"] = "CylinderShape3D"
            info["radius"] = shape.radius
            info["height"] = shape.height
        else:
            info["type"] = "unsupported"
        shapes.append(info)
    return shapes

## Convexity means a triangle is contained in a convex shape iff all three
## vertices are. Every transformed triangle takes the best (minimum) over shapes
## of the worst (maximum over its vertices) signed distance; above the slack it
## counts as a containment violation.
func _containment_report(mesh_instances: Array, asset: Node3D, shapes: Array, slack: float) -> Dictionary:
    var triangles_total := 0
    var triangles_violating := 0
    var worst := -INF
    var worst_mesh := ""
    var worst_point := Vector3.ZERO
    for mesh_instance in mesh_instances:
        var mesh: Mesh = (mesh_instance as MeshInstance3D).mesh
        if mesh == null:
            continue
        var xform := _relative_transform(asset, mesh_instance)
        var faces := mesh.get_faces()
        for face_index in range(0, faces.size(), 3):
            var p0: Vector3 = xform * faces[face_index]
            var p1: Vector3 = xform * faces[face_index + 1]
            var p2: Vector3 = xform * faces[face_index + 2]
            var best := INF
            var best_point := p0
            for shape in shapes:
                var d0 := _shape_distance(p0, shape)
                var d1 := _shape_distance(p1, shape)
                var d2 := _shape_distance(p2, shape)
                var seated: float = maxf(d0, maxf(d1, d2))
                if seated < best:
                    best = seated
                    best_point = p0
                    if d1 >= d0 and d1 >= d2:
                        best_point = p1
                    elif d2 >= d0 and d2 >= d1:
                        best_point = p2
            triangles_total += 1
            if best > worst:
                worst = best
                worst_mesh = str(mesh_instance.name)
                worst_point = best_point
            if best > slack:
                triangles_violating += 1
    return {
        "triangles_total": triangles_total,
        "triangles_violating": triangles_violating,
        "worst_distance_m": worst,
        "worst_mesh": worst_mesh,
        "worst_point": worst_point,
        "shape_count": shapes.size(),
    }

## Closed-solid report for ONE mesh instance AFTER its transform relative to the
## asset root. Under the explicit Godot clockwise front-face convention a solid
## wound for the engine has a positive -sum(p0.dot(p1.cross(p2)))/6 volume and
## every directed edge exactly paired; a left-handed (det<0) transform mirrors
## the mesh and flips both. Orientation is tested against the mesh-local origin
## (every factory mesh is star-shaped about it), so cross points inward for a
## correct outward face (dot with the centroid offset < 0). Overlapping parts are
## allowed; no union watertightness is claimed.
func _transformed_solid_report(mesh_instance: MeshInstance3D, asset: Node3D) -> Dictionary:
    var report := {
        "boundary_edges": 0,
        "degenerate_triangles": 0,
        "faces_total": 0,
        "faces_clockwise_front": 0,
        "faces_counterclockwise": 0,
        "orientation_violations": 0,
        "volume_ccw_m3": 0.0,
        "volume_m3": 0.0,
        "determinant": 0.0,
    }
    var mesh: Mesh = mesh_instance.mesh
    if mesh == null:
        return report
    var xform := _relative_transform(asset, mesh_instance)
    report["determinant"] = xform.basis.determinant()
    var center: Vector3 = xform.origin
    var faces := mesh.get_faces()
    var welded := {}
    var edges := {}
    var volume_ccw := 0.0
    for face_index in range(0, faces.size(), 3):
        var p0: Vector3 = xform * faces[face_index]
        var p1: Vector3 = xform * faces[face_index + 1]
        var p2: Vector3 = xform * faces[face_index + 2]
        var a := _weld_id(welded, p0)
        var b := _weld_id(welded, p1)
        var c := _weld_id(welded, p2)
        if a == b or b == c or c == a:
            report["degenerate_triangles"] = int(report["degenerate_triangles"]) + 1
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
        var face_ccw_volume := p0.dot(p1.cross(p2)) / 6.0
        volume_ccw += face_ccw_volume
        report["faces_total"] = int(report["faces_total"]) + 1
        if face_ccw_volume > 0.0:
            report["faces_counterclockwise"] = int(report["faces_counterclockwise"]) + 1
        else:
            report["faces_clockwise_front"] = int(report["faces_clockwise_front"]) + 1
        var cross := (p1 - p0).cross(p2 - p0)
        if cross.dot(p0 + p1 + p2 - 3.0 * center) >= 0.0:
            report["orientation_violations"] = int(report["orientation_violations"]) + 1
    for key in edges.keys():
        var entry: Array = edges[key]
        if int(entry[0]) != 2 or int(entry[1]) != 0:
            report["boundary_edges"] = int(report["boundary_edges"]) + 1
    report["volume_ccw_m3"] = volume_ccw
    report["volume_m3"] = -volume_ccw
    return report

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
    _check(total_meshes == 70, "30-instance probe has exactly 70 visual meshes (actual=" + str(total_meshes) + ")")
    _check(total_triangles == 43904, "30-instance probe has exactly 43904 triangles (actual=" + str(total_triangles) + ")")
    _check(total_triangles <= SCENE_TRIANGLE_BUDGET, "asset-only triangles within 300k scene budget: " + str(total_triangles))
    _check(holder.get_child_count() == 32, "probe holds 30 obstacles + drill + frame")
    print("MEASURE thirty_instance_probe objects=32 meshes=" + str(total_meshes) + " triangles=" + str(total_triangles))
    holder.free()