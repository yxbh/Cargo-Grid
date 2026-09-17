# Geometry and print assumptions

This is the maintainer reference for dimensions, interfaces and validation limits. The README covers normal use; this file records the details that must not change accidentally.

## Datums and interfaces

All dimensions are millimeters. The southwest main-body corner is the tile datum, not the bounding-box centre; the underside is Z=0. Manifest/API `pitch` is the user-facing unit size and `height` is tile thickness. X-socket centres are at `(pitch/2 + i*pitch, pitch/2 + j*pitch)`.

For unit size `u`, the main body is `u*nx` by `u*ny`. Positive-X/Y male projections and the south female depth are `0.1*u`; the west female depth adds the existing absolute 0.1 mm allowance. Joining half-widths, necks, outer walls and 45-degree flanks scale from the standard 60 mm local-plane profile. At 60/13, an unterminated tile remains `(60*nx+6, 60*ny+6, 13)` with the original 6/6.1 mm depths.

`joint_style="original"` is the default. For tile thickness `t`, male ledges reach `t-3` and female pocket ceilings reach `t-2.8`; the 0.2 mm difference remains an absolute allowance. The explicit `full-height` option extends tabs to the top and opens receiving pockets through the roof. Full-height male tabs do not fit original roofed female pockets. Tile-facing edge and corner accessories use the selected unit/thickness/style.

The socket X outline scales in its local plane from the standard approximately 44.556 mm throat. The plug's nominal outline scales from the same dimensions while its small plug/socket differences, 0.08 mm accepted bracket-stem inset and explicit `fit_offset` remain absolute millimeters. Plug projection is `t-0.2`; the final R2 tip and analytic 3 mm entry roundover remain physical radii. A smaller unit can require the standalone entry cutter rather than a whole-body fillet, but it preserves the matching local profile. When a panel plug is turned upright, the scaled local plane becomes world X/Z and thickness remains its world-Y insertion depth.

The standard compatibility preset is 60 mm unit size, 13 mm thickness and zero fit offset. Other values match parts generated from the same effective parameters but are not claimed compatible with standard stock parts. Cells, copy counts, build dimensions, packing gaps, stop heights, ramp run, round-hole diameter and slicer settings do not scale. Comfort radii remain explicit millimeters; constrained small-unit features use only their documented capped blend. The separate physical support-rail dovetail is not a tile interface and remains fixed. Minimum unit/thickness checks protect current constructions, not universal printability.

### Optional open-through tile-edge-joint experiment

At reference dimensions, opening the negative-X pockets brings them close to adjacent X-socket entry flares. The separating web narrows to about 0.146 mm at Z=12.5 and opens to the exterior near Z=12.75. This also occurs without additional round holes. Solid validity, nominal mating checks or an empty slicer-warning list do not establish adequate structural integrity.

The full-height option remains explicitly experimental. This refers only to alternate tile-edge tabs/open receiving pockets, not cargo-stop height, tile thickness or printer build height. No narrower joint, reduced entry relief, restored roof or extra fit allowance is silently substituted to hide that limitation.

## Exact footprints and hole scopes

Exact layouts use complete-pitch cells and integrated filler volume on their terminated perimeter pieces. Filler distribution may be balanced or biased to positive/negative sides. It never scales socket pitch. Assembly frames describe the floor layout; export packing and print rotations are separate transforms.

The full 10 mm round-hole pattern is the default. `full` scope uses half-unit grid sites except X-socket centres, including retained edge/corner sites; `interior` keeps only complete interior sites, and `hole_diameter=None`/`--no-holes` makes solid webs. At standard 60 mm units, default 1x1, 2x1, 2x3 and 4x4 tiles respectively have 8, 13, 29 and 65 additional sites. The diameter stays 10 mm when unit size changes. Terminated/filler boundaries and geometric keep-outs can reject sites; accepted status and reasons appear in the manifest. If no requested site fits, the CLI recommends a smaller diameter or `--no-holes`.

Neither enabling holes nor producing one valid solid establishes strength or bridge quality. Check the intended hole centres, retained webs and actual slicer paths for the chosen configuration.

## Non-printing roof modifiers

Roof support is off by default and only applies to original-style tile `part` and `layout` jobs. It targets actual planar, downward-facing female roof faces on both retained west and south edges, not male edges. Either female edge may be terminated independently. A job with no eligible female edge is rejected.

Faces are grouped by edge and grid-centred roof before clipping. A south R5 cutout can split one roof into two planar faces. `critical` coverage creates two nominal 3 mm bands per roof, with an inner offset of at least 6 mm from its grid centre and at least 1 mm beyond an accepted edge-hole radius. `full` preserves complete roof footprints; separated face volumes remain separate rather than becoming a nonmanifold modifier at a tangent shared edge. A default full-hole 2x1 tile has three roofs, six critical modifiers or five full modifiers.

The enforcer half-span is `min(max(1.0, generation_layer_height), roof_thickness)`, giving Z=9.2--11.2 around the default Z=10.2 ceiling. This spans multiple potential layer planes; it is not a permanent 2 mm support slab. Bambu's manual-support calculation selects current-layer regions inside the enforcer and removes regions already covered by the preceding model layer. Changing a profile does not regenerate the masks, so actual contacts still need checking.

Native `support_enforcer` parts do not become tile solids. STEP exports and model packing bounds exclude them; print transforms move them with the owning model. The slicer can expand actual support beyond the nominal mask, including temporarily occupying west/south round cutouts. Inspect underside/edge access and clear those cutouts before assembly.

Logical PETG model/base slot 1 and PLA interface slot 2 are explicit. The maintained dissimilar-material workflow requests `support_top_z_distance=0`, `independent_support_layer_height=0`, `support_interface_spacing=0`, `support_interface_top_layers=2` and `support_on_build_plate_only=0`. These five keys are included in process-override tracking so a profile change does not silently replace the requested contact behavior. At least two dense layers are required for zero contact; explicitly larger counts are preserved. A positive top gap selects a separate gapped request without forcing synchronized layer height.

Selecting this workflow declares the intended PETG/PLA roles; names alone do not prove chemical compatibility or release quality. Initial same-material/unsupported roof pairs are rejected. If materials are substituted later in the slicer, re-evaluate contact settings rather than leaving zero gap on a potentially fusing pair. The zero-contact workflow additionally preserves `support_object_xy_distance=0.4`: a setting-only 0.35-to-0.40 comparison removed small same-layer PLA-interface/PETG-side-wall overlaps outside the intended roof projection while retaining all lips and exact vertical contact. South critical-mask coverage decreased by no more than 1.44 percentage points; the first-layer footprint was unchanged. This is a scoped contact safeguard, not a global XY change. Threshold, bridge, cooling, speed, prime, flush and automatic-foot settings remain untouched. Roof support cannot be combined with stacks, catalogues, accessories or full-height joints.

### Slice mode and first-layer defaults

Every generated Bambu plate explicitly defaults to `Auto For Match` / Convenience Mode, with no requested physical nozzle map or assignment cache. This is the generator's chosen default rather than Bambu's factory default. An explicit `nozzle_map`/`--roof-nozzle-slots` request selects Custom mapping. In the native dialect, `Auto For Flush` is Filament-Saving Mode and `Manual` is Custom filament grouping. The distinct `normal(manual)` support type selects enforcer-defined regions and does not force Custom grouping.

`support_on_build_plate_only` is false and explicitly preserved for the zero-contact workflow. Initial support-foot expansion is omitted by default, leaving the slicer's native automatic value; `foot_expansion=0`/`--roof-foot-expansion-mm 0` explicitly requests zero. An observed automatic nozzle assignment is not a locked contract. Explicit contact changes are tracked for GUI import, while native-default mapping and automatic-foot keys remain unmarked.

Expansion changes the first support/raft layer, not the model CAD. It may affect bed contact, clearance and removal even when roof-facing interface coverage is unchanged. Neither zero nor automatic expansion is universally correct. Check the actual support and model extrusion footprints, including declared widths and arcs, and distinguish those from nominal CAD sections at the same Z. Layer discretization can make those representations differ.

## Stacks and accessory scope

Stacking creates explicit sacrificial support-base and lower/upper release volumes between repeated identical tiles. The gap must leave positive base thickness after both interfaces. Quantities, maximum stack height, partial batches, material roles and usable build reservations remain explicit. Generated contact/separation geometry does not prove successful physical detachment.

The accessory catalogue contains independently authored functional edge/corner pieces, X-plug plates, normal full-solid stops, angled stops, vertical tile brackets and physical support rails. It is not a promise that every contour or secondary mechanism matches another design. Physical support rails use separate end-to-end dovetails and a 25 mm supporting depth; they are not X-plug attachments, and no positive mat-to-rail latch is assumed.

Catalogue membership is finite and build-volume-dependent. Oversized accessory variants are listed as omitted rather than shrunk. Ordered tile sizes remain distinct even if either orientation fits the same bed. Bambu bracket, normal-stop and angled-stop jobs first apply their validated X-axis print rotation; bounding-rectangle packing then permits its existing 90-degree XY rotation. Other families are not reoriented. This is not an optimal-packing guarantee.

### Vertical tile brackets

`vertical-tile-bracket` replaces the unreleased `lock-90` catalogue family without retaining an alias. It supports three depth-matched configurations—floor 1x2 -> wall 1x2, floor 2x1 -> wall 2x1 and floor 2x2 -> wall 2x2—and two independent-height configurations—floor 1x1 -> wall 1x2 and floor 2x1 -> wall 2x2. API `nx` is base/wall X width, `ny` is floor-base Y depth, and optional `panel_height_cells` is wall Z height; omitting or explicitly matching it to `ny` preserves the original specification and stable ID. Floor and wall posts use the same interface unit/thickness, including the rotated world-X/Z wall profile. Standard 60/13 remains the stock-compatible preset.

The bracket is one full-width solid-backed wedge. Base shoulder Z=0 and downward plug tips Z=-12.8 are retained; original lower geometry through Z3.1 is unchanged. A filled nonfunctional upper-rim band at Z3.1--4.1 avoids a shallow exterior slit under the wedge. Base dimensions are 60x120, 120x60 and 120x120 mm. No outboard tabs, through-channel pattern or split mechanism is added.

For base depth `d`, the vertical tile seat is Y=`d-13`, panel plug tips end at Y=`d-0.2`, and the separate tile occupies Y=`d-13` through `d`. Panel bottom Z=6.1 and its 60 mm row pitch stay fixed. There are two vertically stacked panel plugs on 1x2, two side-by-side on 2x1, and four on 2x2. A full-width internal strip occupies Z4.1--6.1 and has nominal zero-gap bearing; with the illustrated full-hole tiles, planar contact is about 260.892 mm2 on 1x2 and 521.784 mm2 on the two-column brackets. These are nominal CAD contacts, not force-free fit or a load rating.

The ordinary tile remains a separate part and is not fused into bracket STEP/STL/3MF geometry. The default wall placement keeps its original underside outward. The accepted reverse placement uses a rigid Z=180-degree then X=-90-degree rotation so the top face is outward; every adjoining wall tile must use the same orientation because left/right joining handedness reverses. Solid backing makes backed interior round holes nominally 13 mm-deep blind pockets. Edge half/quarter cutouts are not all sealed bores. Same-orientation left/right/up extensions retain their mating placement, while downward extension is obstructed.

All five brackets use the accepted two-way wall post. Its wide seating-plane root flare is removed, the straight stem profile is inset 0.08 mm, a 0.1 mm transition at insertion depth 10.7--10.8 mm reaches the exact unchanged final 2 mm rounded tip, and same-profile reinforcement extends 2 mm behind the seat. The top-outward seated CAD arrangement has zero volume collision; the underside-outward arrangement retains 5.439166 mm3 total nominal overlap on the 1x1-to-1x2 representative. A straight top-outward insertion sweep still reaches 5.439166 mm3 at intermediate offsets because the unchanged tip base crosses the narrow corridor. This is an accepted nominal-interference design for physical testing, not evidence of force-free insertion or verified physical fit.

The two shallow variants retain a 60 mm floor depth, panel seat Y=47, panel plug tips Y=59.8 and the original two-row wall Z grid at standard dimensions. Their natural filled rear profile rises 107 mm across the available 42.8 mm upper run rather than forcing the original 45-degree slope. The upper rear body stays behind the connector root while both floor and panel X regions remain exact. All five brackets use R3 at the analogous exposed thick front-to-slope transition; other thick free body edges remain R2, the thin bearing lip remains R1 and the internal panel-bearing corner stays exact. Standard shallow bounds remain 60x60x140.378 mm and 120x60x140.378 mm including downward plugs.

Shallow Bambu exports use Y=-90 degrees broad-side-down and object-scoped normal Auto. At official H2D 0.8/0.32 and 0.4/0.20 PETG settings, both variants had one connected model first layer, complete model-layer schedules and paths inside shared reach. OFF controls emitted floating-cantilever warnings. Auto generated about 6.74/3.93 g support for the one-column variant and 19.91/14.06 g for the two-column variant, reaching both floor and panel X mating regions. Those regions are exposed for access in the side-down pose, but support removal, resulting fit, stability and strength are not physically verified.

### Floor ramps

`ramp` is an independently authored floor-to-mat transition using the existing original roofed female tile-edge interface. It has a fixed 13 mm rise, fixed 50 mm finished positive-Y run and parametric X width in integer 60 mm cells. Each cell repeats one unchanged female pocket at its half-pitch centre; width changes never scale the run or joint. The ramp receives an unchanged tile's north male edge at Y=0. Rotating a printed part does not change the directional joining contract.

The approved profile is one filled wedge with a 10 mm high-edge carrier and a floor-tangent rounded nose. One coupled operation applies R2 to the free exterior edges while a mating-boundary underside transition remains R1; the female pocket is then cut with the shared `tile_join_tool` at 6.1 mm depth. The 1-cell production solid is geometrically coincident with the approved visual STEP within the existing Boolean/STEP budgets. Separate adjacent ramps meet without overlap, while a multi-cell ramp is one continuous solid without internal assembly seams.

Ramps require original roofed joints. Width and the female join follow unit size, rise follows tile thickness and the finished run remains the approved physical 50 mm. Experimental full-height ramp geometry remains rejected because a generic post-fillet cutter left real overlap with its matching tile. There are no corner ramps, male adapters, X plugs, holes or added mechanisms.

The source orientation already places the underside on Z=0. Bambu exports scope normal Auto support to each ramp object for its female pocket roofs without enabling global support. Bounded native checks of 1-cell and 5-cell ramps at the documented H2D PETG profiles produced one connected first model layer and continuous model schedules. The deposited first layer reached about 48.72 mm of the 50 mm run at 0.8/0.32 and 48.47 mm at 0.4/0.20; the remaining nose is the upward-curving tangent tip. Auto support occupied only the exposed female-pocket region and must be removed before assembly. This is slicer evidence, not physical fit, adhesion or traffic/load validation.

### Normal full-solid vertical stops

`vertical-stop` is distinct from `vertical-tile-bracket` and does not restore the obsolete `lock-90` name. Its finite catalogue grids are 1x1, 1x2, 2x1 and 2x2 at H60 and H120 mm. The first count is base X width, the second is base Y depth and height is measured from the attachment shoulder Z=0. Base shoulder, pitch and downward X plugs reuse the existing mounted-base construction; plug tips remain Z=-12.8.

The body is one full-width filled triangular wedge from the 4.1 mm front toe to a solid cargo face at positive Y. It has no open central bay, separate side ribs, wall holes, panel connectors, ledge or tile. The 2x1/H120 geometry is the natural wedge selected for the family rather than an extra-material raised 45-degree toe. A solid CAD body does not request 100% slicer infill.

The retangent profile is solved so the coupled R2 blend reaches the exact requested H60/H120 maximum while the cargo-face Y datum remains exact. One fillet operation rounds all twelve free source edges: cargo cap/perimeter, both diagonal rear boundaries, front/toe perimeter and the complete underside outer perimeter. The protected X plug profiles and existing R1 roots have zero geometric change. R2 on both horizontal boundaries of the 4.1 mm toe leaves a 0.1 mm planar center land at the extreme front; source bodies, STEP roundtrips and closed meshes remain valid.

Each Bambu export computes its X rotation from the actual depth, height and R2 retangent slope so the broad rear face is down before fit checks and packing. Normal Auto support metadata is scoped to the stop object. In the documented H2D PETG native checks, 1x1/H120 and 2x1/H120 generated mounting-region support at both 0.8/0.32 and 0.4/0.20; this requires sliced-path and removal review and does not imply physical print approval. Other profiles can make different support decisions.

### Accessory edge rounds

Original-style edge and corner bodies use R3 before the unchanged tile-joint tools are applied. The asymmetric outer-corner tips are extended only along their free long axis before rounding so their published envelopes remain unchanged. Experimental full-height parts retain their existing selective R2/R1 construction.

Straight rail and connector outer bodies use R3, with R3 window corners and R2 window rims. Rail-end variants 1/2 use sequential rounds to avoid kernel-dependent coupled topology: R3 around both side caps, with R0.75/R0.25 along the ramp-profile edges. Variant 1 uses R2.5 window corners, R1 horizontal window rims and R0.5 sloped underside rims; variant 2 uses R2/R2/R1.5. Variants 3/4 use coupled R3 bodies with R3/R2 horizontal windows and R1/R0.75 on their sloped underside window rims. Male/female support tools are applied afterward. Small custom units proportionally cap constrained window-rim radii; the separate support dovetail remains fixed. Attachment plates use R2 around the complete 4.1 mm body, then receive exact X plugs and R2 roots.

Angled `lock-45` stops retain a 4.1 mm front base/toe, a 6 mm horizontal cap thickness (about 4.243 mm normal to the 45-degree cargo face), unchanged outer bounds and exact X connectors/roots. One coupled operation applies R2 to all 18 free envelope edges. The 1x1 and 2x2 Bambu poses remain X=-135 degrees; bounded native 0.8/0.32 and 0.4/0.20 checks produced no support with either OFF or Auto.

## Export checks

Each design exported by `export_job` must be one valid positive-volume solid. STEP reimport checks body count, bounding coordinates within 0.00001 mm and volume against the actual surface area times OCCT linear confusion, with a small numerical floor. Export starts with OCCT's average precision mode. If and only if that STEP reimports as topologically invalid, it retries the same source solid with least precision and applies the same body, bounds and volume gates; it does not widen a tolerance or alter source geometry. The manifest records the selected STEP precision mode, deltas and budgets instead of substituting a scale-independent tolerance claim.

Mesh chord tolerance is 0.02 mm. Surface seams are welded only within 0.000001--0.00001 mm, bounded by kernel vertex tolerance and an independent displacement cap. Unmeshed faces are accepted only below 0.0000000001 mm2; all resulting meshes must still be closed, consistently oriented and positive-volume, without zero-area triangles.

A remaining isolated three-edge crack can be closed only when it is an unambiguous oppositely oriented triangle, contains no duplicate face, has maximum edge 0.1 mm, and has area below both 0.0000001 mm2 and its perimeter times OCCT linear confusion. Fifteen barycentric probes, including vertices and edge-quarter points, must lie within OCCT's 0.0000001 mm tolerance of the unchanged CAD surface. No vertices move. Larger, ambiguous, nontriangular or off-surface gaps remain errors. The mesh report records any repair and the strict checks still run afterward.

Manifests include a schema version, generator version, design modes, resolved parameters, compatibility qualifications and unsupported combinations. Core 3MF preserves model orientation and quantities; native-compatible 3MF adds plate/material/modifier metadata with diagnostic profile IDs. Neither means the exported job has been sliced or physically verified.

Bambu single-part and catalogue exports rotate attachment plates X=180 degrees body-down, original vertical tile brackets by their retangented rear-face-down X angle, shallow brackets Y=-90 degrees (broad side down), normal stops by their per-design broad-rear-face-down angle and angled stops X=-135 degrees (back face down) before bounds checks and packing. STEP/STL and core 3MF retain model orientation. Recommendations include per-artifact applied flags; Bambu plate items include the exact source-to-project transform, composed with their in-plane packing rotation and translation. Normal-stop and shallow-bracket items carry object-scoped `enable_support=1` and `support_type=normal(auto)` without changing global tile/original-bracket support behavior. The pose is already baked into the Bambu mesh and must not be applied twice. API catalogue callers use `orient_for_bambu=True` for the matching eligibility calculation. Roof-support and stack workflows keep their existing orientation and cannot be combined with independently oriented models.

The optional H2D dual-safe catalogue plan is machine-specific rather than a generic build rectangle. Ordinary plates use the verified common reach X25..325, Y0..320, Z<=320, with model bounds inset 5 mm and separated by at least 10 mm. Families occupy named coherent plates. The 306x306 mm 5x5 tile is isolated on a named left-nozzle-only plate because it cannot fit the 300 mm common width; filament slot 1 is explicitly mapped left there, while common plates retain automatic Convenience Mode. This placement policy is recorded in the manifest. Model-only packing does not replace checking generated support, brim or tower paths after a real slice.

## Optional reference comparison

Portable tests inspect generated solids, dimensions, layout placement, accepted hole locations, STEP reimports, mesh topology, accessory families, separator contacts and 3MF structure without a redistributed reference mesh.

The optional local comparison explicitly builds original-style geometry and resolves an explicitly supplied local 3MF's per-model IDs and component transforms. It samples socket rays, directional joining sections, mixed original/new signed intervals and insertion offsets. Near-horizontal mesh intersections use a disclosed 0.0001 mm section adjustment. Its 0.008 mm measurement budget covers tessellation and near-tangent sampling, not a manufacturing allowance.

Sampling is not an exhaustive insertion/collision sweep or full-surface equivalence proof. Rounded upper joining patches may differ even when sampled functional datums match. The reference itself can have both interference and clearance; that is not evidence of intended insertion force, calibration or load capacity. Full-height geometry is never reported as an original-compatible pass.

## Unverified physical properties

Physical original/new mating, insertion/removal cycles, retention force, support release, flatness, thermal behavior in a parked vehicle, impact, creep and material/process calibration require applicable physical observations. Keep those results with their actual profile and model revision, separate from package defaults. Do not infer them from silence, valid solids, imported projects or a historical study of another configuration.

No load/restraint rating, universal support setting or service-environment certification is supplied.
