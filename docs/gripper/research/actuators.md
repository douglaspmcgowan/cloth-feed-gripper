# PWM actuator market scan (gripper, 2026-09-22)

Data: `actuators.csv` (35 rows: 27 PWM hobby servos `A..`, 8 PWM-driven DC gearmotors with encoders `M..`). All prices are USD, single unit, as listed on 2026-09-22. Every row is under $50.

## Method

- Scope from Douglas's 2026-09-22 ruling: PWM-controlled, <= $50, hand-sized, light. Course: >= 1 DC motor, >= 1 analog input.
- Prices and specs taken from vendor product pages that show a price (Adafruit, Pololu, SparkFun, ServoCity, Ready Made RC, Servos.net, BuddyRC, Maker Portal, NFP Shop, SpeedyFPV, MakerFocus, RCDrone, DFRobot). Datasheet PDFs read where public (DS3218 Miuzei and Annimos, DS3235, MG996R Handsontec).
- Amazon pages could not be read (no rendered price), so Amazon-only multipacks (Miuzei, Annimos, Stemedu, Wishiot) are covered through their datasheets, not their prices.
- The `provenance` column marks each row's numbers as sourced, derived, or assumed. Derived rules: kg·cm = oz·in x 0.0720; servo rpm-equivalent = 10 / (s per 60 deg); encoder counts at the output = motor CPR x gear ratio.
- Stock status is noted where the page said "out of stock" or "sold out" (A03, A05, A08, A14, A19, A20, A21, A26).
- Excluded: Power HD 1501MG (17 kg·cm @6 V, 60 g) is discontinued at Pololu ([Pololu #1057](https://www.pololu.com/product/1057)); no current price found.

## Spec reliability of cheap servos

- **Values differ between sources for the same part.** MG996R: TowerPro says 9.4/11 kg·cm and 0.19/0.15 s ([TowerPro PDF](https://www.electronicoscaldas.com/datasheet/MG996R_Tower-Pro.pdf)), Handsontec says 0.17/0.14 s and 4.8-7.2 V ([Handsontec](https://www.handsontec.com/dataspecs/motor_fan/MG996R.pdf)), Adafruit says 8.5/10 kg·cm ([Adafruit](https://www.adafruit.com/product/1142)). DS3218: stall current 2.2 A per [Miuzei](https://images-na.ssl-images-amazon.com/images/I/81Lbgu+nG6L.pdf) vs 1.8 A per [Annimos](https://cdck-file-uploads-europe1.s3.dualstack.eu-west-1.amazonaws.com/arduino/original/4X/7/4/f/74f50fff235673f3d7b2a23ae8b8d6e7f30a47f7.pdf). DS3235 listings give 60 g or 80 g. HS-311: 3.5 kg·cm @6 V per [BuddyRC](https://www.buddyrc.com/products/hitec-hs-311-standard-analog-sport-servo) vs 3.7 per [servodatabase](https://servodatabase.com/servo/hitec/hs-311).
- **Stall current spreads 8x in the micro class.** Hitec HS-5065MG lists 3 A @6 V ([ServoCity](https://www.servocity.com/hs-5065mg-servo/)); an MG90S clone lists 0.4 A @5 V ([Maker Portal](https://makersportal.com/shop/p/mg90s-micro-servo)). Size the supply for the brand figure.
- **"kg" names are stall figures at the top voltage.** DS3235 "35 kg" is 35 kg·cm at 7.4 V; at 6 V it is 32 ([datasheet](https://hajim.rochester.edu/me/sites/kelley/me240/DS3235-270_datasheet.pdf)). Assumed: plan on continuous holding torque of 30-50 % of stall, because a stalled servo draws its stall current and overheats. Pololu warns that stalling or back-driving damages hobby servos ([Pololu FS5106B-FB](https://www.pololu.com/product/3442)).
- **Pololu gearmotor stall torques are theoretical.** The gearbox limits instantaneous torque to 2.5 kg·cm for 380:1 and 1000:1, and 2 kg·cm for other ratios ([Pololu category](https://www.pololu.com/category/60/micro-metal-gearmotors)). The 11 kg·cm listed for 1000:1 is not usable.
- **Some figures are implausible.** 1 µs deadband on the analog SG-5010 (A14). 200 mA stall on the Adafruit N20 (M05). 170 mA "current rating" on DFRobot FIT0483 (M06). Bench-check them before use.
- **Travel depends on pulse width.** Many 180° servos give only 90-120° with 1-2 ms pulses. They need 0.5-2.5 ms, or 0.75-2.25 ms on Adafruit parts.
- Clones are common. Recommendation (assumed): buy one or two spares from the vendor whose page you cite, then measure stall current and torque with a lever arm and a scale.

## Course compliance: does a hobby servo count as a DC motor?

- **Not settled by public sources.** The public [EDG ME102B page](https://edg.berkeley.edu/course/me102b) states learning outcomes, such as "electromechanical actuators with drive electronics", but no project rules. The project spec lives on bCourses.
- A hobby servo does have a brushed DC motor inside, and coreless on the DS3235. But its drive electronics are sealed inside the servo, and the student sends it only a position pulse. Assumption: staff will not count a servo alone as "the DC motor", because the course teaches motor selection and H-bridge drive.
- **Low-risk route:** make the transmission DOF a PWM-driven DC gearmotor through an H-bridge, with encoder or pot feedback. Examples are M01-M03 (Pololu HPCB with 12 CPR encoder) plus a DRV8833-class driver. Alternatively, pair a servo with a separate DC motor.
- The feedback servos (A06-A13) meet the analog-input requirement by themselves: wire the pot wiper to an Arduino ADC pin. That also gives closed-jaw and contact detection.
- **Ask the ME102B GSI whether a hobby servo counts before buying.**

## Conflict with existing CAD

`cad/gripper/params.json` specifies a Feetech STS3215. That is a serial-bus servo, not a PWM servo, so it conflicts with the 2026-09-22 PWM ruling. The servo envelope in the CAD needs to change to the chosen part. Standard-size servos in this scan are about 40 x 20 x 38-43 mm, versus 45.2 x 24.7 x 35 mm in `params.json`.

## Shortlist (assumed ranking, pending grip-force sizing)

| Pick | Why |
|---|---|
| A11 FEETECH FT1117M-FB ($19.65, 22 g, 3.5 kg·cm) | Light, with analog feedback. Best mass-to-torque ratio among the documented feedback servos. |
| A12 FS5106B-FB ($25.64, 43 g, 6 kg·cm) / A13 FS5115M-FB ($35.77, 62 g, 15.5 kg·cm) | Standard size, with feedback, from a well-documented vendor. Pick whichever the torque budget needs. |
| A17 DS3218MG ($12.99, 58 g, 21.5 kg·cm @6.8 V) | Cheapest high torque. No feedback wire. Specs vary between sellers. |
| M02 Pololu 380:1 HPCB + encoder ($32.45, ~11 g) | The clean "DC motor" answer. 4550 counts per output revolution. Keep grip torque under the 2.5 kg·cm gearbox limit. |

## 2026-10-11 candidate extension

Why: the jaw needs 0.792 N·m (8.07 kg·cm) of hold torque at the shaft, and the current pick A17 holds only 3 % above that at the 40 % hold rule. This pass adds 14 rows (11 servos `A28`-`A38`, 3 gearmotors `M09`-`M11`) and 6 columns at the end of `actuators.csv` (46 columns, 52 rows). All prices and stock were read from public pages on 2026-10-11. All 14 meet R7 (PWM position servo or PWM-driven DC gearmotor, no serial bus, no continuous-rotation servo) and R8 (under $50; see the price column for the two UK-priced rows).

New columns: `spec_basis` (`datasheet` = a manufacturer document with the number; `vendor-listing` = only a retailer or product page gives it, no datasheet; `mixed`), `stall_current_at_V`, `retrieved_date`, and `recheck_price_usd` / `recheck_stock` / `recheck_source` (filled for the 10 existing rows A13, A16-A20, M01-M04 only). Every numeric cell is a bare number; caveats are in `notes`. Servo `no_load_speed_rpm` is derived as 10 / (s per 60°) at the high voltage.

### New rows

Stall torque is shown as kg·cm at each published voltage. The hold requirement is 8.07 kg·cm at the shaft, so stall torque needs to be well above that.

| id | Part | Price (USD) | Stall torque (kg·cm @ V) | Speed (s/60°) | Mass | Spline | Spec basis | Stock (2026-10-11) |
|---|---|---|---|---|---|---|---|---|
| A28 | goBILDA 2000 Series Dual Mode 25-2 Torque | 36.99 | 17.2 @ 4.8, 21.6 @ 6.0, 25.2 @ 7.4 | 0.25 @ 4.8, 0.17 @ 7.4 | 60 g | 25 tooth | vendor-listing (no PDF) | in stock (goBILDA) |
| A29 | goBILDA 2000 Series Dual Mode 25-3 Speed | 36.99 | 7.9 @ 4.8, 9.3 @ 6.0, 10.8 @ 7.4 | 0.11 @ 4.8, 0.07 @ 7.4 | 58 g | 25 tooth | vendor-listing (no PDF) | in stock (goBILDA) |
| A30 | REV Smart Robot Servo V2 Balanced, REV-41-3334 | 32.50 | 13.5 @ 6.0, 16.7 @ 7.4 | 0.14 @ 6.0, 0.12 @ 7.4 | 62 g | H25T (25 tooth) | mixed (page plus drawing PDF) | in stock (REV) |
| A31 | REV Smart Robot Servo V2 UltraSpeed, REV-41-3336 | 32.50 | 5.6 @ 6.0, 6.2 @ 7.4 | 0.043 @ 6.0, 0.035 @ 7.4 | 60 g | H25T (25 tooth) | mixed | in stock (REV) |
| A32 | DSServo DS3230 MG (Blue) | 27.00 | 26 @ 5.0, 30 @ 6.8 | 0.20 @ 5.0, 0.18 @ 6.8 | 60 g | not listed | vendor-listing | backordered (aifitlab) |
| A33 | DSServo DS3225 MG | 20.00 | 24.5 @ 5.0, 28 @ 6.8 | 0.16 @ 5.0, 0.14 @ 6.8 | 60 g | not listed | vendor-listing | backordered (aifitlab) |
| A34 | DSServo DS3235 SG (Blue) | 30.00 | 23 @ 5.0, 30 @ 7.4, 35 @ 8.4 | 0.18 @ 5.0, 0.11 @ 8.4 | 60 g | not listed | vendor-listing | backordered (aifitlab) |
| A35 | Hitec HS-645MG | 43.99 | 7.7 @ 4.8, 9.6 @ 6.0 | 0.24 @ 4.8, 0.20 @ 6.0 | 55.2 g | C24T | vendor-listing | in stock (ServoCity) |
| A36 | FEETECH FT5325M | not read (GBP 18.74) | 20.5 @ 6.0, 25 @ 7.4 | 0.185 @ 6.0, 0.151 @ 7.4 | 67 g | 25T | vendor-listing | "Only 5 left" (Maplin UK) |
| A37 | FEETECH FT5330M | not read (GBP 18.56) | 28.8 @ 6.0, 35.5 @ 7.4 | 0.238 @ 6.0, 0.192 @ 7.4 | 67 g | 25T | vendor-listing | "Only 3 left" (Maplin UK) |
| A38 | FEETECH FS5115M, no feedback wire (Pololu #3426) | 32.06 | 14 @ 4.8, 15.5 @ 6.0 | 0.25 @ 4.8, 0.20 @ 6.0 | 60.7 g | 25T / 5.9 mm | datasheet | backorders allowed; category page says out of stock (Pololu) |
| M09 | Pololu 100:1 HPCB 6V + 12 CPR encoder (#5190) | 32.45 | 1.6 @ 6.0 (theoretical) | 330 rpm no load | 11 g | 3 mm D-shaft | vendor-listing | active, backorders allowed (Pololu) |
| M10 | Pololu 210:1 HPCB 6V + 12 CPR encoder (#5194) | 32.45 | 2.8 @ 6.0 (theoretical) | 160 rpm no load | not on page | 3 mm D-shaft | vendor-listing | active, backorders allowed (Pololu) |
| M11 | Pololu 250:1 HPCB 6V + 12 CPR encoder (#5196) | 32.45 | 3.2 @ 6.0 (theoretical) | 130 rpm no load | not on page | 3 mm D-shaft | vendor-listing | active, backorders allowed (Pololu) |

What this shows for the 8.07 kg·cm hold requirement:

- At 7.4 V or below, the stall torque is 25 kg·cm or more only for A28, A34 (30 at 7.4 V), A36, A37 and, at 6.8 V, A32 (30) and A33 (28). Of these, only A28 is a name-brand listing that is in stock; A32-A34 are backordered, and A36-A37 are listed in pounds sterling with a stated back-order lead time of 45 (unit not given).
- A30 (REV V2 Balanced) gives 16.7 kg·cm at 7.4 V and is in stock, with a drawing PDF that confirms the standard 49.5 x 10 mm hole pattern and 54 mm flange.
- The three gearmotors stall at 1.6-3.2 kg·cm on paper, and Pololu limits instantaneous load to 2 kg·cm for these ratios, so they need further reduction to reach 8.07 kg·cm at the shaft.
- Not added: servos over $50 (Axon MAX Servo MK2 $99.99 and Axon MINI Servo MK2 $99.99, both sold out; Savox SC-0251MGP $51.99; Feetech FT5313M $79.17 and FT5121M $80.81 at Pololu); a part too large for the standard envelope (DS5160 class, 65 x 30 x 48 mm); and parts whose pages would not load (Studica Multi-Mode Smart Servo, RCDrone and RobotShop pages: HTTP 403; REV-41-1097: HTTP 404, discontinued per search result, not read).

### Recheck of 10 existing rows (2026-10-11)

| id | Part | Price then | Price now | Stock now |
|---|---|---|---|---|
| A13 | FEETECH FS5115M-FB | 35.77 | 35.77 (Pololu) | backorders allowed; category page lists out of stock |
| A16 | MG996R-class (Adafruit #1142) | 19.95 | 19.95 (Adafruit) | out of stock |
| A17 | DSServo DS3218MG (SpeedyFPV) | 12.99 | 12.99 (SpeedyFPV) | page shows "Maximum Available" next to 14; count not stated |
| A18 | DSServo DS3225 (MakerFocus) | 18.99 | 18.99, list 21.99 (MakerFocus) | unclear: Add to cart plus back-in-stock signup |
| A19 | DSServo DS3235 (RCDrone) | 24.49 | not rechecked, page returned HTTP 403 | other vendor: DS3235 SG (Blue) $30.00 backordered (aifitlab, different variant) |
| A20 | JX PDI-6221MG (RCDrone) | 18.05 | not rechecked, page returned HTTP 403 | no other public vendor price read |
| M01 | Pololu 150:1 HPCB (#5193) | 32.45 | 32.45 | active, backorders allowed |
| M02 | Pololu 380:1 HPCB (#5200) | 32.45 | 32.45 | active, backorders allowed |
| M03 | Pololu 1000:1 HPCB (#5202) | 43.95 | 43.95 | active, backorders allowed |
| M04 | Pololu 298:1 HP (#5173) | 29.95 | 29.95 | active, backorders allowed |

No existing price changed. The `spec_basis` of these 10 rows: A13, A16, A17 `mixed`; A18, A20, M01-M04 `vendor-listing`; A19 `datasheet`.

### Vendor claims without a datasheet

These rows rest on a retailer or product page only (`spec_basis` = `vendor-listing`): A28, A29 (goBILDA publishes only a STEP file), A32-A34 (aifitlab), A35 (ServoCity), A36-A37 (Maplin; servodatabase.com agrees, but it states that part of its data is community or AI submitted), M09-M11 (Pololu's own extrapolated stall figures, not measured), and from the earlier rows A18, A20, M01-M04. The two aifitlab "Red" variants were not added as rows because their own prices were not shown on the fetched pages.

- Torque differs by vendor for one part: A18 (MakerFocus) lists DS3225 at 21 / 25 kg·cm at 5.0 / 6.8 V and 67 g; A33 (aifitlab) lists 24.5 / 28 kg·cm and 60 g.
- A34 DS3235 SG (aifitlab) lists 35 kg·cm at 8.4 V, while the DS3235 datasheet row A19 lists 35 kg·cm at 7.4 V.
- Dimensions for A36 and A37 conflict inside the Maplin pages (40 x 20 x 47.4 mm in the text, 55 x 20 x 43 mm in the table).
- A38 mass: Pololu says 62 g and a burst above 3 A at 6 V; the Feetech datasheet says 60.7 g and 1.7 A stall.
- Not read: no goBILDA, aifitlab or Maplin page publishes a datasheet PDF for these parts; the Hitec page for the HS-645MG returned 404.

### Sources for the extension (all retrieved 2026-10-11)

- [goBILDA 25-2 Torque](https://www.gobilda.com/2000-series-dual-mode-servo-25-2), [goBILDA 25-3 Speed](https://www.gobilda.com/2000-series-dual-mode-servo-25-3-speed)
- [REV Smart Robot Servo V2](https://www.revrobotics.com/Smart-servo-v2), [REV V2 drawing PDF](https://www.revrobotics.com/content/docs/REV-41-3334-3336-DR.PDF), [REV Smart Robot Servo manual page (V1, 13.5 kg·cm at 6 V)](https://docs.revrobotics.com/rev-crossover-products/servo/srs)
- [aifitlab DS3230 MG](https://aifitlab.com/products/dsservo-ds3230-mg-servo-motor), [aifitlab DS3225 MG](https://aifitlab.com/products/dsservo-ds3225mg-servo-motor), [aifitlab DS3235 SG](https://aifitlab.com/products/dsservo-ds3235-sg-servo-motor), [aifitlab DSServo collection](https://aifitlab.com/collections/dsservo-motor)
- [ServoCity HS-645MG](https://www.servocity.com/hs-645mg-servo/)
- [Maplin FT5325M](https://pro.maplin.co.uk/products/ft5325m-high-torque-67g-25kg-cm-digital-180-rotation-servo-feetech), [Maplin FT5330M](https://pro.maplin.co.uk/products/ft5330m-high-torque-67g-35-5kg-cm-digital-180-rotation-servo-feetech), [servodatabase FT5325M](https://servodatabase.com/servo/feetech/ft5325m), [servodatabase FT5330M](https://servodatabase.com/servo/feetech/ft5330m)
- [Pololu FS5115M #3426](https://www.pololu.com/product/3426), [Feetech FS5115M specification PDF](https://www.pololu.com/file/0J1270/FS5115M-specs.pdf), [Pololu FS5115M-FB #3443](https://www.pololu.com/product/3443), [Pololu RC servo category](https://www.pololu.com/category/23/rc-servos)
- [Pololu #5190](https://www.pololu.com/product/5190), [#5190 specs](https://www.pololu.com/product/5190/specs), [#5194](https://www.pololu.com/product/5194), [#5196](https://www.pololu.com/product/5196), [#5193](https://www.pololu.com/product/5193), [#5200](https://www.pololu.com/product/5200), [#5202](https://www.pololu.com/product/5202), [#5173](https://www.pololu.com/product/5173), [Pololu micro metal gearmotor category](https://www.pololu.com/category/60/micro-metal-gearmotors)
- Over-budget or dropped: [goBILDA Axon MINI MK2](https://www.gobilda.com/axon-mini-servo-mk2/), [ServoCity Axon MAX MK2](https://www.servocity.com/axon-max-servo-mk2/), [Hobbyetc Savox SC-0251MGP](https://store.hobbyetc.com/parts/view/168168), [servodatabase Savox SC-0251MG+](https://servodatabase.com/servo/savox/sc0251mg)
- Recheck: [Adafruit #1142](https://www.adafruit.com/product/1142), [SpeedyFPV DS3218MG](https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories), [MakerFocus DS3225](https://www.makerfocus.com/products/digital-servo-25kg), [servodatabase JX PDI-6221MG](https://servodatabase.com/servo/jx-servo/pdi-6221mg)

## Sources

Every row's `vendor_url` and `datasheet_url` in the CSV is its source. Other sources: [Pololu RC servo list](https://www.pololu.com/category/23/rc-servos), [TowerPro MG90S](https://www.electronicoscaldas.com/datasheet/MG90S_Tower-Pro.pdf), [TowerPro SG90](https://handsontec.com/dataspecs/motor_fan/SG90-Servo.pdf), [Pololu micro metal gearmotors](https://www.pololu.com/category/60/micro-metal-gearmotors), [EDG ME102B](https://edg.berkeley.edu/course/me102b).
