# B procedural asset foundation and independent review

This checkpoint implements A's three-method resource factory in B-owned files:
`create_drill()`, `create_obstacle(kind)` and `create_frame()`. It supplies a
0.80 m drill with six blade groups and eighteen studs, five obstacle kinds
(water, hard_rock, fault, void, casing), and twelve cube edges without faces.
Metadata is measured from actual transformed mesh vertices. Candidate collision
shapes are disabled, with collision layer/mask zero; A retains world authority,
collision/sweep integration, viewer/editor and gameplay decisions.

Main acceptance is limited to this software/asset inspection foundation.
G01, full game-grade art/UI, equal blue/red gate integration, complete passage,
free-camera/editor behavior, causal truth isolation, continuous collision,
both control paths, R03, and hardware/system acceptance are **not established**.
The regular inspection layout is not a proposed fixed gameplay route.

## Actual validation

- Official Windows Godot 4.7.2 `4.7.2.stable.official.ed1daf0bf`, executable
  SHA256 `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424`.
  The engine package stays private; acquisition/version evidence is in the raw
  geometry/render result records. No global install or A project edit.
- 622 actual engine checks pass. The baseline stderr contains the intentional
  unsupported-kind negative test; export and final render stderr are empty.
- Independent Python review consumes exported **actual mesh triangles** for
  seven assets /45 mesh components: paired opposite edges after 1-micrometre
  welding, nondegenerate triangles, positive clockwise signed component volume,
  proper basis orientation, measured bounds/pivot and disabled shape metadata.
- Every complete mesh fits **one** convex box/cylinder/capsule, within 2e-6 m.
  This uses an inverse of the exported shape basis. Convexity then covers each
  complete triangle; per-vertex membership in different shapes is insufficient.
  This is numerical candidate containment, not exact or continuous CCD proof.
- The original correction02 export is a preserved negative control: eighteen
  reflected stud meshes and one casing containment failure are detected. The
  corrected 45 meshes pass. Closed component volumes do not measure the Boolean
  union of overlapping drill components or prove absence of self-intersections.
- A new isolated project ran the portable reproduction script successfully.

The drill's actual radius about Z is 0.11985299381223237 m, Z bounds approximately
[-0.3999999762, 0.4000000060] m and pivot radius 0.40447494509872484 m. Its candidate
capsule radius is 0.12 m, total height 1.04 m (axis endpoints approximately
±0.52 m). This candidate is not A's final motion or collision ABI. Casing visual
radius is 0.3998318237102257 m within its 0.4 m cylinder. Exact values and numerical
tolerances are in `convex-review.json` and `geometry/result.json`.

## Real rendering and visual review

`render/png/` contains eleven 1280x720 images from the same source bytes:
six drill axis views, oblique and head views, a labelled five-kind gallery, and
two views of thirty obstacles plus drill and edge cube. Main viewed all eleven.
Actual traversal counts 32 objects,70 meshes,43904 triangles,43 disabled shapes;
occluded screenshot pixels are not used as object-count evidence. Device and
driver are recorded in `render/render_report.json` (RTX4060 Laptop, OpenGL
compatibility renderer). This proves no FPS, final renderer or runtime behavior.

The main corrected inspection-camera fitting and added a view-only fill light;
asset geometry and materials did not change. Previous malformed command,
cropped image and harness parse failure are retained in `render/prior-attempts/`.
The raw harness's introductory “five PNGs” comment is stale; its shot list and
executed output contain eleven. Dark cutters/void and plain procedural forms
remain artwork-quality limitations, rather than final game-grade acceptance.

## Reproduce

From the repository root, using Python 3.12 standard library and the exact
Windows engine executable above:

```text
python -B -X utf8 competition/deepeye/evidence/assets/main-review-20261016/independent_review.py --godot PATH_TO_GODOT_EXE --output-root YOUR_NEW_DIRECTORY
```

Add `--render` to render the inspection fixture on an actual GPU. The script
creates its own `project.godot` and copies only the twelve pinned B source files;
it does not start or modify A's application. Render reproduction needs a working
Windows graphics session. No physical board, register write or ENABLE is used.

## Provenance and rejected results

The original foundation and correction02 were rejected by main. Their worker
logs, source snapshots and main findings remain recorded. Correction03 fixed
the geometry but wrote a sibling evidence/private directory and the wrong work
label. `provenance-reconciliation.json` records the actual registered job,
ownership and mismatch. Raw worker records were not rewritten or treated as
ownership-compliant execution. Main adopted the exact corrected source only
after independent engine, topology, containment and rendering evidence.

H01-H15 DEEPEYE-HUMAN-LOCK-20261014/revision1 remains unchanged. Canonical
requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
contract source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, frozen design
`1011259415a0916054eb580687612580bc1e5f09`. This record does not weaken any human
requirement or transfer A's ABI/board authority.
