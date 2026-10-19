# Gear strength, fatigue and wear: 3D printed vs CNC (gripper, 2026-09-22)

> **Design loads superseded.** The STS3215 stall loads below are historical. The gripper actuator is a PWM hobby servo, and the load cases (LC1 hold 0.383 N·m, LC2 cap 0.956 N·m, LC3 stall with one finger blocked 2.0 N·m of mesh torque), allowables and safety factors now live in `docs/gripper/DESIGN-BASIS.md`. The equations, material data and test data here still apply.

Scope: the 1:1 spur sector pair in `cad/gripper/params.json` (m 1.0, z 24, b 6 mm, α 20°, 100° sector), and the design space m 0.8-1.5, z 14-36, mesh torque 0.5-3 N·m. No prices are quoted in this note.

Tags: **[S]** sourced (link in the row or sentence), **[D]** derived here (the method is shown), **[A]** assumed. The derived numbers come from a throwaway script that uses the equations in section 5. They are not a validated tool.

## 1. Bottom line

- **The current gear (m 1, z 24, b 6) is marginal in PLA.** At 1 N·m mesh torque, Lewis root stress is 41 MPa [D]. Printed PLA tensile strength is 35 MPa in X-Y [S], and the PLA coupon fatigue strength at 1e5 cycles is about 22 MPa σmax [D]. Tooth deflection is 0.081 mm [D], against the VDI 2736 guide value of 0.07·m = 0.07 mm [S].
- **The mesh carries about half the servo torque.** Finger A's own reaction goes straight into the shaft; only finger B's share crosses the mesh [A, from statics of a symmetric grip]. At STS3215 stall (1.91 N·m at 7.4 V, [README](../../../cad/gripper/README.md)) that puts about 0.95 N·m on the teeth [D].
- **The critical failure modes in this gripper are static, and wear is secondary.** Teeth are loaded mostly while the jaw is still (holding), always on the same flank. That makes the root load a pulsating R ≈ 0 cycle with long dwells. The expected failures are tooth-root overload at stall or impact, low-cycle root fatigue, and creep and backlash growth under the holding load. Sliding wear and heating are minor, because each stroke slides only about 0.7 mm per flank [D] at very low power.
- **Fixes, cheapest first:**
  1. Limit the holding torque in firmware or with a compliant stop, so the gear never sees stall.
  2. Go to m 1.25, z 24 (a = 30 mm): σ drops to 26 MPa/N·m and λ to 0.065 mm [D].
  3. Print the teeth in PA6-CF or PAHT-CF (X-Y bending strength 151 / 125 MPa [S]).
  4. Machine POM (flexural fatigue 32 MPa at 1e6 cycles [S]).
  Metal is not needed for strength. Steel costs about 6x the mass of a PLA sector [D].
- **Pair dissimilar polymers.** In the POM/PA6 pairing, friction was 0.28; PA6/PA6 was 0.45, and POM/POM wore the most ([Pogacnik & Tavcar, KISSsoft](http://globasdistribution.com/wp-content/uploads/2017/01/article_kisssoft_vdi_2736_gear_temperature.pdf)) [S].

## 2. Design allowables

### 2.1 Printed polymers (FFF, 100 % infill, vendor TDS; X-Y = in-layer, Z = across layers)

| Material (source) | ρ g/cm³ | E X-Y / Z MPa | Tensile X-Y / Z MPa | Bending strength X-Y / Z MPa | HDT 0.45 MPa °C | Notes |
|---|---|---|---|---|---|---|
| PLA, Bambu PLA Basic ([TDS](https://wiki.bambulab.com/filament-acc/abs-asa-pc/bambu_pla_basic_technical_data_sheet.pdf)) | 1.24 | 2580 / 2060 | 35 / 31 | 76 / 59 | 57 | Tg 60 °C. Specimens annealed 55 °C, 8 h [S] |
| PETG, Bambu PETG Basic ([TDS](https://store.bblcdn.com/s1/default/cb94589bf7994fdcbfa833badefae9cd/Bambu_PETG_Basic_Technical_Data_Sheet.pdf)) | 1.25 | 2780 / 2550 | 51 / 35 | 75 / 56 | 71 | Impact X-Y / Z 34.2 / 10.5 kJ/m² [S] |
| ABS, Bambu ABS ([TDS](https://store.bblcdn.com/s7/default/23b4cf2b83d5470bb96d19970b5f3ae8/Bambu_ABS_Technical_Data_Sheet_V3.pdf)) | 1.05 | 2200 / 1960 | 33 / 28 | 62 / 39 | 87 | [S] |
| PA6-CF, Bambu ([TDS](https://wiki.bambulab.com/filament-acc/petcf-ppacf/c750bddfb8e44af6ae9f7dd9625fa458.pdf)) | 1.09 | 4430 / 2170 | 102 / 48 | 151 / 80 | 186 | Dried and annealed 80 °C, 12 h. Saturated water uptake 2.35 % [S] |
| PAHT-CF, Bambu ([TDS](https://wiki.bambulab.com/filament-acc/asacf-pahtcf/65f1b18a6d6142d794a1a6a00f1496ef.pdf)) | 1.06 | 3860 / 2180 | 92 / 47 | 125 / 61 | 194 | Water uptake 0.88 % [S] |
| Onyx (CF-PA), Markforged ([Hriberšek et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11269922/)) | - | 1400 | 36 | 81 | 145 | Vendor values quoted in the paper [S] |
| POM printed | 1.41 | - | ~69-70 | - | - | Generic blog values only ([Makenica](https://makenica.com/the-comprehensive-guide-to-pom-3d-printing/)). No printed-POM TDS found. Treat as unknown [S, weak] |

**PLA fatigue (FFF, R = 0.05, 5 Hz, 100 % infill, 0.2 mm layers)** ([Polymers 2026, notched PLA](https://pmc.ncbi.nlm.nih.gov/articles/PMC12787623/)):

- Fit: Basquin σa = 68.159·N^−0.161 (smooth YZ specimens, UTS 37.2 MPa) [S].
- At σmax = 0.6·UTS (22.3 MPa), life was about 1e5 cycles [S].
- Derived σmax allowables [D]: 47 MPa at 1e3, 33 MPa at 1e4, 22.5 MPa at 1e5, 15.5 MPa at 1e6.
- Notch factor Kf is 1.12-1.16 [S].

**Orientation, infill and layers:**

- **Raster angle.** Tensile strength is highest at a 0° raster. Fatigue life is longest at 45° and drops sharply at 90° ([Horasan 2024, abstract](https://onlinelibrary.wiley.com/doi/full/10.1111/ffe.14406)) [S].
- **Infill.** Below 100 % infill, printed PLA behaves as a notched material and fatigue strength falls ([Safai et al. review](https://www.sciencedirect.com/science/article/pii/S0142112320305399), via search abstract) [S, abstract-level].
- **Nylon gear wear.** Alternating raster directions gave much higher wear on printed nylon gears. Fibre orientation dominated tribology ([Zhang, Purssell, Mao, Leigh 2020](https://www.sciencedirect.com/science/article/abs/pii/S0301679X19304724)) [S, abstract].
- **What that means for the print** [A, from the above]:
  - Print gears flat, with the gear axis along Z, so the tooth bending plane lies in X-Y and inter-layer bonds carry no root tension.
  - Use enough perimeters (for example 5+) that each tooth is all contour extrusions following the root fillet, with 100 % solid infill in the hub.
  - Use a 0.1-0.2 mm layer height for flank accuracy.

### 2.2 Machined polymers and metals

| Material | ρ g/cm³ | UTS / yield MPa | E MPa | Fatigue | Hardness | Source |
|---|---|---|---|---|---|---|
| POM-H Delrin 100/500 | 1.42 [A] | 69 (tensile, 23 °C); flexural yield 97-99 | 2800-3100 | **Flexural 32 MPa at 1e6** (ASTM D671, 23 °C, 50 % RH). Tensile falls to 48 MPa at 70 °C | - | [DuPont Delrin Design Guide Module III](https://kmsbearings.com/content/category/pdfs/Delrin_Acetal_Design_Guide.pdf) [S] |
| POM-H Delrin 500 (gear curve) | - | - | - | Flexural: below 25 MPa "fatigue should not be an issue" at 23 °C. Fully reversed (R = −1) is more damaging than one-direction loading, and the allowable falls at 66 / 100 °C | - | [Delrin Fatigue Endurance](https://www.delrin.com/wp-content/uploads/2024/07/Delrin-Solutions-Series-Fatigue-Endurance-NA-FNL.pdf) [S] |
| POM (VDI 2736 root fatigue) | - | - | - | About 30-35 MPa root bending fatigue at 1e7 cycles, 23 °C (PA66 conditioned 25-30) | - | Search-result summary of VDI 2736 data; not verified against the standard [S, weak] |
| Al 6061-T6 | 2.70 | 310 / 276 (typical); 290 / 240 minimum | 69 000 | 97 MPa at 5e8 cycles, R.R. Moore reversed | 95 HB | [Wikipedia](https://en.wikipedia.org/wiki/6061_aluminium_alloy), [Epocrafter](https://www.epocrafter.com/6061-vs-7075-aluminum/) [S] |
| Al 7075-T6 | 2.81 | 572 / 503 (typical) | 71 700 | 159 MPa at 5e8 cycles | 150 HB | [Epocrafter](https://www.epocrafter.com/6061-vs-7075-aluminum/), [Wikipedia](https://en.wikipedia.org/wiki/7075_aluminium_alloy) [S] |
| Through-hardened steel, AGMA grade 1 | 7.85 [A] | - | 210 000 [A] | St = 0.533·HB + 88.3 MPa (bending); Sc = 2.22·HB + 200 MPa (contact, 1e7 cycles, 99 % reliability). **At 200 HB: St = 195, Sc = 644 MPa** [D] | e.g. 200 HB [A] | ANSI/AGMA 2001-D04 / 2101-D04 equations, as reported in [search summary](https://www.engineersedge.com/gears/agma_allowable_contact_stress_15854.htm) [S] |

**Aluminium caveat.** AGMA publishes no aluminium gear allowables in the sources found. Practitioners report that aluminium teeth gall and wear fast. They also report that hard anodize is too thin and brittle over soft substrate for Hertzian tooth loads ([Eng-Tips](https://www.eng-tips.com/threads/type-iii-hard-anodize-finish-on-gear.264621/), [Eng-Tips](https://www.eng-tips.com/threads/aluminium-and-stainless-steel-gears-wear-out-fast.344093/)) [S, practitioner].

## 3. Gear-specific life tests

| Test | Geometry | Materials | Load / speed | Result | Lewis σ at test [D] |
|---|---|---|---|---|---|
| [Hriberšek et al. 2024, Heliyon](https://pmc.ncbi.nlm.nih.gov/articles/PMC11269922/) | m 1, z 20, b 6, α 20° | Printed Onyx driven by 42CrMo4 steel | 1.1 / 1.3 / 1.5 N·m at 1400 rpm | 6.27 M (sd 1.36) / 2.05 M (0.53) / 0.06 M cycles. The 1.5 N·m gears failed by melting at about 103.5 °C; the lower loads by root fatigue. Flank wear 0.186 mm after 4.86 M cycles at 1.1 N·m [S] | 57 / 67 / 78 MPa |
| [Pogacnik & Tavcar (KISSsoft / Ljubljana)](http://globasdistribution.com/wp-content/uploads/2017/01/article_kisssoft_vdi_2736_gear_temperature.pdf) | m 1, z 20, b 6, ISO 10-11 | Molded POM driving molded PA6, dry | 0.30-0.82 N·m, 600-2305 rpm | 0.42 N·m: 5.4-15.6 M cycles. 0.59 N·m: 1.6-3.6 M. 0.82 N·m: 0.30-0.76 M, or immediate thermal failure at high rpm. Values are at 90 % survival; failure was PA6 root fatigue. Step test: PA6/PA6 failed at 0.45 N·m, POM/PA6 at 0.75 N·m [S] | 22 (0.42) / 42 (0.82) MPa |
| [igus 3D printed gear](https://www.igus.com/custom-parts-services/3d-printing/3d-printed-gear) (vendor) | m 1, z 30, b 6.5, driving a rack | SLS iglidur i3 vs milled POM | 2.25 N·m, pivoting 1440°, 64 rpm | Vendor claims i3 lasts 5x milled POM. Another vendor summary gives milled POM broken at 12 500 cycles and i3 at about 20 000 ([3druck](https://3druck.com/en/programs/calculate-lifetime-of-3d-printed-gears-0181934/)). The two figures conflict [S, vendor] | 64 MPa |
| [DuPont Delrin gear brochure](https://www.emcoplastics.com/assets/pdf/delrin/Delrin%20Gear%20Brochure%20Dupont_10_2007.pdf) | m 0.8, z 40, identical pair | Delrin 100P | 3 N·m, 100 rpm | Failure in about 10 min, i.e. about 1000 cycles. FEA showed yield exceeded, i.e. low-cycle fatigue [S] | b not given |
| [Tunalioglu & Agca 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9147857/) | m 6, z 17/22, b 10 | Printed ABS, PLA, PETG vs steel; 0.2 mm layers, 100 % rectilinear | 1.5 N·m, 900 rpm | PETG lasted 22.3 % longer than PLA and 37 % longer than ABS [S]. Hackaday reports about 500 k (PLA) and 700 k (PETG) cycles ([Hackaday](https://hackaday.com/2025/07/17/this-service-life-study-really-grinds-our-gears/)) [S, secondary] | 1.6 MPa: a wear/thermal failure, not bending. Not transferable |
| Recycled PLA gears ([Research Square](https://www.researchsquare.com/article/rs-5284212/v1)) | not verified | Recycled vs blended PLA | not verified | About 733 k vs 1.048 M cycles (search-snippet level) [S, weak] | - |

**Reading.** These are continuous-rotation tests, so heat drives much of the failure. For m 1, b 6 polymer gears, the data put Lewis root stress of about 20-40 MPa at millions of cycles, and 55-65 MPa at 1e4-1e6 cycles for CF-PA [D]. The gripper runs cold and slow, so these lives are conservative for heat but not for dwell creep [A].

## 4. Wear coefficients (Archard, dimensional k in mm³/(N·m))

| Pair | k | Conditions | Source |
|---|---|---|---|
| POM vs steel | 3.4e-6 | Value from VDI 2736, used in an FE wear model (m 2.5, z 36, b 14, 16 N·m, dry, μ = 0.25) | [Muratović et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11054830/) [S] |
| POM vs C45 steel | 5.58 / 9.77 / 12.96 e-6 | 4 / 5 / 6 N·m, 1000 rpm; k rises with load | [Contact mechanics wear model 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11510993/) [S] |
| PVDF vs C45 | 7.72 / 10.98 / 12.62 e-6 | same | same [S] |
| Printed PETG (pin-on-disc) | 5e-4 dry, 1e-4 wet | Pin-on-disc, not a gear test | [Springer J. Inst. Eng. D 2025](https://link.springer.com/article/10.1007/s40033-025-00885-y) (search abstract) [S, weak] |
| Printed PLA | below 1e-6 mild regime, above 1e-6 severe | Review, abstract-level | [Materials Today Proc. review](https://www.sciencedirect.com/science/article/abs/pii/S2214785322031017) [S, weak] |

Friction coefficients back-calculated from VDI 2736 temperatures, dry, m 1 gears: PA6/PA6 0.45, POM/PA6 0.28, POM/POM 0.25, POM/PA6-30GF 0.25, PA6-30/PA6-30 0.37. The VDI default for POM/PA is 0.18 ([Pogacnik & Tavcar](http://globasdistribution.com/wp-content/uploads/2017/01/article_kisssoft_vdi_2736_gear_temperature.pdf)) [S].

**Lubrication:**

- **Plastic gears.** Most run dry. A lubricant mainly controls meshing temperature and matters at high speed ([KHK](https://khkgears.net/new/gear_knowledge/gear_technical_reference/design-of-plastic-gears.html)) [S].
- **Delrin curves.** DuPont's Lewis-stress life curves are for continuously lubricated gears, with stress reduced 25 % as margin. PTFE-filled grades wore least in DuPont's steel-pinion tests ([DuPont](https://www.emcoplastics.com/assets/pdf/delrin/Delrin%20Gear%20Brochure%20Dupont_10_2007.pdf)) [S].
- **Printed materials.** Practitioner advice: for PLA, PETG and ABS, use lithium or silicone grease and avoid petroleum oils. Nylon runs dry ([Siraya Tech](https://siraya.tech/blogs/news/best-filament-for-gears)) [S, practitioner].
- **For this gripper** [A]: use a thin PTFE dry lube or silicone grease on printed teeth. Keep grease away from the cloth path.

## 5. Equations for a 1:1 spur pair (m 0.8-1.5, z 14-36)

Symbols: T = mesh torque (N·mm), d = m·z, Ft = 2T/d, b = face width, u = 1.

**Geometry** [D, standard involute]:

- Radii: r = mz/2, ra = r + m, rb = r·cos α; center distance a = m·z.
- Contact ratio: εα = [2·√(ra² − rb²) − a·sin α] / (π·m·cos α). It is 1.46 (z 14) to 1.69 (z 36).
- Sliding velocity: vs = 2ω·|g|, where g is the distance of the contact point from the pitch point along the line of action.
- Sliding per closing stroke Δθ: s ≈ 2·g²max/rb, with g limited to rb·Δθ/2 and to the addendum. For a 20° jaw stroke this gives about 0.69 mm per flank (m 1, z 24) [D].

**Lewis (first pass)**: σF = Ft / (b·m·Y), where Y is the Lewis form factor, 20° full depth [S partial; see note].

| z | 12 | 14 | 16 | 18 | 20 | 24 | 26 | 28 | 30 | 34 | 36 | 38 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Y | 0.245 | 0.277 | 0.296 | 0.309 | 0.322 | 0.337 | 0.346 | 0.353 | 0.359 | 0.371 | 0.378 [D, interpolated] | 0.384 |

The values for 12, 20, 24 and 30 teeth are confirmed on [Firgelli](https://www.firgelliauto.com/blogs/engineering-calculators/gear-tooth-strength-calculator-lewis-formula). The 14- and 24-tooth values come from a search excerpt of the standard Lewis table. The other values are the standard table as widely reproduced and were not re-verified against a linked page [S, partial].

DuPont's plastic-gear form is Sb = 2T/(f·Y·M·Dp) ([DuPont](https://www.emcoplastics.com/assets/pdf/delrin/Delrin%20Gear%20Brochure%20Dupont_10_2007.pdf)) [S]. KHK/JGMA uses F = m·y·b·σb·f, with speed, temperature, lubrication and material factors ([KHK](https://khkgears.net/new/gear_knowledge/gear_technical_reference/design-of-plastic-gears.html)) [S].

**ISO 6336-3 root stress (Method B)**: σF0 = Ft/(b·mn)·YF·YS·Yβ·YB·YDT; then σF = σF0·KA·KV·KFβ·KFα ([ISO 6336-3:2019](https://www.iso.org/obp/ui/#iso:std:iso:6336:-3:en)) [S, structure].

- I implemented YF and YS at the outer point of single-pair contact, for a standard rack (hfP = 1.25m, ρfP = 0.38m, x = 0) [D].
- Results: YF·YS = 3.51 (z 14), 3.15 (18), 2.88 (24), 2.73 (30), 2.64 (36).
- Cross-check: this is close to 1/Y, and to YFa·YSa·Yε ≈ 4.19 × 0.72 ≈ 3.0 for z 24 [D].
- Check against [python-gearbox](https://github.com/efirvida/python-gearbox) (LGPL; ISO 6336 and AGMA 2101-D04) or KISSsoft before relying on it.

**Hertz / ISO 6336-2 contact**: σH = ZE·ZH·Zε·√[Ft/(b·d1)·(u+1)/u]·√(KA·KV·KHβ·KHα) ([ISO 6336-2](https://cdn.standards.iteh.ai/samples/36328/0ff3045b2f864587a44a4f285b62b854/ISO-6336-2-2006.pdf), public sample pages) [S, structure].

- ZH = √(2/(cos²α·tan α)) = 2.495 for α 20°, x = 0 [D].
- ZE = √(1/(π·[(1−ν1²)/E1 + (1−ν2²)/E2])) [D]. Self-mated values, with ν = 0.35 polymers, 0.33 Al, 0.30 steel [A]: PLA 21.6, PETG 22.5, PA6-CF 28.3, POM 22.9, Al 6061 111, steel 192 √MPa [D].
- Zε = √((4 − εα)/3) [D].

**Metal allowables (AGMA 2001/2101)**:

- Bending: σ ≤ St·YN/(SF·Kθ·KR). Contact: σc ≤ Sc·ZN·CH/(SH·Kθ·KR). St and Sc are from the section 2.2 table [S].
- Steel teeth at 1 N·m (m 1, z 24): σH = 460 MPa vs Sc = 644 at 200 HB, and σF = 41 MPa vs St = 195 [D]. Steel is far oversized here.

**VDI 2736 (thermoplastic gears)**. Parts 1-4 cover materials, rating and test methods ([VDI 2736 Blatt 1](https://www.vdi.de/en/home/vdi-standards/details/vdi-2736-blatt-1-thermoplastic-gear-wheels-materials-material-selection-production-methods-production-tolerances-form-design)). The standard itself is paywalled and was not read. Public sources give the following:

- **Root**: σF = (Ft/(b·mn))·YFa·YSa·Yε·Yβ·KF, compared with a permissible σFP = σFlimN(N, ϑroot)·YN/SFmin. σFlimN depends on cycles and root temperature. VDI tabulates POM, PA66, PET and PE, at 10 % failure probability ([Gear Solutions, VDI vs JIS](https://gearsolutions.com/features/comparison-of-strength-ratings-of-plastic-gears-by-vdi-2736-and-jis-b-1759/)) [S, structure; the exact factor list is inferred].
- **Flank**: Hertz as above, with the polymer ZE and σHlimN(N, ϑflank). No sourced polymer σHlim was found. As an operating anchor, DuPont ran Delrin wear tests at an initial contact stress of 39-42 MPa for tens of millions of cycles, with wear, not pitting, as the result ([DuPont](https://www.emcoplastics.com/assets/pdf/delrin/Delrin%20Gear%20Brochure%20Dupont_10_2007.pdf)) [S].
- **Deformation**: λ = 7.5·(Ft/(b·cos β))·(1/E1 + 1/E2), with limit λzul = 0.07·mn ([Polymers 2023, VDI deformation check](https://pmc.ncbi.nlm.nih.gov/articles/PMC10537784/)) [S]. The article's text reads "Ft·b". I used Ft/b, which is the dimensionally consistent form [D]. The same study measured deflection about 50 % above the VDI estimate at low speed [S].
- **Wear (local)**: W = (Fn/bw)·NL·ζ·kw, with Fn = 2Td/(dw·cos αt) and ζ = specific sliding ([Muratović et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11054830/)) [S]. The fetched text put NL in the denominator; the product form here is Archard-consistent [D]. Nodal Archard form: dh/ds = kw·p ([PMC11510993](https://pmc.ncbi.nlm.nih.gov/articles/PMC11510993/)) [S].
- **Temperature**:
  - The root and flank temperature is ϑ = ϑ0 + (term ∝ P·μ·HV × [kϑ/(b·z·(v·m)^c) + housing term] × duty-cycle factor). The published POM/PA defaults are μ = 0.18, kϑ,root = 2100 and c = 0.75. Refitted values from tests are kϑ,root = 1505 and c = 0.36 (standard deviation 4 °C) ([Pogacnik & Tavcar](http://globasdistribution.com/wp-content/uploads/2017/01/article_kisssoft_vdi_2736_gear_temperature.pdf)) [S].
  - The full coefficient set was not available publicly. **Do not compute with this until it is checked against VDI 2736-2** [A].
  - The loss factor is HV = π(u+1)/(z1·u·cos βb)·(a0 + a1|ε1| + a2|ε2| + a3|ε1|ε1 + a4|ε2|ε2) (Ohlendorf/Wimmer), and PV = HV·μ·Pin ([FVA-Workbench](https://doc.fva-service.de/90/en/root-power-loss.html)) [S].
  - For this gripper, the peak mesh power is about 1 W: 1 N·m × 20° in 0.3 s [A], at a small duty cycle. So ϑ ≈ ambient [D]. The design temperature is set by the room and nearby motors (for example ≤ 40 °C [A]), not by friction.

## 6. Derived stresses across the design space (T_mesh = 1 N·m, b = 6 mm)

Bending stress scales linearly with T and 1/b. Contact stress scales with √T and 1/√b. [D]

| m | z | a = d mm | εα | σF Lewis MPa | σF ISO-B MPa | σH PLA/PLA MPa | σH POM/POM MPa | λ PLA mm (limit 0.07m) |
|---|---|---|---|---|---|---|---|---|
| 0.8 | 14 | 11.2 | 1.46 | 134 | 130 | 114 | 121 | 0.173 (0.056) ✗ |
| 0.8 | 24 | 19.2 | 1.60 | 64 | 63 | 65 | 69 | 0.101 (0.056) ✗ |
| 0.8 | 36 | 28.8 | 1.69 | 38 | 38 | 42 | 45 | 0.067 (0.056) ✗ |
| 1.0 | 14 | 14 | 1.46 | 86 | 84 | 92 | 97 | 0.138 (0.070) ✗ |
| 1.0 | 18 | 18 | 1.53 | 60 | 58 | 70 | 75 | 0.108 (0.070) ✗ |
| **1.0** | **24** | **24** | **1.60** | **41** | **40** | **52** | **55** | **0.081 (0.070) ✗** |
| 1.0 | 30 | 30 | 1.65 | 31 | 30 | 41 | 44 | 0.065 (0.070) ✓ |
| 1.0 | 36 | 36 | 1.69 | 25 | 24 | 34 | 36 | 0.054 (0.070) ✓ |
| 1.25 | 18 | 22.5 | 1.53 | 38 | 37 | 56 | 60 | 0.086 (0.088) ✓ |
| 1.25 | 24 | 30 | 1.60 | 26 | 26 | 42 | 44 | 0.065 (0.088) ✓ |
| 1.25 | 36 | 45 | 1.69 | 16 | 16 | 27 | 29 | 0.043 (0.088) ✓ |
| 1.5 | 14 | 21 | 1.46 | 38 | 37 | 61 | 65 | 0.092 (0.105) ✓ |
| 1.5 | 18 | 27 | 1.53 | 27 | 26 | 47 | 50 | 0.072 (0.105) ✓ |
| 1.5 | 24 | 36 | 1.60 | 18 | 18 | 35 | 37 | 0.054 (0.105) ✓ |
| 1.5 | 36 | 54 | 1.69 | 11 | 11 | 23 | 24 | 0.036 (0.105) ✓ |

**Mesh torque allowed by root stress, for m 1, z 24, b 6** [D]:

| Allowable σ, MPa | Basis | Mesh torque, N·m |
|---|---|---|
| 11.25 | PLA at 1e5 cycles (22.5 MPa), safety factor 2 [A] | 0.27 |
| 15.5 | PLA at 1e6 cycles | 0.38 |
| 22.5 | PLA at 1e5 cycles, no safety factor | 0.55 |
| 32 | POM flexural fatigue at 1e6 cycles | 0.78 |
| 57 | Onyx 6 M-cycle test level | 1.38 |
| 97 | Al 6061 fatigue strength | 2.35 |
| 195 | Steel St at 200 HB | 4.73 |

**Mass** of a solid 100° sector at the pitch radius, m 1, z 24, b 6 [D]: PLA 0.93 g, PETG 0.94 g, PA6-CF 0.82 g, POM 1.06 g, Al 2.04 g, steel 5.92 g.

## 7. What a "virtual dyno" duty-cycle life simulation needs

**Inputs:**

1. **Geometry.** m, z, x, b, αn, tip and root radii, and the root fillet (from `params.json` or the rack). Also center distance, its tolerance, and backlash. Also the sector: which 1-3 teeth carry load at the hold angle [D: at 20° stroke, contact sweeps about 3.9 mm of the line of action, so the same teeth take every grip].
2. **Load profile per grip.** Model the servo torque-time curve, with the mesh getting about ½ the shaft torque [A]:
   - closing (low torque: inertia plus friction),
   - impact at finger contact (peak = stall, or the firmware limit, times a KA of 1.25-1.75 [A]),
   - hold (torque and duration),
   - opening (reverse flank, near zero).
   Also supply grips per hour and hours of life. Target [A]: about 1e5 grips, i.e. 50 h at 30 grips/min (1 per 2 s).
3. **Materials, per print orientation.**
   - E(T), and UTS and flexural strength in X-Y and Z (section 2.1).
   - An S-N curve at R ≈ 0: Basquin A, B (PLA from section 2.1; others need tests).
   - The notch factor, and the creep compliance J(t, σ, T) for the hold dwell. **No sourced creep data yet.**
   - kw and μ for the actual pair (section 4).
   - Moisture state for PA.
4. **Environment.** Ambient temperature (heating is negligible), humidity, and lubrication state.
5. **Method per step.**
   - Root stress (ISO-B or VDI) per load segment, with Miner damage D = Σ nᵢ/Nᵢ.
   - Archard wear per segment: Δh = kw·p·s, using the loaded sliding only, and updating the profile.
   - Creep deflection during the hold, and the resulting backlash growth.
   - The deformation check against λ ≤ 0.07·m.
6. **Failure criteria.**
   - D ≥ 1.
   - Wear depth ≥ a chosen limit, for example 0.1·m [A].
   - Backlash growth that exceeds the jaw-position tolerance (see `tolerancing.md`).
   - λ > 0.07·m.
   - Static: σF,peak ≥ UTS or flexural strength (X-Y) divided by SF 1.5-2 [A].
7. **Calibration.** Bench-test real printed sector pairs with a step-load test: start at 15-20 MPa root stress, raise torque 20 % per step, hold at least 2e5 cycles per step (the Pogacnik & Tavcar procedure [S]). Then run constant-load life tests at three or more torques to fit a gear-level S-N curve. The coupon curves will overpredict life: printed teeth have fillet and surface defects [A].

## Assumptions

- The mesh carries about half the shaft torque (symmetric grip, rigid fingers). The design load is servo stall (STS3215 1.91 N·m, taken from the existing README) unless firmware limits it.
- Tooth loading is pulsating, R ≈ 0 (one flank, closing direction). Coupon data at R = 0.05 applies directly. Fully reversed data would be conservative.
- Life target is about 1e5 grips. Operating ambient is ≤ 40 °C. Printed gears are 100 % solid with many perimeters and the axis along Z.
- Poisson ratios: 0.35 for polymers, 0.33 for Al, 0.30 for steel.
- Self-mated pairs were used for σH and λ. With a dissimilar pair, ZE and λ fall between the two self-mated values.
- The standard rack (hfP 1.25m, ρfP 0.38m) and x = 0 match the CadQuery profile ("addendum m, dedendum 1.25m", root radius not specified).
- The VDI 2736 equation structure was reconstructed from public secondary sources. Coefficients are used only where a source gave them.

## Open questions

- Actual holding-torque strategy: firmware current or position limit, or a mechanical slip or compliant stop? This sets the static design load.
- Actual servo: `actuators.md` flags that the STS3215 conflicts with the PWM ruling. The replacement's stall torque rescales every number here linearly.
- No public creep data for printed PLA, PETG or PA-CF under sustained tooth load. Backlash growth during long holds is unquantified; a bench test is needed.
- No public printed-POM TDS, and no printed-gear S-N curves at low speed and R ≈ 0.
- VDI 2736 permissible σFlimN and σHlimN tables and the temperature coefficients need the paid standard, or a KISSsoft / FVA-Workbench licence (check whether Berkeley provides one).
- The Lewis Y values for 14, 16, 18, 28 and 34 teeth are standard-table values that were not re-verified on a linked page.
