extends SceneTree
const Factory = preload("res://world/asset_library.gd")

func vec(v: Vector3) -> Array:
    return [v.x, v.y, v.z]

func relative(asset: Node3D, node: Node3D) -> Transform3D:
    var chain: Array[Node3D] = []
    var current: Node = node
    while current != asset:
        if current is Node3D:
            chain.push_front(current)
        current = current.get_parent()
    var result := Transform3D.IDENTITY
    for part in chain:
        result = result * part.transform
    return result

func xform(t: Transform3D) -> Dictionary:
    return {"x": vec(t.basis.x), "y": vec(t.basis.y), "z": vec(t.basis.z), "origin": vec(t.origin), "determinant": t.basis.determinant()}

func extract(asset: Node3D, kind: String) -> Dictionary:
    var meshes: Array = []
    var shapes: Array = []
    for node in asset.find_children("*", "MeshInstance3D", true, false):
        var m := node as MeshInstance3D
        var t := relative(asset, m)
        var points: Array = []
        for vertex in m.mesh.get_faces():
            points.append(vec(t * vertex))
        meshes.append({"path": str(asset.get_path_to(m)), "transform": xform(t), "faces": points})
    for node in asset.find_children("*", "CollisionShape3D", true, false):
        var c := node as CollisionShape3D
        var item := {"path": str(asset.get_path_to(c)), "transform": xform(relative(asset, c)), "disabled": c.disabled, "type": c.shape.get_class()}
        if c.shape is BoxShape3D:
            item["size"] = vec(c.shape.size)
        elif c.shape is CapsuleShape3D or c.shape is CylinderShape3D:
            item["radius"] = c.shape.radius
            item["height"] = c.shape.height
        shapes.append(item)
    var b: StaticBody3D = asset.get_node("Collision")
    var bounds: Dictionary = asset.get_meta("geometry_bounds_m")
    return {"kind": kind, "meshes": meshes, "shapes": shapes, "collision_layer": b.collision_layer, "collision_mask": b.collision_mask, "meta_pivot": asset.get_meta("pivot_bound_radius_m"), "meta_bounds": {"min":vec(bounds["min"]),"max":vec(bounds["max"]),"size":vec(bounds["size"])}}

func _initialize() -> void:
    var records: Array = []
    for kind in ["drill", "water", "hard_rock", "fault", "void", "casing", "frame"]:
        var asset: Node3D
        if kind == "drill":
            asset = Factory.create_drill()
        elif kind == "frame":
            asset = Factory.create_frame()
        else:
            asset = Factory.create_obstacle(kind)
        records.append(extract(asset, kind))
        asset.free()
    var output := FileAccess.open("res://exported_meshes.json", FileAccess.WRITE)
    output.store_string(JSON.stringify({"engine":Engine.get_version_info(), "assets":records}))
    output.close()
    print("EXPORT asset_count=" + str(records.size()))
    quit(0)
