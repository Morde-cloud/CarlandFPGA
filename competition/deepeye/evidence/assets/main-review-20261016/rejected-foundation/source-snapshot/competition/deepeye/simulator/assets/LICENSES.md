# DeepEye asset licenses and provenance (B asset domain)

Scope: every asset produced by `competition/deepeye/simulator/world/` and exposed through
`DeepEyeAssetLibrary` (`res://world/asset_library.gd`), for work
`B-ASSETS-FACTORY-FOUNDATION-20261015-01-v1` of task `DEEPEYE-IMPLEMENTATION-20261014/v1`.
Human contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen resource contract `competition/deepeye/docs/resource_contract.json` (A-owned; SHA256
`852a686a0ee261773dbc233350a6ab1d540edae0b2c3889d928caefdfc629ff4`).

## License

All geometry is original procedural work authored for this project. It is generated at
runtime in GDScript by the B-owned scripts listed below, from closed-form formulas and a
deterministic harmonic displacement function. No external model, mesh, texture, scan,
sound or downloaded asset is used, referenced or redistributed, and no network download or
third-party installer is involved. Materials are code-defined `StandardMaterial3D`
resources with no external textures.

Identifier: `LicenseRef-CarlandFPGA-Original-Procedural` (project-internal original work;
rights held by the project owner; no third-party license obligations apply to these
assets). The Godot Engine built-in mesh classes (`BoxMesh`, `CylinderMesh`,
`CapsuleShape3D`, `BoxShape3D`, `CylinderShape3D`) are generated at runtime by the
MIT-licensed Godot Engine; no Godot asset files are redistributed with this project.

## Provenance table

| asset_id | source file | method | provenance |
|---|---|---|---|
| `drill_pdc_v1` | `world/drill_geometry.gd` | code primitives placed on the cutter-head cone surface | original design referencing the taskbook PDC requirements (taskbook section 8.1); no third-party model |
| `obstacle_water_v1` | `world/obstacle_geometry.gd` | deterministic star-mesh generator, semi-axes 3x2x1 m, inward undulation 5% tapered to poles | original procedural design (taskbook section 8.4) |
| `obstacle_hard_rock_v1` | `world/obstacle_geometry.gd` | same generator, semi-axes 1.5 m, 35% multi-harmonic lumpiness | original procedural design (taskbook section 8.4) |
| `obstacle_fault_v1` | `world/obstacle_geometry.gd` | closed solid box prism 8x1x6 m | original procedural design (taskbook section 8.4) |
| `obstacle_void_v1` | `world/obstacle_geometry.gd` | same generator, semi-axes 2x1.5x1.5 m, no undulation | original procedural design (taskbook section 8.4) |
| `obstacle_casing_v1` | `world/obstacle_geometry.gd` | closed solid cylinder OD 0.8 m x 8 m, 48 segments, caps on | original procedural design (taskbook section 8.4) |
| `frame_workspace_v1` | `world/frame_geometry.gd` | twelve edge prisms on the [-15, 15]^3 cube bounds | original procedural design (taskbook section 8.1) |

Reference documents used as design input (read-only, not redistributed):
`docs/competition/deepeye-2026/taskbook_final.md` (SHA256
`7f5c94f7fc73698236be954ae7818266d6dfe8b4949d1752dd045d76f4b71f18`) and the contract
files above.

## Notes

- Water uses translucent alpha for presentation only; transparency never changes the solid
  closed mesh or any volume/bounds metadata, and no material sends type or truth labels to
  any controller.
- Same-parameter generation: all five obstacle kinds come from shared generator code; the
  0.30 m equal blue/red gate geometry is A-owned and untouched by these assets.
- Volume, bounds and pivot-radius provenance is recorded in `simulator/assets/scene_catalog.json`;
  runtime metadata is re-measured from actual mesh vertices by the factory.
- No visual, performance or collision-acceptance claim is made here; screenshots were not
  captured in this environment.