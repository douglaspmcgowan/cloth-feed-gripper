# Cloth-feed gripper assembly

This guide builds the ME102B cloth-feed gripper from the printed parts and the bill of materials in cad/gripper/drawings/BOM.md. It follows the CAD in cad/gripper, and the data behind it is in cad/gripper/assembly/steps.json. Every torque below is an assumed starting value, not a measured one.

Directions use the CAD frame: X is the jaw closing direction, Y points up to the wrist and Z comes out of the gear plane. Jaw angle 0 is the closed pose; positive angles open the jaw.

## How the build goes

The wrist plate goes on the SO-101 roll horn first, and the housing comes up onto it afterwards. Pressing work is done on the bench so the arm never takes a hammer blow. Steps 22 to 25 need the servo powered to hold the jaw open.

- Prepare the printed parts (step 1).
- Wrist plate on the arm (steps 2 to 4). Built on the bench, then joined.
- Housing on the wrist plate (steps 5 to 7). Built on the bench, then joined.
- Servo unit into the cradle (steps 8 to 11). Built on the bench, then joined.
- Pins, knuckles and front plate (steps 12 to 17).
- Fingers and pads (steps 18 to 26).

## Tools and consumables

- 1.5 mm hex key
- 2.5 mm hex key
- 3 mm hand reamer
- PH1 screwdriver
- arbor press
- cyanoacrylate glue
- feeler gauge or paper strip
- flat block
- flat support block
- marker
- needle-nose pliers
- servo and controller
- soldering iron with an M3 insert tip, set to about 220 C
- torque screwdriver
- tweezers

## Steps

### Prepare the printed parts

**Step 1. Line-ream the pin bores through the housing and front plate together**

- Fasteners: none; clamp the front plate to the housing with the three M3x16 screws, ream, then take the screws out again.
- Tools: 3 mm hand reamer, marker.
- Check: A 3 m6 dowel pin starts into both bores by hand. Mark the housing and front plate as a matched pair.
- Note: Done on the bench before anything else. The CAD bores are 2.9 mm and the pins are pressed, so the pair is reamed together to keep the two pivots parallel.

### Wrist plate on the arm

**Step 2. Heat-set four inserts into the wrist plate**

- Where: on the bench, away from the arm.
- Parts: wrist plate.
- Fastener items: insert 1, insert 2, insert 3, insert 4.
- Fasteners: 4 x M3 heat-set insert 4.2x3.5, pressed in from the underside of the spider arms.
- Tools: soldering iron with an M3 insert tip, set to about 220 C, flat block.
- Check: Each insert sits flush with the underside of the plate and square to it. Let the plastic cool before screwing into it.
- Note: PETG melts around 220 C, so keep the iron on each insert only as long as it takes to push it flush.

**Step 3. Seat the wrist plate on the SO-101 roll horn**

- Where: this joins the bench sub-assembly to the gripper on the arm.
- Parts: wrist plate.
- Fastener items: insert 1, insert 2, insert 3, insert 4.
- Fasteners: none until the next step.
- Tools: none.
- Check: The horn sits in the recess of the plate and the four counterbores line up with the four horn holes.
- Note: The wrist plate goes on the horn first; the housing comes up onto it afterwards. The horn belongs to the SO-101 arm and is not in this bill of materials.

**Step 4. Fit the four horn screws**

- Fastener items: horn screw 1, horn screw 2, horn screw 3, horn screw 4.
- Fasteners: 4 x M3x6 pan head into the SO-101 aluminium horn, about 0.6 N m (assumed), thread-locker none.
- Tools: PH1 screwdriver, torque screwdriver.
- Check: All four heads seat in the counterbores and the plate does not rock. Stop if a screw bottoms before the plate clamps.
- Note: This is the only time the horn screws are easy to reach. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

### Housing on the wrist plate

**Step 5. Press the two dowel pins into the housing**

- Where: on the bench, away from the arm.
- Parts: housing.
- Fastener items: pin a, pin b.
- Fasteners: 2 x dowel pin 3 m6 x 15, pressed 2.5 mm into the mid plate until the pin end is flush with its back face.
- Tools: arbor press, flat support block.
- Check: Both pins stand square to the mid plate and stick out 12.5 mm on the gear side.
- Note: Pressing on the bench keeps the shock off the arm. Support the mid plate from behind.

**Step 6. Lift the housing with its pins up onto the wrist plate**

- Where: this joins the bench sub-assembly to the gripper on the arm.
- Parts: housing.
- Fastener items: pin a, pin b.
- Fasteners: none until the next step.
- Tools: none.
- Check: The deck lies flat against the underside of the wrist plate and the four deck holes sit over the inserts.

**Step 7. Fit the four deck screws**

- Fastener items: deck screw 1, deck screw 2, deck screw 3, deck screw 4.
- Fasteners: 4 x M3x6 pan head up through the deck into the heat-set inserts, about 0.5 N m (assumed), thread-locker none.
- Tools: PH1 screwdriver, torque screwdriver.
- Check: The deck is tight against the wrist plate with no gap at any of the four screws.
- Note: As drawn, deck screw 1, deck screw 2, deck screw 3 cannot be fitted straight from below; see the findings. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

### Servo unit into the cradle

**Step 8. Press the horn onto the servo spline**

- Where: on the bench, away from the arm.
- Parts: servo, servo horn.
- Fasteners: none; use the centre screw that ships with the servo.
- Tools: none.
- Check: The horn bottom sits 1.0 mm above the servo case top.

**Step 9. Fit the two dog pins into the horn**

- Where: on the bench, away from the arm.
- Fastener items: dog pin 1, dog pin 2.
- Fasteners: 2 x pin standing 7.2 mm proud of the horn face, low-strength thread-locker (assumed). The BOM lists M3x8 socket screws, which cannot do this; assumed here: M3x10 headless screws threaded in from the front face (see the findings).
- Tools: 2.5 mm hex key.
- Check: Both pins stand square to the horn face, 14 mm apart across the shaft, with 7.2 mm showing.

**Step 10. Slide the servo unit up into the cradle**

- Where: this joins the bench sub-assembly to the gripper on the arm.
- Parts: servo, servo horn.
- Fastener items: dog pin 1, dog pin 2.
- Fasteners: none until the next step.
- Tools: none.
- Check: The servo ears rest flat under the seat frame, the horn is 0.5 mm below the mid plate and both dog pins stand in the arc slots.
- Note: Before this step, power the servo and set the horn to the angle where the dog pins sit at the middle of their arc slots (jaw angle 0). Keep the servo lead clear of the horn.

**Step 11. Fit the four servo ear screws and nuts**

- Fastener items: ear screw 1, ear screw 2, ear screw 3, ear screw 4.
- Fasteners: 4 x M3x10 with nut through the servo ears and the seat frame, nut on top of the frame, about 0.4 N m (assumed).
- Tools: PH1 screwdriver, needle-nose pliers.
- Check: The ears are pulled flat against the frame and the servo does not move when pushed by hand.
- Note: The nuts are not captured in a pocket, so hold each one while its screw turns. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

### Pins, knuckles and front plate

**Step 12. Slip the two back shims onto the pins**

- Fastener items: shim a back, shim b back.
- Fasteners: 2 x shim washer 3.2x6x0.85, one per pin, against the mid plate.
- Tools: tweezers.
- Check: Each shim spins freely on its pin.

**Step 13. Fit knuckle A with its bronze sleeve onto pin A**

- Parts: knuckle A.
- Fastener items: sleeve a.
- Fasteners: 1 x sintered bronze sleeve 3x5x8, pressed into the knuckle bore beforehand.
- Tools: arbor press.
- Check: The knuckle turns smoothly on the pin and both dog pins sit in the slots on its back face.
- Note: Press the sleeve into the knuckle on the bench first. Hold the knuckle at jaw angle 0 so the dog slots line up with the pins.

**Step 14. Fit knuckle B with its bronze sleeve onto pin B**

- Parts: knuckle B.
- Fastener items: sleeve b.
- Fasteners: 1 x sintered bronze sleeve 3x5x8, pressed into the knuckle bore beforehand.
- Tools: arbor press.
- Check: The two gear sectors mesh with no visible gap at jaw angle 0 and both knuckles still turn on their pins.
- Note: Drop knuckle B straight down while the gears are at jaw angle 0 so the teeth find each other.

**Step 15. Slip the two front shims onto the pins**

- Fastener items: shim a front, shim b front.
- Fasteners: 2 x shim washer 3.2x6x0.85, one per pin, on top of each knuckle.
- Tools: tweezers.
- Check: Each shim spins freely and the knuckles still turn.

**Step 16. Press the front plate onto the pins and standoffs**

- Parts: front plate.
- Fasteners: none until the next step; the pin ends press 2.5 mm into the plate.
- Tools: none.
- Check: The plate sits on all three standoffs and the knuckles still turn freely with about 0.3 mm of end play.
- Note: Use the matched front plate from step 1. Do not tilt it; start both pins together.

**Step 17. Fit the three front plate screws**

- Fastener items: plate screw 1, plate screw 2, plate screw 3.
- Fasteners: 3 x M3x16, self-tapping into the 2.5 mm pilot in each standoff, about 0.3 N m (assumed).
- Tools: PH1 screwdriver, torque screwdriver.
- Check: The plate is tight on the standoffs and the gears still turn by hand through the servo.
- Note: These cut their own thread in PETG, so stop at first snug. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

### Fingers and pads

**Step 18. Slide finger A up into the root block of knuckle A**

- Parts: finger A.
- Fasteners: none until the next step.
- Tools: none.
- Check: The root tab sits between the two cheeks against the web and its peg holes line up with the cheek holes.

**Step 19. Pin finger A with two dowels and an M2 bolt**

- Fastener items: peg a 1, peg a 2, m2 a.
- Fasteners: 2 x dowel 2 x 24, 1 x M2x25 with nut, about 0.2 N m (assumed).
- Tools: 1.5 mm hex key, tweezers.
- Check: The finger cannot slide out of the block and the bolt is snug without crushing the cheeks.
- Note: The CAD shows only a plain shank, so head and nut sides are assumed: head on the back, nut on the front end. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

**Step 20. Slide finger B up into the root block of knuckle B**

- Parts: finger B.
- Fasteners: none until the next step.
- Tools: none.
- Check: The root tab sits between the two cheeks against the web and its peg holes line up with the cheek holes.

**Step 21. Pin finger B with two dowels and an M2 bolt**

- Fastener items: peg b 1, peg b 2, m2 b.
- Fasteners: 2 x dowel 2 x 24, 1 x M2x25 with nut, about 0.2 N m (assumed).
- Tools: 1.5 mm hex key, tweezers.
- Check: The finger cannot slide out of the block.
- Note: Same as finger A. Torques are assumed starting values, not measured; stop at the first sign of a stripped thread.

**Step 22. Bond the FSR backing to the pad of finger B with the jaw open**

- Parts: FSR backing.
- Fasteners: cyanoacrylate glue, thin film on the pad face.
- Tools: cyanoacrylate glue, servo and controller.
- Jaw angle: 20 degrees open.
- Check: The backing sits flat on the pad with its pocket facing the jaw centre, tight to the tip edge.
- Note: The jaw must be open at 20 degrees for steps 22 to 25: with the jaw closed the pad gap is only 4.45 mm and the stack on one finger blocks the other. Drive the jaw with the servo; never turn it by hand.

**Step 23. Drop the FSR 402 into the backing pocket**

- Parts: FSR 402 sensor.
- Fasteners: double-sided tape or a dot of glue at the head only.
- Tools: tweezers.
- Jaw angle: 20 degrees open.
- Check: The round head lies flat in the pocket and the tail runs out through the tail slot without a sharp bend.

**Step 24. Bond the puck onto the FSR active area**

- Parts: FSR puck.
- Fasteners: cyanoacrylate glue, one small drop.
- Tools: cyanoacrylate glue, tweezers.
- Jaw angle: 20 degrees open.
- Check: The puck is centred inside the printed circle of the active area and does not touch the backing edge.

**Step 25. Bond the nail onto the pad of finger A**

- Parts: nail.
- Fasteners: cyanoacrylate glue, thin film.
- Tools: cyanoacrylate glue.
- Jaw angle: 20 degrees open.
- Check: The nail sits flat on the pad face at the tip edge and faces the puck.

**Step 26. Close the jaw and check the gap and the travel**

- Fasteners: none.
- Tools: servo and controller, feeler gauge or paper strip.
- Check: At jaw angle 0 the nail and puck faces are 1.0 mm apart and parallel. Run the jaw from -11 to +20 degrees and check that nothing rubs.
- Note: Jaw angle 0 is the CAD closed pose. Every part is now back at its CAD position.

## Findings

Numbers come from the CAD meshes: every insertion path is sampled every 0.5 mm against the parts already installed, and a driver ray is cast from every screw head outward. A free driver length of about 40 mm is wanted for a screw.

### Blockers

- Step 7. Deck screw 1 at x -29.0, z 6.0 cannot be fitted straight from below as drawn. On the way in it first touches the housing 7.5 mm before the seat (overlap up to 8.8 mm3 at x -27.1 to -26.3, y 10.6 to 11.5, z 4.0 to 8.0); the driver has 1.3 mm of free length against 40 mm wanted (blocked by the housing); the diameter 6.0 mm standoff at x -24.5, y 13.0 reaches x -27.50 while the screw head reaches x -26.25.
- Step 7. Deck screw 2 at x 29.0, z 6.0 cannot be fitted straight from below as drawn. On the way in it first touches the housing 7.5 mm before the seat (overlap up to 8.8 mm3 at x 26.3 to 27.1, y 10.6 to 11.5, z 4.0 to 8.0); the driver has 1.3 mm of free length against 40 mm wanted (blocked by the housing); the diameter 6.0 mm standoff at x 24.5, y 13.0 reaches x 27.50 while the screw head reaches x 26.25.
- Step 7. Deck screw 3 at x -29.0, z -13.5 cannot be fitted straight from below as drawn. On the way in it first touches the housing 10.0 mm before the seat (overlap up to 23.9 mm3 at x -31.6 to -26.3, y 6.6 to 15.0, z -16.2 to -11.7); seated, it overlaps the housing by 19.2 mm3; the driver has 9.8 mm of free length against 40 mm wanted (blocked by the housing); the screw head is 5.5 mm across.
- Step 9. The listed dog pin (M3x8 socket screw) cannot make the pin the CAD draws. CAD pin is 7.2 mm long, standing from z -3.0 to 4.2 above the 3.0 mm horn, so it needs about 10.2 mm of screw; M3x8 gives at most 5 mm proud. A socket head under the horn needs 3.0 mm but the horn sits 1.0 mm above the case top. With 5 mm proud the pin top would be at z 2.0, entering the 3.5 mm deep slot by only 1.0 mm.

### Risks

- Step 4. The horn screw length is not confirmed against the real horn hole depth. Tolerance study: CAD hole depth 2.5 mm, M3x6 through the 3.0 mm clamp bottoms by 0.5 mm, engagement 2.0 mm against 1.5 mm needed; measure the SO-101 horn hole depth before ordering.
- Step 7. All 4 horn screws are trapped behind the deck once the housing is on, so removing the gripper from the arm means taking the housing off the wrist plate first. Driver clear 3.6 mm against 40 mm wanted, first hit housing; the deck windows do not line up with all four screws and the gear sectors sit behind them.
- Step 10. The 25-tooth spline moves the horn in coarse steps, so the dog pins will not land exactly at the slot angle without driving the servo. Spline step 14.4 deg (up to 7.2 deg off); the dog pin arc slots reach -16 to +25 deg against a jaw range of -11 to +20 deg, a margin of only 5 deg at the closing end; the knuckle dog slot is 3.14 mm wide for a 3.0 mm pin.
- Step 25. The nail and the FSR stack can only be bonded with the jaw open; the jaw must be driven by the servo. With the jaw closed the nail path along -X runs into FSR 402 sensor, FSR backing, FSR puck, finger B; the closed gap between the finger pads is 4.45 mm and already holds the nail, the FSR stack and a 1.0 mm running gap.

### Notes

- Step 1. The housing and front plate are a matched pair. Pin bores are line-reamed together; replacing either plate means reaming again.
- Step 2. The insert bore in the CAD equals the insert diameter, so the model shows no melt-in interference. Bore 4.2 mm = insert outer diameter 4.2 mm, depth 3.5 mm; printed holes run about 0.25 mm small, so test an insert in a coupon.
- Step 5. The dowel pins are held by a 2.5 mm press fit in the mid plate and 2.5 mm in the front plate, and nothing else. Pin 3.0 mm in a 2.9 mm CAD bore, 1.16 mm3 of interference per plate; 2.5 of 15 mm engaged per end.
- Step 8. The servo horn centre screw is not in the BOM or the CAD. Horn bottom z -6.0, horn top z -3.0, pin A starts at z -2.5; use the screw that ships with the servo.
- Step 11. The servo model has no ear holes and the nuts are not drawn or captured, so the ear screws overlap the servo ears in the CAD and each nut must be held by hand. 17.7 mm3 overlap per screw (solid ears); nut sits on the seat frame at z -14.5 to -12.1, outside the end walls.
- Step 16. The front plate camera pad has two insert bores that no BOM line covers. 2 x 4.2 mm bore, 4.5 mm deep, 8.1 mm apart; the BOM lists only the 4 deck inserts. Leave them empty unless the wrist camera is built.
- Step 17. The front plate screws cut their own thread in a 2.5 mm pilot, and the CAD screw is shorter than the BOM length. Thread-forming overlap 22.6 mm3 per screw; CAD length 16.0 mm including a 2.4 mm head, so 13.6 mm of shank against 16 mm listed; a full 16 mm shank would end at z -3.5, 1.0 mm past the back face of the mid plate.
- Step 19. The finger pegs are shorter in the BOM than in the CAD. CAD peg 26.0 mm long across both cheeks, BOM lists 2 x 24, so each end sits 1.0 mm inside the cheek face; the M2 bolt is 26.0 mm in the CAD against M2x25.

## Driver access

The heat-set inserts are left out: the iron tip has 300 mm or more of free length on the bench.

| Fastener | Driver direction | Free length when fitted, mm | Free length when built, mm | Enough |
|---|---|---:|---:|---|
| horn screw 1 | -Y | 300 or more | 3.6 | yes |
| horn screw 2 | -Y | 300 or more | 3.6 | yes |
| horn screw 3 | -Y | 300 or more | 3.6 | yes |
| horn screw 4 | -Y | 300 or more | 3.6 | yes |
| deck screw 1 | -Y | 1.3 | 1.3 | no |
| deck screw 2 | -Y | 1.3 | 1.3 | no |
| deck screw 3 | -Y | 9.8 | 9.8 | no |
| deck screw 4 | -Y | 300 or more | 300 or more | yes |
| ear screw 1 | -Z | 300 or more | 300 or more | yes |
| ear screw 2 | -Z | 300 or more | 300 or more | yes |
| ear screw 3 | -Z | 300 or more | 300 or more | yes |
| ear screw 4 | -Z | 300 or more | 300 or more | yes |
| plate screw 1 | +Z | 300 or more | 300 or more | yes |
| plate screw 2 | +Z | 300 or more | 300 or more | yes |
| plate screw 3 | +Z | 300 or more | 300 or more | yes |
| m2 a | -Z | 300 or more | 300 or more | yes |
| m2 b | -Z | 300 or more | 300 or more | yes |

## What this plan does not settle

- Torques, thread-locker and the shim and pin press forces are assumed, not measured.
- The SO-101 horn is not modelled, so its hole depth and the horn screw engagement are untested.
- Servo wiring, the FSR tail route and the nut on each M2 bolt are not in the CAD.
- Gear mesh timing is checked only at jaw angle 0, where the CAD says the sectors clear.
