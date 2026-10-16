class_name DeepEyeAssetLibrary
extends RefCounted

## DeepEye B asset factory for the frozen resource contract
## (competition/deepeye/docs/resource_contract.json, A-owned boundary; the A
## interface file docs/interface.json and this contract are read-only here).
## Human contract DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
## c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
## Static factory only; returned assets are presentation nodes:
##   static func create_drill() -> Node3D
##   static func create_obstacle(kind: String) -> Node3D
##   static func create_frame() -> Node3D
## Metadata keys asset_contract_version, source_license, geometry_bounds_m and
## pivot_bound_radius_m are computed from the actual transformed mesh vertices
## (no guessed or stamped radius). No authority or truth API is exposed; A
## world_authority keeps authoritative collision/integration, free camera,
## editor and blue/red gate decisions (equal 0.30 m gates, no preset route).

const DrillGeometry := preload("res://world/drill_geometry.gd")
const ObstacleGeometry := preload("res://world/obstacle_geometry.gd")
const FrameGeometry := preload("res://world/frame_geometry.gd")

const ASSET_CONTRACT_VERSION := 1
const SOURCE_LICENSE := "procedural-original:CarlandFPGA-DEEPEYE-B;see res://assets/LICENSES.md"
const MEASUREMENT_TOLERANCE_M := 2e-6
const KIND_IDS: PackedStringArray = ["water", "hard_rock", "fault", "void", "casing"]

static func create_drill() -> Node3D:
    var root: Node3D = DrillGeometry.build()
    _finalize_asset(root, "drill_pdc_v1", "res://world/drill_geometry.gd")
    return root

static func create_obstacle(kind: String) -> Node3D:
    var root: Node3D = ObstacleGeometry.build(kind)
    if root == null:
        return null
    _finalize_asset(root, "obstacle_" + kind + "_v1", "res://world/obstacle_geometry.gd")
    return root

static func create_frame() -> Node3D:
    var root: Node3D = FrameGeometry.build()
    _finalize_asset(root, "frame_workspace_v1", "res://world/frame_geometry.gd")
    return root

static func measure_visual(asset: Node3D) -> Dictionary:
    var minimum := Vector3(INF, INF, INF)
    var maximum := Vector3(-INF, -INF, -INF)
    var pivot_radius := 0.0
    var axis_radius := 0.0
    var vertex_count := 0
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
            var radial := sqrt(transformed.x * transformed.x + transformed.y * transformed.y)
            axis_radius = maxf(axis_radius, radial)
            pivot_radius = maxf(pivot_radius, transformed.length())
            vertex_count += 1
    return {
        "min": minimum,
        "max": maximum,
        "size": maximum - minimum,
        "center": (minimum + maximum) * 0.5,
        "pivot_bound_radius_m": pivot_radius,
        "max_radius_about_z_m": axis_radius,
        "vertex_count": vertex_count,
        "mesh_count": mesh_count,
    }

static func _relative_transform(asset: Node3D, node: Node3D) -> Transform3D:
    var xform := node.transform
    var parent := node.get_parent()
    while parent != null and parent != asset:
        if parent is Node3D:
            xform = (parent as Node3D).transform * xform
        parent = parent.get_parent()
    return xform

static func _finalize_asset(root: Node3D, asset_id: String, geometry_script_path: String) -> void:
    var measured := measure_visual(root)
    root.set_meta(&"asset_id", asset_id)
    root.set_meta(&"asset_contract_version", ASSET_CONTRACT_VERSION)
    root.set_meta(&"source_license", SOURCE_LICENSE)
    root.set_meta(&"geometry_bounds_m", {
        "min": measured["min"],
        "max": measured["max"],
        "size": measured["size"],
    })
    root.set_meta(&"pivot_bound_radius_m", measured["pivot_bound_radius_m"])
    root.set_meta(&"procedural_source", geometry_script_path + ";deterministic-procedural-mesh-v1")
    root.set_meta(&"measured_vertex_count", measured["vertex_count"])
    var declared: Dictionary = root.get_meta(&"declared_envelope", {})
    var envelope_ok := _envelope_contains(declared, measured)
    root.set_meta(&"envelope_ok", envelope_ok)
    if not envelope_ok:
        push_error("DeepEyeAssetLibrary: " + asset_id + " exceeds its declared envelope: " + str(measured))

static func _envelope_contains(declared: Dictionary, measured: Dictionary) -> bool:
    if declared.is_empty():
        return true
    var tolerance := MEASUREMENT_TOLERANCE_M
    var bounds_min: Vector3 = declared.get("bounds_min", measured["min"])
    var bounds_max: Vector3 = declared.get("bounds_max", measured["max"])
    var actual_min: Vector3 = measured["min"]
    var actual_max: Vector3 = measured["max"]
    if actual_min.x < bounds_min.x - tolerance or actual_min.y < bounds_min.y - tolerance or actual_min.z < bounds_min.z - tolerance:
        return false
    if actual_max.x > bounds_max.x + tolerance or actual_max.y > bounds_max.y + tolerance or actual_max.z > bounds_max.z + tolerance:
        return false
    if declared.has("max_radius_about_z_m"):
        if float(measured["max_radius_about_z_m"]) > float(declared["max_radius_about_z_m"]) + tolerance:
            return false
    return true