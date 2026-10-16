class_name DeepEyeDrillGeometry
extends Object

## DeepEye B procedural PDC drill geometry (editable source; no external assets).
## Human contract DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
## c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
## Resource contract: competition/deepeye/docs/resource_contract.json (A-frozen).
## Units metres; +Z forward, +Y up; origin at rigid-body centre (full-length AABB centre).
## Outer envelope: diameter 0.24 m, rigid length 0.80 m, z in [-0.40, 0.40];
## every blade and body part is computed inside it. Actual bounds and the real
## pivot radius are measured by DeepEyeAssetLibrary from transformed vertices.
## Encoded head margin (correction-02): the engine snaps CylinderMesh primitive
## vertices to a 1e-4 m grid before float32 storage, so a nominal 0.12 m ring
## encodes its 45-degree vertices at (0.0849, 0.0849), radius
## 0.12006673558429641 m measured on 4.7.2-stable. The cutter cone base is
## encoded at HEAD_BASE_ENCODE_RADIUS_M = 0.1198 m, bounding every snapped
## transformed vertex at <= 0.1198 + sqrt(2) * 5e-5 = 0.119871 m, while the
## declared envelope keeps the nominal 0.24 m diameter and the disabled capsule
## collision envelope keeps radius 0.12 m.
## Presentation only: the Collision child is a disabled StaticBody3D envelope
## (collision_layer 0, collision_mask 0); it grants no authority or truth API.

const ENVELOPE_MAX_RADIUS_M := 0.12
const ENVELOPE_HALF_LENGTH_M := 0.40
const ENVELOPE_CAPSULE_HEIGHT_M := 1.04

const HEAD_TIP_RADIUS_M := 0.02
const HEAD_BASE_RADIUS_M := 0.12
const HEAD_BASE_ENCODE_RADIUS_M := 0.1198
const HEAD_LENGTH_M := 0.25
const HEAD_BASE_Z_M := 0.15

const BLADE_COUNT := 6
const BLADE_CENTER_Z_M := 0.24
const BLADE_THICKNESS_M := 0.024
const BLADE_WIDTH_M := 0.022
const BLADE_LENGTH_M := 0.12
const BLADE_EMBED_M := 0.002
const CUTTER_STUD_RADIUS_M := 0.008
const CUTTER_STUD_HEIGHT_M := 0.010

static func build() -> Node3D:
    var root := Node3D.new()
    root.name = "DrillPDC"
    var visual := Node3D.new()
    visual.name = "Visual"
    root.add_child(visual)
    _build_visual(visual)
    root.add_child(_build_collision())
    root.set_meta(&"declared_envelope", {
        "bounds_min": Vector3(-HEAD_BASE_RADIUS_M, -HEAD_BASE_RADIUS_M, -ENVELOPE_HALF_LENGTH_M),
        "bounds_max": Vector3(HEAD_BASE_RADIUS_M, HEAD_BASE_RADIUS_M, ENVELOPE_HALF_LENGTH_M),
        "max_radius_about_z_m": HEAD_BASE_RADIUS_M,
        "z_range_m": [-ENVELOPE_HALF_LENGTH_M, ENVELOPE_HALF_LENGTH_M],
        "note": "drill outer envelope diameter 0.24 m, rigid length 0.80 m; encoded head base 0.0002 m inside the nominal radius for engine vertex snapping (correction-02)",
    })
    return root

static func _build_visual(visual: Node3D) -> void:
    var collar := _make_cylinder(0.060, 0.16, 32, 1, _material_collar())
    collar.name = "Collar"
    collar.transform = _z_axis_transform(Vector3(0.0, 0.0, -0.32))
    visual.add_child(collar)
    var joint := _make_cylinder(0.074, 0.10, 32, 1, _material_joint())
    joint.name = "Joint"
    joint.transform = _z_axis_transform(Vector3(0.0, 0.0, -0.19))
    visual.add_child(joint)
    var body := _make_cylinder(0.090, 0.34, 64, 2, _material_matrix())
    body.name = "BodyMatrix"
    body.transform = _z_axis_transform(Vector3(0.0, 0.0, -0.02))
    visual.add_child(body)
    var head := _make_cone(HEAD_TIP_RADIUS_M, HEAD_BASE_ENCODE_RADIUS_M, HEAD_LENGTH_M, 64, _material_matrix())
    head.name = "HeadPDC"
    head.transform = _z_axis_transform(Vector3(0.0, 0.0, HEAD_BASE_Z_M + HEAD_LENGTH_M * 0.5))
    visual.add_child(head)
    _build_blades(visual)

static func _build_blades(visual: Node3D) -> void:
    var slope := (HEAD_BASE_ENCODE_RADIUS_M - HEAD_TIP_RADIUS_M) / HEAD_LENGTH_M
    var alpha := atan(slope)
    var center_radius := _head_radius_at(BLADE_CENTER_Z_M)
    var blade_material := _material_pdc_blade()
    var stud_material := _material_pdc_stud()
    var stud_offsets := [-0.02, 0.0, 0.04]
    var blade_center := Vector3(0.0, 0.0, BLADE_CENTER_Z_M)
    for i in BLADE_COUNT:
        var phi := TAU * float(i) / float(BLADE_COUNT)
        var radial_dir := Vector3(cos(phi), sin(phi), 0.0)
        var tangential_dir := Vector3(-sin(phi), cos(phi), 0.0)
        var along_dir := (-sin(alpha) * radial_dir + cos(alpha) * Vector3(0.0, 0.0, 1.0)).normalized()
        var surface_normal := (cos(alpha) * radial_dir + sin(alpha) * Vector3(0.0, 0.0, 1.0)).normalized()
        var blade_basis := Basis()
        blade_basis.x = surface_normal
        blade_basis.y = tangential_dir
        blade_basis.z = along_dir
        var blade := MeshInstance3D.new()
        var blade_box := BoxMesh.new()
        blade_box.size = Vector3(BLADE_THICKNESS_M, BLADE_WIDTH_M, BLADE_LENGTH_M)
        blade.mesh = blade_box
        blade.material_override = blade_material
        blade.name = "Blade" + str(i)
        blade.transform = Transform3D(blade_basis, radial_dir * center_radius + blade_center)
        visual.add_child(blade)
        for s_index in stud_offsets.size():
            var offset_along: float = stud_offsets[s_index]
            var stud := _make_cylinder(CUTTER_STUD_RADIUS_M, CUTTER_STUD_HEIGHT_M, 8, 1, stud_material)
            stud.name = "CutterStud_" + str(i) + "_" + str(s_index)
            var stud_basis := Basis()
            stud_basis.x = tangential_dir
            stud_basis.y = surface_normal
            stud_basis.z = along_dir
            var stud_origin := radial_dir * center_radius + blade_center + surface_normal * (BLADE_THICKNESS_M * 0.5 - BLADE_EMBED_M) + along_dir * offset_along
            stud.transform = Transform3D(stud_basis, stud_origin)
            visual.add_child(stud)

static func _build_collision() -> StaticBody3D:
    var body := StaticBody3D.new()
    body.name = "Collision"
    body.collision_layer = 0
    body.collision_mask = 0
    body.set_meta(&"presentation_envelope", true)
    body.set_meta(&"disabled_in_viewer", true)
    var shape := CapsuleShape3D.new()
    shape.radius = ENVELOPE_MAX_RADIUS_M
    shape.height = ENVELOPE_CAPSULE_HEIGHT_M
    var shape_node := CollisionShape3D.new()
    shape_node.name = "EnvelopeCapsule"
    shape_node.shape = shape
    shape_node.disabled = true
    shape_node.transform = _z_axis_transform(Vector3.ZERO)
    body.add_child(shape_node)
    return body

static func _head_radius_at(z: float) -> float:
    var slope := (HEAD_BASE_ENCODE_RADIUS_M - HEAD_TIP_RADIUS_M) / HEAD_LENGTH_M
    return HEAD_BASE_ENCODE_RADIUS_M - (z - HEAD_BASE_Z_M) * slope

static func _z_axis_transform(origin: Vector3) -> Transform3D:
    return Transform3D(Basis(Vector3.RIGHT, PI / 2.0), origin)

static func _make_cylinder(radius: float, height: float, radial_segments: int, rings: int, material: Material) -> MeshInstance3D:
    var mesh := CylinderMesh.new()
    mesh.top_radius = radius
    mesh.bottom_radius = radius
    mesh.height = height
    mesh.radial_segments = radial_segments
    mesh.rings = rings
    mesh.cap_top = true
    mesh.cap_bottom = true
    var instance := MeshInstance3D.new()
    instance.mesh = mesh
    instance.material_override = material
    return instance

static func _make_cone(top_radius: float, bottom_radius: float, height: float, radial_segments: int, material: Material) -> MeshInstance3D:
    var mesh := CylinderMesh.new()
    mesh.top_radius = top_radius
    mesh.bottom_radius = bottom_radius
    mesh.height = height
    mesh.radial_segments = radial_segments
    mesh.rings = 1
    mesh.cap_top = true
    mesh.cap_bottom = true
    var instance := MeshInstance3D.new()
    instance.mesh = mesh
    instance.material_override = material
    return instance

static func _standard_material(albedo: Color, metallic: float, roughness: float) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = albedo
    material.metallic = metallic
    material.roughness = roughness
    return material

static func _material_collar() -> StandardMaterial3D:
    return _standard_material(Color(0.34, 0.35, 0.37), 0.75, 0.60)

static func _material_joint() -> StandardMaterial3D:
    return _standard_material(Color(0.55, 0.46, 0.36), 0.90, 0.35)

static func _material_matrix() -> StandardMaterial3D:
    return _standard_material(Color(0.52, 0.53, 0.55), 0.85, 0.42)

static func _material_pdc_blade() -> StandardMaterial3D:
    return _standard_material(Color(0.07, 0.07, 0.08), 0.35, 0.14)

static func _material_pdc_stud() -> StandardMaterial3D:
    return _standard_material(Color(0.12, 0.12, 0.14), 0.60, 0.06)