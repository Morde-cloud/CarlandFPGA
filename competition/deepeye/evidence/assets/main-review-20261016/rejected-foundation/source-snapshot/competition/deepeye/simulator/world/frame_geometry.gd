class_name DeepEyeFrameGeometry
extends Object

## DeepEye B 30 m workspace frame: cube [-15, 15]^3 shown as exactly 12 edge
## prisms with no enclosing face surfaces (no opaque or transparent walls, no
## wireframe substitute). Fully three-dimensional, editable geometry.
## Human contract DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
## c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
## Resource contract: coordinates cube_min [-15,-15,-15], cube_max [15,15,15].
## Presentation only: the Collision child is a disabled StaticBody3D envelope of
## the 12 edge bars (collision_layer 0, collision_mask 0, shapes disabled); no
## authority or truth API. Corner markers and optional coordinate ticks belong to
## A viewer/editor work and are deliberately absent from this asset.

const HALF_EXTENT_M := 15.0
const EDGE_CROSS_SECTION_M := 0.12

static func build() -> Node3D:
    var root := Node3D.new()
    root.name = "FrameWorkspace"
    var visual := Node3D.new()
    visual.name = "Visual"
    root.add_child(visual)
    var collision := _make_collision_body()
    root.add_child(collision)
    var material := _material_frame()
    var offset := HALF_EXTENT_M - EDGE_CROSS_SECTION_M * 0.5
    var sizes := [
        Vector3(2.0 * HALF_EXTENT_M, EDGE_CROSS_SECTION_M, EDGE_CROSS_SECTION_M),
        Vector3(EDGE_CROSS_SECTION_M, 2.0 * HALF_EXTENT_M, EDGE_CROSS_SECTION_M),
        Vector3(EDGE_CROSS_SECTION_M, EDGE_CROSS_SECTION_M, 2.0 * HALF_EXTENT_M),
    ]
    for axis in 3:
        for side_a in [-1.0, 1.0]:
            for side_b in [-1.0, 1.0]:
                var center := Vector3.ZERO
                if axis == 0:
                    center = Vector3(0.0, side_a * offset, side_b * offset)
                elif axis == 1:
                    center = Vector3(side_a * offset, 0.0, side_b * offset)
                else:
                    center = Vector3(side_a * offset, side_b * offset, 0.0)
                var instance := MeshInstance3D.new()
                var box := BoxMesh.new()
                box.size = sizes[axis]
                instance.mesh = box
                instance.material_override = material
                instance.name = "Edge_A" + str(axis) + "_" + str(int(side_a)) + "_" + str(int(side_b))
                instance.position = center
                visual.add_child(instance)
                var shape_node := CollisionShape3D.new()
                shape_node.name = String(instance.name) + "_Envelope"
                var shape := BoxShape3D.new()
                shape.size = sizes[axis]
                shape_node.shape = shape
                shape_node.disabled = true
                shape_node.position = center
                collision.add_child(shape_node)
    root.set_meta(&"declared_envelope", {
        "bounds_min": Vector3(-15.0, -15.0, -15.0),
        "bounds_max": Vector3(15.0, 15.0, 15.0),
        "note": "12 visible edge prisms only, no enclosing surfaces; cube [-15, 15]^3",
    })
    return root

static func _make_collision_body() -> StaticBody3D:
    var body := StaticBody3D.new()
    body.name = "Collision"
    body.collision_layer = 0
    body.collision_mask = 0
    body.set_meta(&"presentation_envelope", true)
    body.set_meta(&"disabled_in_viewer", true)
    return body

static func _material_frame() -> StandardMaterial3D:
    var material := StandardMaterial3D.new()
    material.albedo_color = Color(0.80, 0.82, 0.86)
    material.metallic = 0.15
    material.roughness = 0.35
    return material