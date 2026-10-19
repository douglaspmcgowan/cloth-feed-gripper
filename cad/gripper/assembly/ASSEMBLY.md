# Cloth-feed gripper assembly (revision B)

**Answer: build it in 32 steps, in the order below.** Every insertion path and every screw driver path checks clear in the CAD. Do the reaming and pressing on the bench first (steps 1 to 5), then the wrist plate, the servo and housing, the mount, the gears and the fingers.

This guide follows the revision B CAD in cad/gripper and the bought parts in cad/gripper/drawings/BOM.md. The data behind it is in cad/gripper/assembly/steps.json. Every torque below is an assumed starting value, not a measured one.

Directions use the CAD frame: X is the jaw closing direction, Y points up to the wrist and Z comes out of the gear plane. Jaw angle 0 is the closed pose; positive angles open the jaw.

## How the build goes

The wrist plate goes on the SO-101 roll horn first, and the housing comes up onto it afterwards. Reaming and pressing are done on the bench so the arm never takes a hammer blow. Steps 29 to 31 need the servo powered to hold the jaw open.

- Prepare the printed parts (steps 1 to 5).
- Wrist plate on the arm (steps 6 to 9). Built on the bench, then joined.
- Servo and housing (steps 10 to 16). Built on the bench, then joined.
- Housing onto the wrist plate (steps 17 to 18).
- Pins, knuckles and front plate (steps 19 to 24).
- Fingers and pads (steps 25 to 32).

## Tools and consumables

- 0-25 mm micrometer
- 1.5 mm hex key
- 2.0 mm hex key
- 2.5 mm drill
- 3.0 mm H7 hand reamer
- 3.0 mm pin gauge
- 6.0 mm H7 hand reamer
- 7 mm spanner or pliers
- 9.0 mm H7 hand reamer
- M3 tap
- PH1 screwdriver
- arbor press
- caliper with depth rod
- cyanoacrylate glue
- depth gauge
- feeler gauge or paper strip
- feeler gauges 0.05-0.5
- flat block
- retaining compound 638
- servo and controller
- soldering iron with an M3 insert tip, set to about 220 C
- thread-locker 243
- torque screwdriver
- tweezers

## Steps

### Prepare the printed parts

**Step 1. Clamp the housing and front plate together and line-ream the pin holes**

- Where: on the bench, away from the arm.
- Parts: housing, front plate.
- Fasteners: 3 x M3x16 plate screws, snug, to clamp the front plate to the housing; take them out again after reaming.
- Tools: 3.0 mm H7 hand reamer, 3.0 mm pin gauge.
- Check: Ream 3.0 H7 from the mid-plate back face through into the 1.5 mm blind holes in the front plate. A 3.0 pin gauge goes in to the bottom of both holes. Mark the pair.
- Note: Reaming the two parts together keeps the two pins parallel. The housing and front plate stay a matched pair.

**Step 2. Ream the boss-web bore 9.0 H7**

- Where: on the bench, away from the arm.
- Parts: housing.
- Fasteners: none.
- Tools: 9.0 mm H7 hand reamer.
- Check: Ream from behind through the cradle pocket. The servo output boss drops into the bore by hand.
- Note: Test with the servo boss now, while the housing is still empty. The web is only 1.6 mm thick, spans about 40 mm and prints on supports: clear the support from both faces first, then turn the reamer slowly with light feed and back it out turning forward; a reamer that grabs tears the web out. Print a spare housing if the web cracks.

**Step 3. Ream the four peg holes 3.0 H7**

- Where: on the bench, away from the arm.
- Parts: housing, wrist plate.
- Fasteners: none.
- Tools: 3.0 mm H7 hand reamer, 3.0 mm pin gauge.
- Check: Two deck peg holes in the housing and two spider peg holes in the wrist plate, each takes the 3.0 pin gauge.

**Step 4. Ream both knuckle bores 6.0 H7 and press in the bushes**

- Where: on the bench, away from the arm.
- Parts: knuckle A, knuckle B.
- Fastener items: bush a, bush b.
- Fasteners: 2 x sintered bronze plain bush 3 x 6 x 10, pressed in with the arbor press until neither end stands proud of a hub face (centred: 0.25 mm below each face of the 10.5 mm hub).
- Tools: 6.0 mm H7 hand reamer, arbor press, 3.0 mm pin gauge, 0-25 mm micrometer.
- Check: Pin-gauge each pressed bore, then measure the two ISO 2338 h8 3 x 16 pins with the micrometer and pair each pin with a bore for 0.000-0.020 mm clearance.
- Note: Pairing the pins to the bores is done once here, so mark which pin goes to which knuckle. The shims bear on the hub faces, so a bush end standing proud would set the end play instead: check both faces with a straight edge.

**Step 5. Tap the two dog holes in the horn**

- Where: on the bench, away from the arm.
- Fasteners: none; skip if the horn already has them.
- Tools: M3 tap, 2.5 mm drill.
- Check: Two M3 holes at r 7 mm, plus and minus 90 degrees from the horn arm line; an M3 screw runs in by hand.
- Note: Drill and tap by hand, square to the horn face.

### Wrist plate on the arm

**Step 6. Heat-set four inserts into the wrist plate**

- Where: on the bench, away from the arm.
- Parts: wrist plate.
- Fastener items: insert 1, insert 2, insert 3, insert 4.
- Fasteners: 4 x M3 brass heat-set insert 4.2 x 3.5, pressed in from the underside of the spider.
- Tools: soldering iron with an M3 insert tip, set to about 220 C, flat block.
- Check: Each insert sits flush with the underside of the plate and square to it. Let the plastic cool before screwing into it.
- Note: PETG melts around 220 C, so keep the iron on each insert only as long as it takes to push it flush.

**Step 7. Bond the two locating pins into the spider holes**

- Where: on the bench, away from the arm.
- Fastener items: locpin 1, locpin 2.
- Fasteners: 2 x ISO 2338 h8 3 x 6 locating pin, retaining compound 638, 2.5 mm standing proud.
- Tools: retaining compound 638, depth gauge.
- Check: Both pins stand 2.5 mm proud of the spider underside and square to it. Leave the compound to cure.
- Note: Bond them before the wrist plate goes on the arm. The deck holes take the pins later with a sliding fit.

**Step 8. Measure the horn hole depth, then seat the wrist plate on the horn**

- Where: this joins the bench sub-assembly to the gripper on the arm.
- Parts: wrist plate.
- Fastener items: insert 1, insert 2, insert 3, insert 4, locpin 1, locpin 2.
- Fasteners: none until the next step.
- Tools: caliper with depth rod.
- Check: Measure the horn hole depth (DB M15) and pick the screw length with wrist_mount.horn_screw_rule: M3x6 needs 3.75 mm or more, 3.5 to 3.7 is marginal, less means drill and re-tap. The four counterbores line up with the four horn holes.
- Note: The horn belongs to the SO-101 arm and is not in the bill of materials.

**Step 9. Fit the four horn screws**

- Fastener items: horn screw 1, horn screw 2, horn screw 3, horn screw 4.
- Fasteners: 4 x M3x6 ISO 7045 pan head into the SO-101 aluminium horn (length per the measured depth), about 0.6 N m (assumed).
- Tools: PH1 screwdriver, torque screwdriver.
- Check: All four heads seat in the counterbores and the plate does not rock. Stop if a screw bottoms before the plate clamps.
- Note: This is the only time the horn screws are easy to reach. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

### Servo and housing

**Step 10. Press four limiter sleeves into the seat holes**

- Where: on the bench, away from the arm.
- Parts: housing.
- Fastener items: limiter 1, limiter 2, limiter 3, limiter 4.
- Fasteners: 4 x compression limiter 5.0 x 3.2 x 2.55, from the frame front face.
- Tools: flat block.
- Check: Each sleeve sits flush in its seat hole, 2.55 mm long.
- Note: The sleeves take the clamp load of the ear screws so the printed seat does not creep.

**Step 11. Power the servo to the jaw-0 pulse**

- Where: on the bench, away from the arm.
- Fasteners: none.
- Tools: servo and controller.
- Check: The servo is on the jaw-0 pulse (the CAD closed pose) and stays powered until the horn is on.
- Note: The horn goes on in the next step at this angle, so the dog slots land at jaw angle 0.

**Step 12. Slide the horn in from below under the arc slots**

- Where: on the bench, away from the arm.
- Parts: servo horn.
- Fasteners: 1 x M3x6 ISO 7380 button head centre screw, loose in the horn for now.
- Tools: none.
- Check: The horn sits between the boss web and the mid plate and its two tapped holes are under the two arc slots.
- Note: Slide the horn from below, +Y, with the centre screw already in it.

**Step 13. Slide the servo in from behind and drive the centre screw**

- Where: on the bench, away from the arm.
- Parts: servo.
- Fasteners: the M3x6 ISO 7380 centre screw, driven through the pin A bore.
- Tools: 2.0 mm hex key.
- Check: The boss is in the web bore and the spline is in the horn. The hex key goes through the pin A bore into the centre screw while you hold the servo up.
- Note: Pin A is not in yet. It goes in at step 16 because the hex key uses its bore.

**Step 14. Fit the four ear screws with washers and nuts**

- Where: on the bench, away from the arm.
- Fastener items: ear screw 1, ear screw 2, ear screw 3, ear screw 4, washer 1, washer 2, washer 3, washer 4, nut 1, nut 2, nut 3, nut 4.
- Fasteners: 4 x M3x10 ISO 7045 from the ear side, washer + nut on the frame front face in the end-wall notches, about 0.4 N m (assumed).
- Tools: PH1 screwdriver, 7 mm spanner or pliers.
- Check: The ears are pulled flat against the sleeves and the servo does not move when pushed by hand.
- Note: Slide each washer and nut in sideways from the outboard end into its notch (they cannot come straight down past the end wall), then hold the nut while its screw turns. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

**Step 15. Fit the two dog set screws through the arc slots**

- Where: on the bench, away from the arm.
- Fastener items: dog screw 1, dog screw 2.
- Fasteners: 2 x M3x10 ISO 4026 socket set screw, thread-locker 243, from the front through the mid-plate arc slots into the horn.
- Tools: 1.5 mm hex key, thread-locker 243.
- Check: Each screw top stands 4.0 mm in front of the mid-plate front face.
- Note: They carry the drive to knuckle A. Do not over-tighten into the aluminium. They are not strong enough to carry a full stall on one dog (README, Dog coupling): keep the interim limit there until the coupling is fixed.

**Step 16. Press the two h8 pins in from the front**

- Where: on the bench, away from the arm.
- Parts: housing.
- Fastener items: pin a, pin b.
- Fasteners: 2 x ISO 2338 h8 3 x 16, retaining compound 638, pressed in until 0.5 mm short of the mid-plate back face.
- Tools: arbor press, retaining compound 638.
- Check: Both pins stand 14.0 mm proud of datum D and square to the mid plate.
- Note: Pin A goes in only after step 13, because the hex key uses its bore. Use each pin with the bore it was paired with. Service: pin A is bonded and its back end faces the horn, so it can only be driven out backwards after the servo and the horn come off (steps 13 and 12 in reverse); pin B can be driven out backwards at any time.

### Housing onto the wrist plate

**Step 17. Lift the housing up onto the wrist plate**

- Where: this joins the bench sub-assembly to the gripper on the arm.
- Parts: housing.
- Fasteners: none until the next step.
- Tools: none.
- Check: The locating pins go into the deck holes, the deck lies flat against the underside of the wrist plate and the four deck holes sit over the inserts.
- Note: The servo, horn and all the fasteners fitted so far come up with the housing.

**Step 18. Fit the four deck screws**

- Fastener items: deck screw 1, deck screw 2, deck screw 3, deck screw 4.
- Fasteners: 4 x M3x6 ISO 7045 pan head up through the deck into the heat-set inserts, about 0.5 N m (assumed).
- Tools: PH1 screwdriver, torque screwdriver.
- Check: The deck is tight against the wrist plate with no gap at any of the four screws.
- Note: All four deck screws have at least 40 mm of free driver length from below. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

### Pins, knuckles and front plate

**Step 19. Slip the two back shims onto the pins**

- Fastener items: shim a back, shim b back.
- Fasteners: 2 x shim washer 3.2 x 7 x 0.85, one per pin, against the mid plate; it bears on the knuckle hub face, not on the bush.
- Tools: tweezers.
- Check: Each shim spins freely on its pin.

**Step 20. Fit knuckle A with its bush onto pin A**

- Where: this joins the bench sub-assembly to the gripper on the arm.
- Parts: knuckle A.
- Fasteners: none; the bush was pressed in at step 4.
- Tools: none.
- Check: The knuckle turns smoothly on the pin and the two dog slots sit on the two set screws at jaw angle 0.
- Note: Hold the knuckle at jaw angle 0 so the dog slots line up with the set screws.

**Step 21. Fit knuckle B with its bush onto pin B**

- Where: this joins the bench sub-assembly to the gripper on the arm.
- Parts: knuckle B.
- Fasteners: none; the bush was pressed in at step 4.
- Tools: none.
- Check: The two gear sectors mesh with no visible gap at jaw angle 0 and both knuckles still turn on their pins.
- Note: Drop knuckle B straight down while the gears are at jaw angle 0 so the teeth find each other.

**Step 22. Pick and slip on the two front shims**

- Fastener items: shim a front, shim b front.
- Fasteners: 2 x shim washer 3.2 x 7, one per pin, picked from the 0.05 mm step assortment (0.85 nominal: plate gap 12.5 - hub 10.5 - 2 x 0.85 = 0.3).
- Tools: feeler gauges 0.05-0.5, tweezers.
- Check: End play of each knuckle is 0.3 mm plus or minus 0.05 mm, measured with the feeler gauges.
- Note: Change the shim thickness until each pin is in range.

**Step 23. Press the front plate onto the pins and standoffs**

- Where: this joins the bench sub-assembly to the gripper on the arm.
- Parts: front plate.
- Fasteners: none until the next step; the pin ends go 1.5 mm into the blind holes.
- Tools: none.
- Check: The plate sits on all three standoffs and the knuckles still turn freely.
- Note: Use the matched front plate from step 1. Do not tilt it; start both pins together.

**Step 24. Fit the three front plate screws**

- Fastener items: plate screw 1, plate screw 2, plate screw 3.
- Fasteners: 3 x M3x16, self-tapping into the 2.5 mm pilot in each standoff, about 0.3 N m (assumed).
- Tools: PH1 screwdriver, torque screwdriver.
- Check: The plate is tight on the standoffs and the gears still turn by hand through the servo.
- Note: These cut their own thread in PETG, so stop at first snug. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

### Fingers and pads

**Step 25. Slide finger A up into the root block of knuckle A**

- Parts: finger A.
- Fasteners: none until the next step.
- Tools: none.
- Check: The root tab sits between the two cheeks against the web and its peg holes line up with the cheek holes.

**Step 26. Pin finger A with two dowels and an M2 bolt**

- Fastener items: peg a 1, peg a 2, m2 a.
- Fasteners: 2 x dowel pin 2 x 24 (6 mm apart), 1 x M2x30 with nut, about 0.2 N m (assumed).
- Tools: 1.5 mm hex key, tweezers.
- Check: The finger cannot slide out of the block and the bolt is snug without crushing the cheeks.
- Note: The CAD shows only a plain shank, so head and nut sides are assumed: head on the back, nut on the front end. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

**Step 27. Slide finger B up into the root block of knuckle B**

- Parts: finger B.
- Fasteners: none until the next step.
- Tools: none.
- Check: The root tab sits between the two cheeks against the web and its peg holes line up with the cheek holes.

**Step 28. Pin finger B with two dowels and an M2 bolt**

- Fastener items: peg b 1, peg b 2, m2 b.
- Fasteners: 2 x dowel pin 2 x 24 (6 mm apart), 1 x M2x30 with nut, about 0.2 N m (assumed).
- Tools: 1.5 mm hex key, tweezers.
- Check: The finger cannot slide out of the block.
- Note: Same as finger A. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

**Step 29. Open the jaw 20 degrees and bond the FSR backing and the FSR on finger B**

- Parts: FSR backing, FSR 402 sensor.
- Fasteners: cyanoacrylate glue, thin film on the pad face; a dot of glue at the sensor head only.
- Tools: cyanoacrylate glue, servo and controller, tweezers.
- Jaw angle: 20 degrees open.
- Check: The backing sits flat on the pad with its pocket facing the jaw centre, tight to the tip edge. The FSR head lies flat in the pocket and the tail leaves through the tail slot without a sharp bend.
- Note: The jaw must be open at 20 degrees for steps 29 to 31: with the jaw closed the pad gap is only 4.45 mm and the stack on one finger blocks the other. Drive the jaw with the servo; never turn it by hand.

**Step 30. Bond the puck onto the FSR active area**

- Parts: FSR puck.
- Fasteners: cyanoacrylate glue, one small drop.
- Tools: cyanoacrylate glue, tweezers.
- Jaw angle: 20 degrees open.
- Check: The puck is centred inside the printed circle of the active area and does not touch the backing edge.

**Step 31. Bond the nail onto the pad of finger A**

- Parts: nail.
- Fasteners: cyanoacrylate glue, thin film.
- Tools: cyanoacrylate glue.
- Jaw angle: 20 degrees open.
- Check: The nail sits flat on the pad face at the tip edge and faces the puck.

**Step 32. Close the jaw, check the gap and travel, then calibrate the pinch point**

- Fasteners: none.
- Tools: servo and controller, feeler gauge or paper strip.
- Check: At jaw angle 0 the rigid faces are 1.0 mm apart at the contact height. Run the jaw from -11 to +20 degrees and check that nothing rubs. Then do the one-time pinch-point TCP calibration (tolerance row 5).
- Note: Jaw angle 0 is the CAD closed pose. Every part is now back at its CAD position.

## Findings

Numbers come from the CAD meshes: every insertion path is sampled every 0.5 mm against the parts already installed, and a driver ray is cast from every screw head outward. A free driver length of about 40 mm is wanted for a screw.

### Risks

- Step 8. The horn screw length is not confirmed against the real horn hole depth. The SO-101 horn is not modelled; measure the hole depth (DB M15) and apply wrist_mount.horn_screw_rule: M3x6 needs 3.75 mm or more, 3.5 to 3.7 is marginal, less means re-tap.
- Step 9. All 4 horn screws are trapped behind the deck once the housing is on, so removing the gripper from the arm means taking the housing off the wrist plate first. Driver clear 3.6 mm against 40 mm wanted, first hit housing.
- Step 13. The 25-tooth spline moves the horn in coarse steps, so the dog slots will not land exactly at the screw angle without driving the servo. Spline step 14.4 deg (up to 7.2 deg off); the dog arc slots reach -16 to +25 deg against a jaw range of -11 to +20 deg, a margin of only 5 deg at the closing end.
- Step 15. dog screw 1 is hard to reach for service once the gripper is built. Clear 0.5 mm along [0.0, 0.0, 1.0] (hit knuckle_a).
- Step 15. dog screw 2 is hard to reach for service once the gripper is built. Clear 0.5 mm along [0.0, 0.0, 1.0] (hit knuckle_a).
- Step 31. The nail and the FSR stack can only be bonded with the jaw open; the jaw must be driven by the servo. With the jaw closed the nail path along -X runs into FSR 402 sensor, FSR backing, FSR puck, finger B; the closed gap between the finger pads is 4.45 mm and already holds the nail, the FSR stack and a 1.0 mm running gap.

### Notes

- Step 1. The housing and front plate are a matched pair. Pin holes are line-reamed together; replacing either plate means reaming again.
- Step 6. The insert bore in the CAD equals the insert diameter, so the model shows no melt-in interference. Bore 4.2 mm = insert outer diameter 4.2 mm, depth 3.5 mm; printed holes run about 0.25 mm small, so test an insert in a coupon.
- Step 7. The locating pins go into the spider holes from below (travel +Y), not along -Y. The spider holes are blind and open on the underside, so a -Y path would run through solid plate; the pin is 6.0 mm long and stands 2.5 mm proud.
- Step 12. The horn centre screw (M3x6 ISO 7380) is not in the CAD, so its path is not swept; its head must sit in the horn's counterbored centre, at most 0.4 mm proud, because the mid plate is 0.5 mm above the horn face. It is driven with a 2.0 mm hex key through the pin A bore at step 13; the bore is 3 mm and pin A is not yet fitted.
- Step 13. The servo boss and the boss-web bore touch in the CAD. 4.5 mm3 overlap: nominal 9.0 mm boss in the 9.0 mm bore, which is reamed H7 at step 2.
- Step 15. The dog set screws are screwed in from the front through the mid-plate arc slots, before the gears go on. Set screw tops at z 4.0; the knuckle A dog slots (3.4 mm wide) take them at jaw angle 0.
- Step 16. Pin A can only go in after the servo is fitted and the horn centre screw is driven, because the 2.0 mm hex key uses the pin A bore. Pin 16.0 mm long, z -2.0 to 14.0, bottom 0.5 mm from the mid-plate back face z -2.5; pressed in from the front with retaining compound, with 1.5 mm in the front-plate blind hole.
- Step 23. The front plate camera pad has two insert bores for the optional wrist camera. 2 x 4.2 mm bore, 4.5 mm deep, 8.1 mm apart; BOM line 'Camera-pad inserts (optional)'. Leave them empty unless the wrist camera is built.
- Step 24. The front plate screws cut their own thread in a 2.5 mm pilot; stop at first snug (torque-limited driver, RISK F45). Thread-forming overlap 27.9 mm3 per screw; CAD length 17.8 mm including a 1.8 mm head, so 16.0 mm of shank against 16 mm listed.
- Step 26. The finger pegs in the CAD are the hole tool, 1 mm longer each side than the 2 x 24 dowel the BOM lists (block width 24). CAD peg 26.0 mm long across both cheeks; a 2 x 24 dowel sits flush with both cheek faces; the M2x30 bolt covers 24 mm of block plus a 1.6 mm nut (RISK F48).

## Driver access

The heat-set inserts are left out: the iron tip has 300 mm or more of free length on the bench.

| Fastener | Driver direction | Free length when fitted, mm | Free length when built, mm | Enough |
|---|---|---:|---:|---|
| horn screw 1 | -Y | 300 or more | 3.6 | yes |
| horn screw 2 | -Y | 300 or more | 3.6 | yes |
| horn screw 3 | -Y | 300 or more | 3.6 | yes |
| horn screw 4 | -Y | 300 or more | 3.6 | yes |
| ear screw 1 | -Z | 300 or more | 300 or more | yes |
| ear screw 2 | -Z | 300 or more | 300 or more | yes |
| ear screw 3 | -Z | 300 or more | 300 or more | yes |
| ear screw 4 | -Z | 300 or more | 300 or more | yes |
| dog screw 1 | +Z | 300 or more | 0.5 | yes |
| dog screw 2 | +Z | 300 or more | 0.5 | yes |
| deck screw 1 | -Y | 300 or more | 300 or more | yes |
| deck screw 2 | -Y | 300 or more | 300 or more | yes |
| deck screw 3 | -Y | 300 or more | 300 or more | yes |
| deck screw 4 | -Y | 300 or more | 300 or more | yes |
| plate screw 1 | +Z | 300 or more | 300 or more | yes |
| plate screw 2 | +Z | 300 or more | 300 or more | yes |
| plate screw 3 | +Z | 300 or more | 300 or more | yes |
| m2 a | -Z | 300 or more | 300 or more | yes |
| m2 b | -Z | 300 or more | 300 or more | yes |

## What this plan does not settle

- Torques, thread-locker and the shim and pin press forces are assumed, not measured.
- The SO-101 horn is not modelled, so its hole depth and the horn screw engagement are untested.
- The horn centre screw and the nuts on the M2 bolts are not in the CAD.
- Servo wiring, the FSR tail route and the nut on each M2 bolt are not in the CAD.
- Gear mesh timing is checked only at jaw angle 0, where the CAD says the sectors clear.
