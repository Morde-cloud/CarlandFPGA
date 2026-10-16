"""Independent Python review of actual Godot-exported transformed triangles.

Each whole mesh must fit ONE convex disabled shape, within 2 micrometres.
This is a floating-point asset fixture check, not continuous collision proof.
"""
import collections
import math

TOL = 2e-6

def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a): return math.sqrt(dot(a, a))

def local(point, shape):
    t = shape['transform']
    cols = [t[k] for k in ('x', 'y', 'z')]
    # Invert the actual exported basis, rather than assuming exact orthogonality.
    determinant = dot(cols[0], cross(cols[1], cols[2]))
    assert determinant > .99999 and determinant < 1.00001
    assert all(abs(dot(cols[i], cols[j]) - int(i == j)) < 2e-6 for i in range(3) for j in range(3))
    delta = sub(point, t['origin'])
    return [dot(delta, cross(cols[1], cols[2]))/determinant,
            dot(delta, cross(cols[2], cols[0]))/determinant,
            dot(delta, cross(cols[0], cols[1]))/determinant]

def excess(point, shape):
    p = local(point, shape)
    if shape['type'] == 'BoxShape3D':
        assert all(s > 0 for s in shape['size'])
        return max(abs(v)-s/2 for v, s in zip(p, shape['size']))
    radius, height = shape['radius'], shape['height']
    assert radius > 0 and height > 0
    radial = math.hypot(p[0], p[2])
    if shape['type'] == 'CylinderShape3D':
        return max(radial-radius, abs(p[1])-height/2)
    assert shape['type'] == 'CapsuleShape3D' and height >= 2*radius
    return math.hypot(radial, max(abs(p[1])-(height/2-radius), 0))-radius

def review(raw):
    assert [a['kind'] for a in raw['assets']] == ['drill','water','hard_rock','fault','void','casing','frame']
    reports, findings = [], []
    for asset in raw['assets']:
        kind = asset['kind']
        points = [p for m in asset['meshes'] for p in m['faces']]
        assert points and all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in points)
        lo = [min(p[i] for p in points) for i in range(3)]
        hi = [max(p[i] for p in points) for i in range(3)]
        pivot = max(map(norm, points))
        radial = max(math.hypot(p[0], p[1]) for p in points)
        assert abs(pivot-asset['meta_pivot']) < TOL
        assert all(abs(lo[i]-asset['meta_bounds']['min'][i]) < TOL and abs(hi[i]-asset['meta_bounds']['max'][i]) < TOL for i in range(3))
        assert asset['collision_layer'] == asset['collision_mask'] == 0
        assert asset['shapes'] and all(s['disabled'] for s in asset['shapes'])
        meshes = []
        for mesh in asset['meshes']:
            faces = mesh['faces']
            assert faces and len(faces) % 3 == 0
            # Convexity makes this sufficient for all complete triangles in this mesh.
            bounds = [(max(excess(p, s) for p in faces), s['path']) for s in asset['shapes']]
            whole_mesh_excess, enclosing_shape = min(bounds)
            edges, terms, degenerate = collections.defaultdict(list), [], 0
            for i in range(0, len(faces), 3):
                a, b, c = faces[i:i+3]
                ids = [tuple(round(v, 6) for v in p) for p in (a,b,c)]
                degenerate += len(set(ids)) != 3 or norm(cross(sub(b,a), sub(c,a))) <= 1e-10
                for u, v in zip(ids, ids[1:]+ids[:1]): edges[tuple(sorted((u,v)))].append((u,v))
                terms.append(-dot(a,cross(b,c))/6)
            bad_edges = sum(len(v) != 2 or v[0] != v[1][::-1] for v in edges.values())
            volume = math.fsum(terms)
            item = {'path':mesh['path'], 'triangles':len(faces)//3, 'boundary_edges':bad_edges,
                    'degenerate':degenerate, 'clockwise_volume_m3':volume,
                    'determinant':mesh['transform']['determinant'], 'enclosing_shape':enclosing_shape,
                    'whole_mesh_max_excess_m':whole_mesh_excess}
            meshes.append(item)
            if bad_edges or degenerate or volume <= 0 or mesh['transform']['determinant'] <= 0:
                findings.append({'kind':kind,'mesh':mesh['path'],'finding':'topology_or_orientation'})
            if whole_mesh_excess > TOL:
                findings.append({'kind':kind,'mesh':mesh['path'],'finding':'whole_mesh_containment','excess_m':whole_mesh_excess})
        if kind == 'drill': assert radial < .12 and abs(hi[2]-lo[2]-.8) < TOL
        if kind == 'frame': assert len(meshes) == len(asset['shapes']) == 12
        reports.append({'kind':kind, 'min':lo,'max':hi,'pivot_m':pivot,'max_radius_z_m':radial,'meshes':meshes})
    return {'asset_count':len(reports), 'mesh_count':sum(len(r['meshes']) for r in reports),
            'containment_tolerance_m':TOL,'edge_weld_digits':6,'reports':reports,'findings':findings,
            'status':'passed' if not findings else 'rejected',
            'limits':['per-component closed meshes, not a Boolean union-volume calculation',
                      'floating-point convex containment within tolerance, not exact or continuous collision proof',
                      'disabled candidate shapes, no runtime authority/physics or G01 acceptance']}
