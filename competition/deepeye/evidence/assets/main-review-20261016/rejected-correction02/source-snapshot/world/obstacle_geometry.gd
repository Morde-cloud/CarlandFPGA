class_name DeepEyeObstacleGeometry
extends Object

## DeepEye B geological obstacle kinds as closed solid procedural meshes.
## Human contract DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
## c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
## Resource contract: kind ids "water", "hard_rock", "fault", "void", "casing";
## children "Visual" and "Collision"; the collision presentation envelope is
## disabled in the viewer and is never authoritative or truth-visible.
## Units metres; origin at rigid-body centre. Water and hard_rock are required.
## Declared envelopes: water 6x4x2, hard_rock 3x3x3, fault 8x1x6 (thin plate,
## inclination is placement), void 4x3x3, casing diameter 0.8 x length 8 along +Z.
## Volumes with explicit provenance: simulator/assets/scene_catalog.json.
## The star-mesh generator is deterministic and keeps every vertex at or inside
## its declared envelope (undulation is inward only, tapered to exact poles).
## Triangle indices use Godot's clockwise front-face convention (ArrayMesh docs);
## vertex normals remain the outward ellipsoid-gradient normals and are unchanged
## by the winding. A solid wound for the engine therefore has a negative signed
## volume under the mathematical counter-clockwise convention, i.e. a positive
## volume under the explicit clockwise convention used by the contract test
## (correction-02 fixed the previous counter-clockwise index order).

const KINDS: PackedStringArray = ["water", "hard_rock", "fault", "void", "casing"]

const RADIAL_SEGMENTS := 48
const RINGS := 24

static func build(kind: String) -> Node3D:
    match kind:
        "water":
            return _build_water()
        "hard_rock":
            return _build_hard_rock()
        "fault":
            return _build_fault()
        "void":
            return _build_void()
        "casing":
            return _build_casing()
        _:
            push_error("DeepEyeObstacleGeometry: unknown obstacle kind '" + kind + "'; valid kinds: " + ", ".join(KINDS))
            return null

static func _build_water() -> Node3D:
    var terms := [
        {"m": 3.0, "n": 2.0, "phase": 0.7, "weight": 1.0},
        {"m": 2.0, "n": 3.0, "phase": 2.1, "weight": 0.6},
    ]
    var visual := _wrap_solid_mesh(Vector3(3.0, 2.0, 1.0), 0.05, terms, _material_water())
    return _wrap("ObstacleWater", visual, _make_collision_box(Vector3(6.0, 4.0, 2.0)), Vector3(3.0, 2.0, 1.0))

static func _build_hard_rock() -> Node3D:
    var terms := [
        {"m": 3.0, "n": 2.0, "phase": 0.4, "weight": 1.0},
        {"m": 5.0, "n": 3.0, "phase": 2.2, "weight": 0.7},
        {"m": 2.0, "n": 5.0, "phase": 4.1, "weight": 0.5},
        {"m": 7.0, "n": 1.0, "phase": 1.3, "weight": 0.3},
    ]
    var visual := _wrap_solid_mesh(Vector3(1.5, 1.5, 1.5), 0.35, terms, _material_hard_rock())
    return _wrap("ObstacleHardRock", visual, _make_collision_box(Vector3(3.0, 3.0, 3.0)), Vector3(1.5, 1.5, 1.5))

static func _build_void() -> Node3D:
    var visual := _wrap_solid_mesh(Vector3(2.0, 1.5, 1.5), 0.0, [], _material_void())
    return _wrap("ObstacleVoid", visual, _make_collision_box(Vector3(4.0, 3.0, 3.0)), Vector3(2.0, 1.5, 1.5))

static func _build_fault() -> Node3D:
    var visual := Node3D.new()
    var instance := MeshInstance3D.new()
    instance.name = "SolidMesh"
    var box := BoxMesh.new()
    box.size = Vector3(8.0, 1.0, 6.0)
    instance.mesh = box
    instance.material_override = _material_fault()
    visual.add_child(instance)
    return _wrap("ObstacleFault", visual, _make_collision_box(Vector3(8.0, 1.0, 6.0)), Vector3(4.0, 0.5, 3.0))

static func _build_casing() -> Node3D:
    var visual := Node3D.new()
    var instance := MeshInstance3D.new()
    instance.name = "SolidMesh"
    var mesh := CylinderMesh.new()
    mesh.top_radius = 0.4
    mesh.bottom_radius = 0.4
    mesh.height = 8.0
    mesh.radial_segments = RADIAL_SEGMENTS
    mesh.rings = 1
    mesh.cap_top = true
    mesh.cap_bottom = true
    instance.mesh = mesh
    instance.material_override = _material_casing()
    instance.transform = Transform3D(Basis(Vector3.RIGHT, PI / 2.0), Vector3.ZERO)
    visual.add_child(instance)
    return _wrap("ObstacleCasing", visual, _make_collision_cylinder(0.4, 8.0), Vector3(0.4, 0.4, 4.0))

static func _wrap_solid_mesh(semi: Vector3, lumpiness: float, terms: Array, material: Material) -> Node3D:
    var visual := Node3D.new()
    var instance := MeshInstance3D.new()
    instance.name = "SolidMesh"
    instance.mesh = _generate_star_mesh(semi, RADIAL_SEGMENTS, RINGS, lumpiness, terms)
    instance.material_override = material
    visual.add_child(instance)
    return visual

static func _wrap(node_name: String, visual: Node3D, collision: StaticBody3D, half_extents: Vector3) -> Node3D:
    var root := Node3D.new()
    root.name = node_name
    visual.name = "Visual"
    collision.name = "Collision"
    root.add_child(visual)
    root.add_child(collision)
    root.set_meta(&"declared_envelope", {
        "bounds_min": -half_extents,
        "bounds_max": half_extents,
        "note": "closed solid presentation mesh; authoritative collision and occupancy belong to A world_authority",
    })
    return root

static func _generate_star_mesh(semi: Vector3, radial_segments: int, rings: int, lumpiness: float, terms: Array) -> ArrayMesh:
    var vertex_array := PackedVector3Array()
    var normal_array := PackedVector3Array()
    var index_array := PackedInt32Array()
    vertex_array.push_back(Vector3(0.0, semi.y, 0.0))
    normal_array.push_back(Vector3(0.0, 1.0, 0.0))
    for i in range(1, rings):
        var theta := PI * float(i) / float(rings)
        for j in radial_segments:
            var phi := TAU * float(j) / float(radial_segments)
            var unit := Vector3(sin(theta) * cos(phi), cos(theta), sin(theta) * sin(phi))
            var factor := _radial_factor(unit, lumpiness, terms)
            var point := Vector3(unit.x * semi.x * factor, unit.y * semi.y * factor, unit.z * semi.z * factor)
            vertex_array.push_back(point)
            normal_array.push_back(_star_normal(point, semi))
    var bottom_index := vertex_array.size()
    vertex_array.push_back(Vector3(0.0, -semi.y, 0.0))
    normal_array.push_back(Vector3(0.0, -1.0, 0.0))
    for j in radial_segments:
        var jn_top := (j + 1) % radial_segments
        index_array.push_back(0)
        index_array.push_back(1 + j)
        index_array.push_back(1 + jn_top)
    for i in range(1, rings - 1):
        var ring_upper := 1 + (i - 1) * radial_segments
        var ring_lower := 1 + i * radial_segments
        for j in radial_segments:
            var jn := (j + 1) % radial_segments
            index_array.push_back(ring_upper + j)
            index_array.push_back(ring_lower + j)
            index_array.push_back(ring_lower + jn)
            index_array.push_back(ring_upper + j)
            index_array.push_back(ring_lower + jn)
            index_array.push_back(ring_upper + jn)
    var ring_last := 1 + (rings - 2) * radial_segments
    for j in radial_segments:
        var jn_bottom := (j + 1) % radial_segments
        index_array.push_back(bottom_index)
        index_array.push_back(ring_last + jn_bottom)
        index_array.push_back(ring_last + j)
    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertex_array
    arrays[Mesh.ARRAY_NORMAL] = normal_array
    arrays[Mesh.ARRAY_INDEX] = index_array
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
    return mesh

static func _radial_factor(unit: Vector3, lumpiness: float, terms: Array) -> float:
    if lumpiness <= 0.0 or terms.is_empty():
        return 1.0
    var theta := acos(clampf(unit.y, -1.0, 1.0))
    var phi := atan2(unit.z, unit.x)
    var value := 0.0
    var weight_sum := 0.0
    for term in terms:
        var m: float = term["m"]
        var n: float = term["n"]
        var phase: float = term["phase"]
        var weight: float = term["weight"]
        value += weight * sin(m * phi + phase) * cos(n * theta + phase * 0.5)
        weight_sum += absf(weight)
    if weight_sum > 0.0:
        value /= weight_sum
    var taper := sin(theta) * sin(theta)
    return 1.0 - lumpiness * taper * (0.5 + 0.5 * value)

static func _star_normal(point: Vector3, semi: Vector3) -> Vector3:
    var gradient := Vector3(point.x / (semi.x * semi.x), point.y / (semi.y * semi.y), point.z / (semi.z * semi.z))
    if gradient.length_squared() < 1e-12:
        return Vector3.UP
    return gradient.normalized()

static func _make_collision_body() -> StaticBody3D:
    var body := StaticBody3D.new()
    body.name = "Collision"
    body.collision_layer = 0
    body.collision_mask = 0
    body.set_meta(&"presentation_envelope", true)
    body.set_meta(&"disabled_in_viewer", true)
    return body

static func _make_collision_box(size: Vector3) -> StaticBody3D:
    var body := _make_collision_body()
    var shape_node := CollisionShape3D.new()
    shape_node.name = "EnvelopeBox"
    var shape := BoxShape3D.new()
    shape.size = size
    shape_node.shape = shape
    shape_node.disabled = true
    body.add_child(shape_node)
    return body

static func _make_collision_cylinder(radius: float, length: float) -> StaticBody3D:
    var body := _make_collision_body()
    var shape_node := CollisionShape3D.new()
    shape_node.name = "EnvelopeCylinder"
    var shape := CylinderShape3D.new()
    shape.radius = radius
    shape.height = length
    shape_node.shape = shape
    shape_node.disabled = true
    shape_node.transform = Transform3D(Basis(Vector3.RIGHT, PI / 2.0), Vector3.ZERO)
    body.add_child(shape_node)
    return body

static func _opaque_material(albedo: Color, metallic: float, roughness: float) -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = albedo
    material.metallic = metallic
    material.roughness = roughness
    return material

static func _material_water() -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.16, 0.38, 0.52, 0.45)
    material.metallic = 0.0
    material.roughness = 0.18
    material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    return material

static func _material_hard_rock() -> StandardMaterial3D:
    return _opaque_material(Color(0.42, 0.38, 0.33), 0.0, 0.92)

static func _material_fault() -> StandardMaterial3D:
    return _opaque_material(Color(0.55, 0.42, 0.30), 0.0, 0.78)

static func _material_void() -> StandardMaterial3D:
    return _opaque_material(Color(0.05, 0.05, 0.07), 0.05, 0.95)

static func _material_casing() -> StandardMaterial3D:
    return _opaque_material(Color(0.62, 0.64, 0.68), 0.95, 0.18)