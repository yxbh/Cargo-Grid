# Geometry contract and evidence boundaries

## Datums and interfaces

All dimensions are millimeters. The southwest main-body corner is the tile datum, not the bounding-box centre; the underside is Z=0. X-socket centres are at `(pitch/2 + i*pitch, pitch/2 + j*pitch)`.

At reference dimensions, the main body is `60*nx` by `60*ny`, with 6 mm positive-X/Y male projections and a 13 mm height. An unterminated tile therefore has external dimensions `(60*nx+6, 60*ny+6, 13)`. West/negative-X and south/negative-Y edges receive mating tabs. The female X pocket is 6.1 mm deep and the female Y pocket is 6 mm; joining flanks have 45-degree sides and nominal 1 mm blends.

`joint_style="original"` is the default: male ledges reach Z=10 and female pocket ceilings are at Z=10.2. The explicit `full-height` option extends tabs to the top and opens receiving pockets through the roof. Full-height male tabs do not fit original roofed female pockets. Tile-facing edge and corner accessories use the selected style.

The shared X throat is approximately 44.556 mm across X/Y, with an analytic 3 mm entry-roundover cutter over the upper 3 mm. A plug's 12.8 mm projection is constructed upward, then oriented downward by the attachment mounting frame. Shoulder seating at Z=13 leaves a nominal 0.2 mm underside gap. Entry relief, throat sections and bearing/seating land are separate features.

Pitch changes relocate the fixed interface envelopes; they do not uniformly scale them. Minimum pitch and height constraints protect those envelopes, not a universal printability threshold. `fit_offset` is an explicit socket offset, not calibrated shrinkage or slicer compensation.

### Experimental full-height limitation

At reference dimensions, opening the negative-X pockets brings them close to adjacent X-socket entry flares. The separating web narrows to about 0.146 mm at Z=12.5 and opens to the exterior near Z=12.75. This also occurs without additional round holes. Solid validity, nominal mating checks or an empty slicer-warning list do not establish adequate structural integrity.

The full-height option remains explicitly experimental. No narrower joint, reduced entry relief, restored roof or extra fit allowance is silently substituted to hide that limitation.

## Exact footprints and hole scopes

Exact layouts use complete-pitch cells and integrated filler volume on their terminated perimeter pieces. Filler distribution may be balanced or biased to positive/negative sides. It never scales socket pitch. Assembly frames describe the floor layout; export packing and print rotations are separate transforms.

Additional round holes are off by default. `interior` scope protects joining edges. Explicit `full` scope uses half-pitch grid sites except X-socket centres, including retained edge/corner sites. At diameter 10 mm, default 1x1, 2x1, 2x3 and 4x4 tiles respectively have 8, 13, 29 and 65 additional sites. Terminated/filler boundaries and geometric keep-outs can reject sites; accepted status and reasons appear in the manifest.

Neither enabling holes nor producing one valid solid establishes strength or bridge quality. Check the intended hole centres, retained webs and actual slicer paths for the chosen configuration.

## Non-printing roof modifiers

Roof support is off by default and only applies to original-style tile `part` and `layout` jobs. It targets actual planar, downward-facing female roof faces on both retained west and south edges, not male edges. Either female edge may be terminated independently. A job with no eligible female edge is rejected.

Faces are grouped by edge and grid-centred roof before clipping. A south R5 cutout can split one roof into two planar faces. `critical` coverage creates two nominal 3 mm bands per roof, with an inner offset of at least 6 mm from its grid centre and at least 1 mm beyond an accepted edge-hole radius. `full` preserves complete roof footprints; separated face volumes remain separate rather than becoming a nonmanifold modifier at a tangent shared edge. A default full-hole 2x1 tile has three roofs, six critical modifiers or five full modifiers.

The enforcer half-span is `min(max(1.0, generation_layer_height), roof_thickness)`, giving Z=9.2--11.2 around the default Z=10.2 ceiling. This spans multiple potential layer planes; it is not a permanent 2 mm support slab. Bambu's manual-support calculation selects current-layer regions inside the enforcer and removes regions already covered by the preceding model layer. Changing a profile does not regenerate the masks, so actual contacts still need checking.

Native `support_enforcer` parts do not become tile solids. STEP exports and model packing bounds exclude them; print transforms move them with the owning model. The slicer can expand actual support beyond the nominal mask, including temporarily occupying west/south round cutouts. Inspect underside/edge access and clear those cutouts before assembly.

Logical PETG model/base slot 1 and PLA interface slot 2 are explicit. The maintained dissimilar-material workflow requests `support_top_z_distance=0`, `independent_support_layer_height=0`, `support_interface_spacing=0`, `support_interface_top_layers=2` and `support_on_build_plate_only=0`. These five keys are included in process-override tracking so a profile change does not silently replace the requested contact behavior. At least two dense layers are required for zero contact; explicitly larger counts are preserved. A positive top gap selects a separate gapped request without forcing synchronized layer height.

Selecting this workflow declares the intended PETG/PLA roles; names alone do not prove chemical compatibility or release quality. Initial same-material/unsupported roof pairs are rejected. If materials are substituted later in the slicer, re-evaluate contact settings rather than leaving zero gap on a potentially fusing pair. The zero-contact workflow additionally preserves `support_object_xy_distance=0.4`: a setting-only 0.35-to-0.40 comparison removed small same-layer PLA-interface/PETG-side-wall overlaps outside the intended roof projection while retaining all lips and exact vertical contact. South critical-mask coverage decreased by no more than 1.44 percentage points; the first-layer footprint was unchanged. This is a scoped contact safeguard, not a global XY change. Threshold, bridge, cooling, speed, prime, flush and automatic-foot settings remain untouched. Roof support cannot be combined with stacks, catalogues, accessories or full-height joints.

### Slice mode and first-layer defaults

Every generated Bambu plate explicitly defaults to `Auto For Match` / Convenience Mode, with no requested physical nozzle map or assignment cache. This is the generator's chosen default rather than Bambu's factory default. An explicit `nozzle_map`/`--roof-nozzles` request selects Custom mapping. In the native dialect, `Auto For Flush` is Filament-Saving Mode and `Manual` is Custom filament grouping. The distinct `normal(manual)` support type selects enforcer-defined regions and does not force Custom grouping.

`support_on_build_plate_only` is false and explicitly preserved for the zero-contact workflow. Initial support-foot expansion is omitted by default, leaving the slicer's native automatic value; `foot_expansion=0`/`--roof-foot-expansion 0` explicitly requests zero. An observed automatic nozzle assignment is not a locked contract. Explicit contact changes are tracked for GUI import, while native-default mapping and automatic-foot keys remain unmarked.

Expansion changes the first support/raft layer, not the model CAD. It may affect bed contact, clearance and removal even when roof-facing interface coverage is unchanged. Neither zero nor automatic expansion is universally correct. Check the actual support and model extrusion footprints, including declared widths and arcs, and distinguish those from nominal CAD sections at the same Z. Layer discretization can make those representations differ.

## Stacks and accessory scope

Stacking creates explicit sacrificial support-base and lower/upper release volumes between repeated identical tiles. The gap must leave positive base thickness after both interfaces. Quantities, maximum stack height, partial batches, material roles and usable build reservations remain explicit. Generated contact/separation geometry does not prove successful physical detachment.

The accessory catalogue contains independently authored functional edge/corner pieces, X-plug plates and locks, and physical support/bracket families. It is not a promise that every contour or secondary mechanism matches another design. Physical support rails use separate end-to-end dovetails and a 25 mm supporting depth; they are not X-plug attachments, and no positive mat-to-rail latch is assumed.

Catalogue membership is finite and build-volume-dependent. Oversized accessory variants are listed as omitted rather than shrunk. Ordered tile sizes remain distinct even if either orientation fits the same bed. Print packing uses actual bounding rectangles with optional 90-degree rotation; it is not an optimal-packing guarantee.

## Export checks

Each design exported by `export_job` must be one valid positive-volume solid. STEP reimport checks body count, bounding coordinates within 0.00001 mm and volume against the actual surface area times OCCT linear confusion, with a small numerical floor. The manifest records deltas and budgets instead of substituting a scale-independent tolerance claim.

Mesh chord tolerance is 0.02 mm. Surface seams are welded only within 0.000001--0.00001 mm, bounded by kernel vertex tolerance and an independent displacement cap. Unmeshed faces are accepted only below 0.0000000001 mm2; all resulting meshes must still be closed, consistently oriented and positive-volume, without zero-area triangles.

A remaining isolated three-edge crack can be closed only when it is an unambiguous oppositely oriented triangle, contains no duplicate face, has maximum edge 0.1 mm, and has area below both 0.0000001 mm2 and its perimeter times OCCT linear confusion. Fifteen barycentric probes, including vertices and edge-quarter points, must lie within OCCT's 0.0000001 mm tolerance of the unchanged CAD surface. No vertices move. Larger, ambiguous, nontriangular or off-surface gaps remain errors. The mesh report records any repair and the strict checks still run afterward.

Manifests include a schema version, generator version, design modes, resolved parameters, compatibility qualifications and unsupported combinations. Core 3MF preserves geometry and quantities; native-compatible 3MF adds plate/material/modifier metadata with diagnostic profile IDs. Neither means the exported job has been sliced or physically verified.

## Optional reference comparison

Portable tests inspect generated solids, dimensions, layout placement, accepted hole locations, STEP reimports, mesh topology, accessory families, separator contacts and 3MF structure without a redistributed reference mesh.

The optional local comparison explicitly builds original-style geometry and resolves the reference archive's per-model IDs and component transforms. It samples socket rays, directional joining sections, mixed original/new signed intervals and insertion offsets. Near-horizontal mesh intersections use a disclosed 0.0001 mm section adjustment. Its 0.008 mm measurement budget covers tessellation and near-tangent sampling, not a manufacturing allowance.

Sampling is not an exhaustive insertion/collision sweep or full-surface equivalence proof. Rounded upper joining patches may differ even when sampled functional datums match. The reference itself can have both interference and clearance; that is not evidence of intended insertion force, calibration or load capacity. Full-height geometry is never reported as an original-compatible pass.

## Unverified physical properties

Physical original/new mating, insertion/removal cycles, retention force, support release, flatness, thermal behavior in a parked vehicle, impact, creep and material/process calibration require applicable physical observations. Keep those results with their actual profile and model revision, separate from package defaults. Do not infer them from silence, valid solids, imported projects or a historical study of another configuration.

No load/restraint rating, universal support setting or service-environment certification is supplied.
