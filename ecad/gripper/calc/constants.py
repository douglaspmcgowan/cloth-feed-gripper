"""Datasheet and vendor numbers used by the gripper controller calculations.

Each entry: value, unit, tag, url, retrieved, note.
Tags: 'S' sourced (the page or PDF was fetched on `retrieved` and the number read from it),
      'A' assumed (the note gives the reason; the number is reversible and swept where it matters).
Jargon: ESR = equivalent series resistance of a capacitor; PGA = programmable-gain amplifier setting of the
INA219 (sets its full-scale shunt voltage); UVLO = under-voltage lockout; BOD = brown-out detector;
gm = transconductance (output current per input volt).

Run `python ecad/gripper/calc/constants.py` to print the table.
"""

RET = '2026-10-11'
TPS = 'https://www.ti.com/lit/ds/symlink/tps54560b.pdf'
INA = 'https://www.ti.com/lit/ds/symlink/ina219.pdf'
MCP = 'https://ww1.microchip.com/downloads/en/DeviceDoc/20005122B.pdf'
ESP = 'https://documentation.espressif.com/esp32_datasheet_en.pdf'
BRN = 'https://www.bourns.com/docs/Product-Datasheets/mfmsmf.pdf'
AOS = 'https://www.aosmd.com/res/data_sheets/AO4407A.pdf'
AWG = 'https://en.wikipedia.org/wiki/American_wire_gauge'
IPC = 'https://www.advancedpcb.com/en-us/tools/trace-width-calculator/'
SPD = 'https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories'
NONE = ''


def _e(value, unit, tag, url, note):
    return {'value': value, 'unit': unit, 'tag': tag, 'url': url, 'retrieved': RET, 'note': note}


C = {
    # ---- TPS54560B (SLVSF00) ------------------------------------------------------------------
    'tps_vin_min': _e(4.5, 'V', 'S', TPS, 'operating input voltage, min (60 V max)'),
    'tps_vin_max': _e(60.0, 'V', 'S', TPS, 'operating input voltage, max'),
    'tps_vref': _e(0.8, 'V', 'S', TPS, 'feedback reference, typ'),
    'tps_vref_min': _e(0.792, 'V', 'S', TPS, 'reference, min over temperature (-1 %)'),
    'tps_vref_max': _e(0.808, 'V', 'S', TPS, 'reference, max over temperature (+1 %)'),
    'tps_ea_gm': _e(350e-6, 'A/V', 'S', TPS, 'error-amplifier transconductance in normal operation (78 uA/V in soft start)'),
    'tps_ea_gain': _e(10000.0, 'V/V', 'S', TPS, 'error-amplifier dc gain; output resistance = gain / gm = 28.6 Mohm'),
    'tps_ea_imax': _e(30e-6, 'A', 'S', TPS, 'error-amplifier source/sink limit at 100 mV overdrive'),
    'tps_ps_gm': _e(17.0, 'A/V', 'S', TPS, 'COMP-to-switch-current transconductance (power stage)'),
    'tps_ilim_min': _e(6.3, 'A', 'S', TPS, 'high-side current limit, min over VIN and temperature (typ 7.9, max 9.5)'),
    'tps_ilim_typ': _e(7.9, 'A', 'S', TPS, 'high-side current limit, typ'),
    'tps_en_thresh': _e(1.2, 'V', 'S', TPS, 'EN threshold, rising and falling (1.1 to 1.3)'),
    'tps_en_thresh_min': _e(1.1, 'V', 'S', TPS, 'EN threshold, min'),
    'tps_en_thresh_max': _e(1.3, 'V', 'S', TPS, 'EN threshold, max'),
    'tps_en_i1': _e(1.2e-6, 'A', 'S', TPS, 'EN pull-up current below threshold (0.58 to 1.8 uA)'),
    'tps_en_ihys': _e(3.4e-6, 'A', 'S', TPS, 'extra EN current once above threshold (2.2 to 4.5 uA)'),
    'tps_rt_coeff': _e(92471.0, 'kHz*kohm^0.991', 'S', TPS, 'fsw[kHz] = 92471 * RT[kohm]^-0.991'),
    'tps_rt_exp': _e(-0.991, '1', 'S', TPS, 'RT exponent in the same equation'),
    'tps_uvlo_rise': _e(4.3, 'V', 'S', TPS, 'internal VIN UVLO, rising (4.1 to 4.48)'),
    'tps_uvlo_hyst': _e(0.325, 'V', 'S', TPS, 'internal UVLO hysteresis'),
    'tps_ton_min': _e(135e-9, 's', 'S', TPS, 'typical minimum controllable on-time'),
    'tps_rds_typ': _e(0.092, 'ohm', 'S', TPS, 'high-side MOSFET on-resistance, typ (VIN 12 V)'),
    'tps_rds_max': _e(0.190, 'ohm', 'S', TPS, 'high-side MOSFET on-resistance, max'),
    'tps_rth_ja': _e(42.0, 'K/W', 'S', TPS, 'DDA (HSOIC-8) junction-to-ambient, JEDEC board'),
    'tps_iq': _e(146e-6, 'A', 'S', TPS, 'operating non-switching supply current'),
    # ---- INA219 (SBOS448G) --------------------------------------------------------------------
    'ina_vos_pga1': _e(100e-6, 'V', 'S', INA, 'INA219A shunt offset max, PGA /1 (typ 10 uV)'),
    'ina_vos_pga2': _e(125e-6, 'V', 'S', INA, 'INA219A offset max, PGA /2'),
    'ina_vos_pga4': _e(150e-6, 'V', 'S', INA, 'INA219A offset max, PGA /4'),
    'ina_vos_pga8': _e(200e-6, 'V', 'S', INA, 'INA219A offset max, PGA /8 (typ 40 uV; the B grade is 100 uV). Part is INA219AIDR'),
    'ina_gain_err_typ': _e(0.0004, '1', 'S', INA, 'current-sense gain error, typ (40 m%)'),
    'ina_meas_err_max': _e(0.005, '1', 'S', INA, 'current measurement error, max at 25 C (includes offset and gain; +/-1 % over -25 to 85 C)'),
    'ina_gain_tc': _e(1e-5, '1/K', 'S', INA, 'gain temperature drift, typ 1 m%/C'),
    'ina_conv_12bit': _e(532e-6, 's', 'S', INA, '12-bit shunt conversion time, typ (586 us max)'),
    'ina_conv_12bit_max': _e(586e-6, 's', 'S', INA, '12-bit conversion time, max'),
    'ina_default_cfg': _e(0x399F, 'code', 'S', INA, 'configuration register reset value: bus 32 V, PGA /8 (+/-320 mV), 12-bit, continuous'),
    'ina_fs_pga8': _e(0.320, 'V', 'S', INA, 'shunt full scale at the default PGA /8'),
    'ina_lsb': _e(10e-6, 'V', 'S', INA, 'shunt-voltage LSB'),
    'ina_ibias': _e(20e-6, 'A', 'S', INA, 'IN+ and IN- input bias current, active mode, typ (IN- also 320 kohm to ground)'),
    'ina_filter_note': _e('series R as small as possible; 10 ohm per input protects against dV/dt and has no significant accuracy effect; caps 0.1 to 1 uF', 'text', 'S', INA,
                          'datasheet advice on input filters (section Filtering and Input Considerations)'),
    # ---- MCP1703A (DS20005122B) ---------------------------------------------------------------
    'mcp_vin_max': _e(16.0, 'V', 'S', MCP, 'input operating range top (2.7 to 16 V)'),
    'mcp_dropout_typ': _e(0.330, 'V', 'S', MCP, 'dropout at 250 mA, 5.0 V output, typ'),
    'mcp_dropout_max': _e(0.650, 'V', 'S', MCP, 'dropout at 250 mA, 5.0 V output, max'),
    'mcp_vout_tol': _e(0.03, '1', 'S', MCP, 'output tolerance over temperature, max (typ 0.4 % at 25 C)'),
    'mcp_isc': _e(0.400, 'A', 'S', MCP, 'output short-circuit current, typ (rated output 250 mA)'),
    'mcp_iout_max': _e(0.250, 'A', 'S', MCP, 'rated output current for a 5.0 V part'),
    'mcp_rth_sot223': _e(62.0, 'K/W', 'A', MCP, 'Microchip DS20005122B page 15 prints 62.9 K/W for SOT-223, not 62.0; value retained for review'),
    # ---- AMS1117-3.3 on the DevKitC V4 --------------------------------------------------------
    'ams_dropout_typ': _e(1.1, 'V', 'A', NONE, 'datasheet fetch failed (SSL handshake error on the vendor server). Value is the usual published typical at 800 mA; a 1.0 V typical is used at 100 mA. Verify on the vendor PDF'),
    'ams_dropout_max': _e(1.3, 'V', 'A', NONE, 'usual published maximum at 800 mA; not fetched this session'),
    'ams_vout_tol': _e(0.01, '1', 'A', NONE, '3.3 V fixed version output tolerance, +/-1 % assumed (not fetched)'),
    'devkit_diode_drop': _e(0.30, 'V', 'A', NONE, 'DevKitC V4 puts a Schottky between the USB 5 V and its 5V rail; drop at 0.1 A assumed'),
    'devkit_overhead_a': _e(0.015, 'A', 'A', NONE, 'DevKitC V4 board overhead (USB bridge, LED, AMS1117 ground current) on the 5 V rail'),
    # ---- ESP32 (datasheet v5.3) ---------------------------------------------------------------
    'esp_vdd_min': _e(2.3, 'V', 'S', ESP, 'chip supply minimum (3.0 V when the module has a 3.3 V in-package flash, as the WROOM-32 does)'),
    'esp_vdd_min_flash': _e(3.0, 'V', 'A', ESP, 'ESP32 chip datasheet applies 3.0 V to in-package flash; the DevKitC WROOM-32E module uses external flash, so this value is not sourced for this assembly'),
    'esp_vdd_max': _e(3.6, 'V', 'S', ESP, 'chip supply maximum'),
    'esp_bod_default': _e(2.43, 'V', 'A', NONE, 'default brown-out detector level in the Arduino-ESP32 / ESP-IDF default sdkconfig (level 7); the datasheet fetched does not state it, verify in the core in use'),
    'esp_i_active_nowifi': _e(0.068, 'A', 'S', ESP, 'CPU powered, 240 MHz dual core, radio off: 30 to 68 mA; top of the range is used'),
    'esp_i_wifi_rx': _e(0.100, 'A', 'S', ESP, 'receive 802.11b/g/n: 95 to 100 mA'),
    'esp_i_wifi_tx_peak': _e(0.240, 'A', 'S', ESP, 'transmit 802.11b 1 Mbps at +19.5 dBm, typ 240 mA (peak of the Wi-Fi cases)'),
    'esp_adc_min_mv': _e(150.0, 'mV', 'S', ESP, 'effective ADC range with 11 dB attenuation, low end'),
    'esp_adc_max_mv': _e(2450.0, 'mV', 'S', ESP, 'effective ADC range with 11 dB attenuation, high end'),
    'esp_adc_err_mv': _e(60.0, 'mV', 'S', ESP, 'total ADC error after eFuse-Vref calibration at 11 dB, +/-60 mV; +/-6 % chip to chip uncalibrated'),
    'esp_adc_cs_pf': _e(20.0, 'pF', 'A', NONE, 'SAR sampling capacitor, not published in the datasheet; 20 pF assumed (a few pF to tens of pF)'),
    'esp_adc_rsw_ohm': _e(1000.0, 'ohm', 'A', NONE, 'sampling switch + mux resistance, assumed'),
    # ---- DS3218MG -----------------------------------------------------------------------------
    'servo_vmin': _e(4.8, 'V', 'A', SPD, 'operating voltage low end on a seller page; manufacturer datasheet not verified'),
    'servo_vmax': _e(6.8, 'V', 'A', SPD, 'operating voltage high end on a seller page; manufacturer datasheet not verified'),
    'servo_stall_a': _e(2.2, 'A', 'A', NONE, 'stall 2.2 A at 6.8 V from docs/gripper/research/actuators.csv row A17 (Miuzei datasheet; Annimos says 1.8 A). The vendor page above does not list current'),
    'servo_idle_a': _e(0.005, 'A', 'A', NONE, 'idle 5 mA from actuators.csv row A17 (Miuzei); moving-no-load current of 0.15 A is a separate assumption in droop_sim.py'),
    # ---- copper wire, 20 C, solid, 100 % IACS -------------------------------------------------
    'awg20_ohm_m': _e(0.03331, 'ohm/m', 'A', AWG, 'general AWG copper reference, not selected stranded wire datasheet'),
    'awg22_ohm_m': _e(0.05296, 'ohm/m', 'A', AWG, 'general AWG copper reference, not selected stranded wire datasheet'),
    'awg24_ohm_m': _e(0.08422, 'ohm/m', 'A', AWG, 'general AWG copper reference, not selected stranded wire datasheet'),
    'awg26_ohm_m': _e(0.1339, 'ohm/m', 'A', AWG, 'general AWG copper reference, not selected stranded wire datasheet'),
    'awg28_ohm_m': _e(0.2129, 'ohm/m', 'A', AWG, 'general AWG copper reference, not selected stranded wire datasheet'),
    'cu_rho': _e(1.724e-8, 'ohm*m', 'A', NONE, 'annealed copper resistivity at 20 C, standard value'),
    'cu_tc': _e(0.00393, '1/K', 'A', NONE, 'copper temperature coefficient of resistance'),
    'cable_l_per_m': _e(0.8e-6, 'H/m', 'A', NONE, 'loop inductance of a twisted power pair, typical 0.5 to 1 uH/m'),
    # ---- passives and parts -------------------------------------------------------------------
    'c12_esr': _e(0.030, 'ohm', 'A', NONE, '1000 uF 16 V low-ESR aluminium electrolytic, ESR near 100 kHz about 20 to 40 mohm; no datasheet fetched'),
    'c12_tol': _e(0.20, '1', 'A', NONE, 'electrolytic capacitance tolerance +/-20 %'),
    'c_wrist_esr': _e(0.100, 'ohm', 'A', NONE, '470 uF general-purpose electrolytic at the forearm end, assumed'),
    'cer_esr': _e(0.003, 'ohm', 'A', NONE, '47 uF 1210 X5R/X7R ceramic ESR, order of a few mohm'),
    'cer_derate_6v6': _e(0.6, '1', 'A', NONE, '47 uF 16 V 1210 X5R retains roughly 50 to 70 % at 6.6 V bias; swept 30 to 100 % in buck_design.py'),
    'l1_dcr': _e(0.015, 'ohm', 'A', NONE, 'Bourns SRP1245A-100M DCR order of 10 to 15 mohm; not fetched'),
    'f1_hold': _e(2.6, 'A', 'A', BRN, 'Bourns MF-MSMF260/16X hold current; selected F1 is RUILON SMD1812P260TF/16, whose datasheet is needed'),
    'f1_trip': _e(5.0, 'A', 'A', BRN, 'Bourns MF-MSMF260/16X trip current; selected RUILON part is not covered'),
    'f1_rmin': _e(0.015, 'ohm', 'A', BRN, 'Bourns MF-MSMF260/16X minimum resistance; selected RUILON part is not covered'),
    'f1_r1max': _e(0.050, 'ohm', 'A', BRN, 'Bourns MF-MSMF260/16X R1max; selected RUILON part is not covered'),
    'f1_vmax': _e(16.0, 'V', 'A', BRN, 'Bourns MF-MSMF260/16X maximum voltage; selected RUILON part needs its own rating'),
    'f1_ttrip': _e(5.0, 's', 'A', BRN, 'Bourns MF-MSMF260/16X trip time; selected RUILON part is not covered'),
    'ipc_k_ext': _e(0.048, '1', 'A', IPC, 'secondary calculator quotes IPC-2221 external-layer fit; standard not read'),
    'ipc_b': _e(0.44, '1', 'A', IPC, 'secondary calculator quotes IPC-2221 exponent; standard not read'),
    'ipc_c': _e(0.725, '1', 'A', IPC, 'secondary calculator quotes IPC-2221 exponent; standard not read'),
    'ipc_mil_per_oz': _e(1.378, 'mil/oz', 'A', IPC, 'secondary calculator quotes copper-weight conversion; no finished stack-up evidence'),
    'tvs_vc': _e(26.0, 'V', 'A', NONE, 'SMBJ16A maximum clamping voltage at its peak pulse current (about 23 A, 600 W class); datasheet fetch returned 404. Verify'),
    'tvs_vwm': _e(16.0, 'V', 'A', NONE, 'SMBJ16A stand-off voltage'),
    'q1_rds': _e(0.013, 'ohm', 'A', AOS, '13 mohm at -10 V belongs to AOS AO4407A; selected PFET is MSKSEMI AO4407A, not covered by this datasheet'),
    'q1_rds_6v': _e(0.017, 'ohm', 'A', AOS, '17 mohm at -6 V belongs to AOS AO4407A; selected MSKSEMI PFET is not covered'),
    'd2_vf': _e(0.50, 'V', 'A', NONE, 'B540C forward drop at about 3 to 5 A, 25 C; datasheet fetch returned 404. Verify'),
    'd7_vf_100ma': _e(0.30, 'V', 'A', NONE, 'BAT60A-class Schottky forward drop at 100 mA, about 0.3 V; not fetched'),
    'd7_vf_slope': _e(0.05, 'V/decade', 'A', NONE, 'forward drop change per decade of current'),
    'rs1_tol': _e(0.01, '1', 'A', NONE, 'RS1 0.1R 1 % (design.py value text)'),
    'rs1_tcr': _e(100e-6, '1/K', 'A', NONE, '2512 metal-element shunt TCR, 50 to 100 ppm/K typical; not fetched'),
    'rs1_rating': _e(2.0, 'W', 'A', NONE, 'design.py value text "0.1R 1% 2W"'),
    'mc_ridley': _e(1.5, '1', 'A', NONE, 'ramp factor mc = 1 + Se/Sn for the sampled current-loop term (Ridley), internal slope not published'),
    'ibus_5v_idle': _e(0.001, 'A', 'A', NONE, '74AHCT1G125 supply current is microamps; 1 mA allowed for the buffer plus R12'),
    # ---- buck-design physical inputs -----------------------------------------------------------
    'buck_servo_lead_resistance_ohm': _e(0.030, 'ohm', 'A', NONE, 'assumed, not sourced: servo lead and plug resistance'),
    'buck_feedback_resistor_tolerance': _e(0.001, '1', 'A', NONE, 'design.py resistor value text specifies 0.1 percent'),
    'buck_nominal_load_a': _e(1.0, 'A', 'A', NONE, 'assumed, not sourced: nominal loop-analysis load'),
    'buck_nominal_input_v': _e(12.0, 'V', 'A', NONE, 'assumed, not sourced: nominal adapter voltage'),
    'buck_load_min_a': _e(0.05, 'A', 'A', NONE, 'assumed, not sourced: loop sweep load corner'),
    'buck_load_light_a': _e(0.15, 'A', 'A', NONE, 'assumed, not sourced: loop sweep load corner'),
    'buck_load_half_a': _e(0.5, 'A', 'A', NONE, 'assumed, not sourced: loop sweep load corner'),
    'buck_load_two_a': _e(2.0, 'A', 'A', NONE, 'assumed, not sourced: loop sweep load corner'),
    'buck_load_max_a': _e(4.0, 'A', 'A', NONE, 'assumed, not sourced: loop sweep load corner'),
    'buck_bulk_esr_min_ohm': _e(0.02, 'ohm', 'A', NONE, 'assumed, not sourced: bulk-capacitor ESR sweep corner'),
    'buck_bulk_esr_max_ohm': _e(0.20, 'ohm', 'A', NONE, 'assumed, not sourced: bulk-capacitor ESR sweep corner'),
    'buck_bulk_scale_min': _e(0.8, '1', 'A', NONE, 'c12_tol lower capacitance factor'),
    'buck_bulk_scale_max': _e(1.2, '1', 'A', NONE, 'c12_tol upper capacitance factor'),
    'buck_ceramic_factor_min': _e(0.3, '1', 'A', NONE, 'assumed, not sourced: ceramic bias sweep corner'),
    'buck_ceramic_factor_mid': _e(0.65, '1', 'A', NONE, 'assumed, not sourced: ceramic bias sweep midpoint'),
    'buck_input_min_v': _e(10.8, 'V', 'A', NONE, 'assumed, not sourced: adapter low-voltage corner'),
    'buck_input_max_v': _e(13.2, 'V', 'A', NONE, 'assumed, not sourced: adapter high-voltage corner'),
    'buck_phase_margin_min_deg': _e(45.0, 'deg', 'A', NONE, 'assumed, not sourced: loop stability acceptance limit'),
    'buck_gain_margin_min_db': _e(10.0, 'dB', 'A', NONE, "owner decision 2026-10-19: keep 10 dB, the design module's acceptance limit; worst computed gain margin 19.50 dB"),
    'tps_en_i1_min': _e(0.58e-6, 'A', 'S', TPS, 'EN pull-up current minimum'),
    'tps_en_i1_max': _e(1.8e-6, 'A', 'S', TPS, 'EN pull-up current maximum'),
    'tps_en_ihys_min': _e(2.2e-6, 'A', 'S', TPS, 'EN hysteresis current minimum'),
    'tps_en_ihys_max': _e(4.5e-6, 'A', 'S', TPS, 'EN hysteresis current maximum'),
    'buck_load_resistance_floor_ohm': _e(0.001, 'ohm', 'A', NONE, 'assumed, not sourced: numerical load-resistance floor'),
    # ---- power-budget physical inputs ----------------------------------------------------------
    'power_external_3v3_load_a': _e(0.010, 'A', 'A', NONE, 'assumed, not sourced: INA219, LED, FSR divider, pull-up and miscellaneous load'),
    'power_starting_efficiency': _e(0.85, '1', 'A', NONE, 'assumed, not sourced: fixed-point iteration starting efficiency'),
    'power_rating_margin_factor': _e(1.25, '1', 'A', NONE, 'assumed, not sourced: adapter rating margin'),
    'power_five_volt_rail_v': _e(5.0, 'V', 'A', NONE, 'MCP1703A fixed output selected in design.py'),
    'power_3v3_rail_v': _e(3.3, 'V', 'A', NONE, 'DevKitC regulated rail nominal voltage'),
    'power_ldo_dropout_scale_cap': _e(1.6, '1', 'A', NONE, 'assumed, not sourced: linear dropout extrapolation cap'),
    'power_usb_min_v': _e(4.75, 'V', 'A', NONE, 'assumed, not sourced: USB supply low corner'),
    'power_usb_max_v': _e(5.25, 'V', 'A', NONE, 'assumed, not sourced: USB supply high corner'),
    'power_fsr_force_low_n': _e(5.0, 'N', 'A', NONE, 'firmware force-control setpoint'),
    'power_fsr_force_high_n': _e(8.0, 'N', 'A', NONE, 'assumed, not sourced: FSR error high-force scenario'),
    'power_3v3_minus_1pct_mv': _e(3267.0, 'mV', 'A', NONE, 'derived from nominal 3.3 V rail and assumed one-percent tolerance'),
    'power_3v3_plus_1pct_mv': _e(3333.0, 'mV', 'A', NONE, 'derived from nominal 3.3 V rail and assumed one-percent tolerance'),
    'power_3v3_minus_3pct_mv': _e(3201.0, 'mV', 'A', MCP, '3 percent is from the 5 V MCP1703A, not the DevKitC 3.3 V regulator; value retained as an assumed scenario'),
    'power_regen_min_mj': _e(2.0, 'mJ', 'A', NONE, 'assumed, not sourced: regeneration sweep point'),
    'power_regen_low_mj': _e(5.0, 'mJ', 'A', NONE, 'assumed, not sourced: regeneration sweep point'),
    'power_regen_basis_mj': _e(20.0, 'mJ', 'A', NONE, 'assumed, not sourced: half stall torque through one degree backlash'),
    'power_regen_high_mj': _e(50.0, 'mJ', 'A', NONE, 'assumed, not sourced: regeneration sweep point'),
    'power_regen_rotor_mj': _e(174.0, 'mJ', 'A', NONE, 'docs/gripper/analysis/dyno.md reflected rotor kinetic energy'),
    'power_switch_transition_time_s': _e(10e-9, 's', 'A', NONE, 'assumed, not sourced: total TPS54560B switching transition time'),
    'power_log_current_floor_a': _e(0.001, 'A', 'A', NONE, 'assumed, not sourced: diode logarithm current floor'),
    'power_diode_reference_current_a': _e(0.1, 'A', 'A', NONE, 'd7_vf_100ma reference current'),
    'power_ldo_full_load_dropout_ratio': _e(1.1, '1', 'A', NONE, 'assumed, not sourced: AMS1117 full-load to light-load dropout ratio'),
    'power_ldo_light_load_a': _e(0.1, 'A', 'A', NONE, 'assumed, not sourced: AMS1117 light-load interpolation point'),
    'power_ldo_load_span_a': _e(0.7, 'A', 'A', NONE, 'assumed, not sourced: AMS1117 dropout interpolation span'),
    'power_fit_a_stall_current_a': _e(3.45, 'A', 'A', NONE, 'docs/gripper/analysis/dyno.md Fit A stall at regulated voltage'),
    'power_ground_wire_length_m': _e(1.2, 'm', 'A', NONE, 'design.py cable length'),
    'power_fsr_return_current_a': _e(0.0009, 'A', 'A', NONE, 'assumed, not sourced: FSR return current'),
    'power_board_plane_resistance_ohm': _e(0.005, 'ohm', 'A', NONE, 'assumed, not sourced: board ground-plane resistance'),
    # ---- INA219-budget physical inputs -------------------------------------------------------
    'ina_trip_current_a': _e(3.0, 'A', 'A', NONE, 'firmware/gripper/config.h STALL_CURRENT_A'),
    'ina_trip_window_s': _e(0.100, 's', 'A', NONE, 'firmware STALL_CURRENT_MS'),
    'ina_control_period_s': _e(0.020, 's', 'A', NONE, 'firmware current-reading period'),
    'ina_force_caps_n': _e((10.0, 8.0), 'N', 'A', NONE, 'force caps swept by fsr_frontend.py and ina219_budget.py: element 0 is firmware F_CAP_N 10 (squeeze-cap sizing constant, config.h), element 1 is the R15 cap, 8 N (Douglas 2026-10-12, DESIGN-BASIS R15)'),
    'ina_gain_temperature_span_c': _e(40.0, 'C', 'A', NONE, 'assumed, not sourced'),
    'ina_shunt_temperature_rise_c': _e(45.0, 'C', 'A', NONE, 'assumed, not sourced'),
    'ina_input_impedance_ohm': _e(320e3, 'ohm', 'S', INA, 'INA219 input impedance'),
    'ina_saturation_error_fraction': _e(0.01, '1', 'A', NONE, 'assumed, not sourced'),
    'ina_detection_limit_s': _e(0.200, 's', 'A', NONE, 'firmware detection requirement R20'),
    'ina_chop_frequencies_hz': _e((300.0, 1000.0, 3000.0, 20000.0), 'Hz', 'A', NONE,
                                  'assumed, not sourced: unpublished servo-drive chop frequencies'),
    'ina_chop_duty': _e(0.5, '1', 'A', NONE, 'assumed, not sourced: chopped-current duty cycle'),
    'ina_average_codes_samples': _e(((0x8, 1), (0x9, 2), (0xA, 4), (0xB, 8),
                                     (0xC, 16), (0xD, 32), (0xE, 64), (0xF, 128)),
                                    'code,count', 'S', INA, 'SADC averaging codes and sample counts'),
    'ina_average_fit_limit_s': _e(0.0195, 's', 'A', NONE, 'assumed, not sourced'),
    'ina_recommended_sadc_code': _e(0xD, 'code', 'A', NONE, 'selected 32-sample SADC setting'),
    'ina_sadc_mask': _e(0xF, 'code', 'S', INA, 'four-bit SADC field mask'),
    'ina_sadc_shift': _e(3, 'bit', 'S', INA, 'SADC field starts at configuration bit 3'),
    # ---- trace-width physical inputs ---------------------------------------------------------
    'trace_supply_current_a': _e(2.2, 'A', 'A', NONE, 'servo_stall_a design input'),
    'trace_auxiliary_current_a': _e(5.0, 'A', 'A', NONE, 'assumed, not sourced'),
    'trace_temperature_rises_c': _e((10.0, 20.0), 'C', 'A', NONE, 'assumed, not sourced'),
    'trace_hold_current_a': _e(1.35, 'A', 'A', NONE, 'docs/gripper/analysis/dyno.md Fit A hold current'),
    'trace_via_plating_um': _e(25.0, 'um', 'A', NONE, 'assumed, not sourced: typical 1 oz class fab'),
    'trace_via_drill_mm': _e(0.4, 'mm', 'A', NONE, 'assumed, not sourced'),
    'trace_reference_length_mm': _e(10.0, 'mm', 'A', NONE, 'assumed, not sourced'),
    'trace_reference_temperature_c': _e(20.0, 'C', 'A', NONE, 'cu_rho reference temperature'),
    'trace_ambient_temperature_c': _e(25.0, 'C', 'A', NONE, 'assumed, not sourced'),
    'trace_mm_per_mil': _e(0.0254, 'mm/mil', 'A', NONE, 'standard unit conversion'),
    # ---- calculation assumptions formerly embedded in modules -------------------------------
    'droop_comp_zero_v': _e(0.6, 'V', 'A', NONE, 'droop_sim.py: COMP voltage at zero peak current'),
    'droop_5v_load_a': _e(0.100, 'A', 'A', NONE, 'droop_sim.py: constant 5 V and ESP32 load'),
    'droop_servo_idle_a': _e(0.15, 'A', 'A', NONE, 'droop_sim.py: moving no-load servo current'),
    'droop_step_time_s': _e(3e-3, 's', 'A', NONE, 'droop_sim.py: load-step start time'),
    'droop_end_time_s': _e(15e-3, 's', 'A', NONE, 'droop_sim.py: simulation end time'),
    'droop_diode_v': _e(0.5, 'V', 'A', NONE, 'droop_sim.py: freewheel diode drop'),
    'droop_fsw_hz': _e(399.8e3, 'Hz', 'A', NONE, 'droop_sim.py: implemented switching frequency'),
    'droop_default_rise_s': _e(1e-3, 's', 'A', NONE, 'droop_sim.py: default servo-current rise time'),
    'droop_default_vin_v': _e(12.0, 'V', 'A', NONE, 'droop_sim.py: nominal input voltage'),
    'droop_fast_rise_s': _e(10e-6, 's', 'A', NONE, 'droop_sim.py: fast load-step scenario'),
    'droop_no_wrist_cap_f': _e(1e-6, 'F', 'A', NONE, 'droop_sim.py: numerical stand-in when wrist capacitance is absent'),
    'droop_voltage_floor_v': _e(0.1, 'V', 'A', NONE, 'droop_sim.py: averaged-model switching voltage floor'),
    'droop_recovery_band_v': _e(0.15, 'V', 'A', NONE, 'droop_sim.py: recovery-time voltage band'),
    'droop_sweep_cap_220_f': _e(220e-6, 'F', 'A', NONE, 'droop_sim.py: bulk-capacitance sweep point'),
    'droop_sweep_cap_470_f': _e(470e-6, 'F', 'A', NONE, 'droop_sim.py: bulk-capacitance sweep point'),
    'droop_sweep_cap_1000_f': _e(1000e-6, 'F', 'A', NONE, 'droop_sim.py: bulk-capacitance sweep point'),
    'droop_sweep_cap_2200_f': _e(2200e-6, 'F', 'A', NONE, 'droop_sim.py: bulk-capacitance sweep point'),
    'droop_low_vin_v': _e(10.8, 'V', 'A', NONE, 'droop_sim.py: low-input-voltage scenario'),
    'fsr_default_vcc_mv': _e(3300.0, 'mV', 'A', NONE, '_common.py: default divider supply'),
    'servo_hold_torque_nm': _e(0.758, 'N*m', 'A', NONE, '_common.py: dyno.md section 0, 5 N setpoint plus 2 N tension'),
    'gripper_pad_radius_m': _e(0.065, 'm', 'A', NONE, '_common.py: firmware config.h R_C_MM'),
    'gripper_train_efficiency': _e(0.85, '1', 'A', NONE, '_common.py: firmware config.h ETA_TRAIN'),
    'fsr_fit_r1n_ohm': _e(6109.0, 'ohm', 'A', NONE, '_common.py: firmware config.h FSR_FIT_R1N_OHM'),
    'fsr_fit_exponent': _e(0.8195, '1', 'A', NONE, '_common.py: firmware config.h FSR_FIT_EXP'),
    'fsr_adc_min_mv': _e(150.0, 'mV', 'S', ESP, '_common.py: effective ADC range lower endpoint'),
    'fsr_adc_max_mv': _e(2450.0, 'mV', 'S', ESP, '_common.py: effective ADC range upper endpoint'),
    # ---- fsr_frontend.py and harness.py literals moved here (four-class rule) -------------------
    'fsr_table_forces_n': _e((0.2, 0.5, 3.0, 5.0, 8.0, 10.0), 'N', 'A', NONE, 'fsr_frontend.py: force points tabulated; analysis choice; assumed, not sourced'),
    'fsr_unloaded_force_n': _e(0.0, 'N', 'A', NONE, 'fsr_frontend.py: unloaded FSR (open circuit) case of the filter table; assumed, not sourced'),
    'fsr_resolution_force_n': _e(5.0, 'N', 'A', NONE, 'fsr_frontend.py: force at which resolution is reported; assumed, not sourced'),
    'fsr_filter_gain_freqs_hz': _e((50.0, 500.0, 1000.0), 'Hz', 'A', NONE, 'fsr_frontend.py: frequencies at which filter gain is tabulated; assumed, not sourced'),
    'ctrl_lag_budget_s': _e(0.076, 's', 'A', NONE, 'fsr_frontend.py: firmware config.h CTRL_LAG_COMP_S; assumed, not sourced (repo file, no vendor document)'),
    'ema_alpha': _e(0.10, '1', 'A', NONE, 'fsr_frontend.py: firmware config.h FSR_EMA_ALPHA; assumed, not sourced (repo file, no vendor document)'),
    'fsr_sample_rate_hz': _e(1000.0, 'Hz', 'A', NONE, 'fsr_frontend.py: firmware FSR sampling and EMA rate (config.h: EMA at 1 kHz); assumed, not sourced'),
    'fsr_e96_search_lo_ohm': _e(1500.0, 'ohm', 'A', NONE, 'fsr_frontend.py: lower edge of the R15 E96 search window; assumed, not sourced'),
    'fsr_e96_search_hi_ohm': _e(6000.0, 'ohm', 'A', NONE, 'fsr_frontend.py: upper edge of the R15 E96 search window; assumed, not sourced'),
    'esp_adc_resolution_bits': _e(12, 'bit', 'A', NONE, 'fsr_frontend.py and harness.py: ESP32 ADC resolution as used here; assumed, not sourced'),
    'harness_awg_power': _e(20, 'AWG', 'A', NONE, 'harness.py: trunk gauge of the servo power pair; design choice; assumed, not sourced'),
    'harness_awg_pigtail': _e(22, 'AWG', 'A', NONE, 'harness.py: servo extension lead pigtail gauge, not stated by the seller; assumed, not sourced'),
    'harness_awg_signal': _e(26, 'AWG', 'A', NONE, 'harness.py: signal conductor gauge; design choice; assumed, not sourced'),
    'harness_spare_fraction': _e(0.15, '1', 'A', NONE, 'harness.py: spare wire length bought (brief); assumed, not sourced'),
    'harness_pigtail_mm': _e(100.0, 'mm', 'A', NONE, 'harness.py: extension lead cut-off length kept with the male plug; assumed, not sourced'),
    'harness_fsr_run_mm': _e(150.0, 'mm', 'A', NONE, 'harness.py: SM receptacle to the Clincher on finger B, with the service loop; assumed, not sourced'),
    'harness_limit_run_mm': _e(120.0, 'mm', 'A', NONE, 'harness.py: SM receptacle to the microswitch; assumed, not sourced'),
    'harness_cap_lead_mm': _e(10.0, 'mm', 'A', NONE, 'harness.py: capacitor lead length left after trimming; assumed, not sourced'),
    'harness_unwired_length_mm': _e(0, 'mm', 'A', NONE, 'harness.py: wire length of a connector row with no wire; assumed, not sourced'),
    'harness_adapter_cord_mm': _e(1500.0, 'mm', 'A', 'https://www.pololu.com/product/1774', 'seller page specifies 1.5 m, but the generic adapter has no manufacturer datasheet or length tolerance'),
    'harness_usb_cable_mm': _e(914.0, 'mm', 'A', 'https://www.adafruit.com/product/592', 'seller page says approximately 3 feet / 1 meter; 914 mm is an exact conversion of the approximate feet figure'),
    'harness_od_26awg_mm': _e(1.5, 'mm', 'A', 'https://www.adafruit.com/product/1877', '26 AWG silicone wire outer diameter needs a manufacturer datasheet or measurement'),
    'harness_bend_factor': _e(10.0, '1', 'A', NONE, 'harness.py: dynamic minimum bend radius in outer diameters; sourcing.EVIDENCE flex_wire (secondary page, tagged A there); assumed, not sourced'),
    'harness_bend_factor_abs': _e(5.0, '1', 'A', NONE, 'harness.py: absolute minimum bend radius in outer diameters (Parker Trilogy per sourcing.EVIDENCE flex_wire, tagged A there); assumed, not sourced'),
    'harness_jaw_max_deg': _e(20.0, 'deg', 'A', NONE, 'harness.py: open end of the jaw range, DESIGN-BASIS R18; assumed, not sourced'),
    'harness_cycle_s': _e(35.0, 's', 'A', NONE, 'harness.py: grip cycle length, DESIGN-BASIS section 7; assumed, not sourced'),
    'harness_design_life_cycles': _e(1e5, '1', 'A', NONE, 'harness.py: design life in grips, DESIGN-BASIS section 7 R25; assumed, not sourced'),
    'harness_semester_fraction': _e(0.1, '1', 'A', NONE, 'harness.py: a semester is about 1/10 of the design life, DESIGN-BASIS section 7; assumed, not sourced'),
    'harness_plug_band_v': _e((6.35, 6.65), 'V', 'A', NONE, 'the one home of the servo plug band (low, high): harness.py, power_budget.py and margins.py rows; assumed, not sourced'),
    'harness_force_error_limit_n': _e(0.1, 'N', 'A', NONE, 'margins.py force-reading-error row limit; assumed, not sourced: acceptable FSR force-reading error'),
    'buck_junction_rise_limit_c': _e(85.0, 'C', 'A', NONE, 'margins.py buck-thermal row limit; assumed, not sourced: allowed U1 junction rise'),
    'trace_temp_rise_limit_c': _e(10.0, 'C', 'A', NONE, 'margins.py trace-temperature row limit; assumed, not sourced: allowed wide-trace temperature rise'),
    'trace_servo_drop_limit_mv': _e(100.0, 'mV', 'A', NONE, 'margins.py trace-drop row limit; assumed, not sourced: allowed servo path drop at stall'),
    'ina_current_error_limit_a': _e(0.05, 'A', 'A', NONE, 'margins.py current-error row limit; assumed, not sourced: allowed current-reading error'),
    'adapter_min_v': _e(12.0, 'V', 'A', NONE, 'margins.py uvlo-range row limit; assumed, not sourced: lowest adapter voltage the UVLO start must stay under'),
    'adapter_current_a': _e(3.0, 'A', 'A', NONE, 'margins.py adapter-current row limit default; assumed, not sourced: adapter current rating'),
    'fsr_adc_droop_limit_mv': _e(1, 'mV', 'A', NONE, 'margins.py adc-charge row limit; assumed, not sourced: acceptable ADC reservoir droop at 2450 mV'),
    'harness_plug_rating_v': _e(6.8, 'V', 'A', NONE, 'harness.py: servo voltage rating, power_budget.py; assumed, not sourced'),
    'harness_servo_v_min': _e(4.8, 'V', 'A', NONE, 'harness.py: servo minimum supply, droop_sim.py figure and dyno.md; assumed, not sourced'),
    'harness_pwm_current_a': _e(1e-3, 'A', 'A', NONE, 'harness.py: SERVO_PWM wire current, 5 V into the servo input behind R13 100 ohm; assumed, not sourced'),
    'harness_fsr_force_cap_n': _e(8.0, 'N', 'A', NONE, 'harness.py: R15 force cap at which FSR current is sized, DESIGN-BASIS R15, ruled 8 N by Douglas 2026-10-12'),
    'harness_vil_fraction': _e(0.25, '1', 'A', NONE, 'harness.py: ESP32 input-low threshold as a fraction of VDD, from memory, to verify; assumed, not sourced'),
    'harness_fsr_error_forces_n': _e((5.0, 8.0), 'N', 'A', NONE, 'harness.py: forces at which the series-wire FSR error is reported; assumed, not sourced'),
    'harness_servo_lead_ohm': _e(0.0, 'ohm', 'A', NONE, 'harness.py: selected servo lead resistance, not recorded and excluded from the path; assumed, not sourced'),
    'fit_a_resistance_ohm': _e(1.80, 'ohm', 'A', NONE, '_common.py: dyno motor fit A'),
    'fit_a_torque_nm_per_a': _e(0.861, 'N*m/A', 'A', NONE, '_common.py: dyno motor fit A'),
    'fit_a_hold_a': _e(1.35, 'A', 'A', NONE, '_common.py: dyno hold row'),
    'fit_b_resistance_ohm': _e(3.09, 'ohm', 'A', NONE, '_common.py: dyno motor fit B'),
    'fit_b_torque_nm_per_a': _e(1.474, 'N*m/A', 'A', NONE, '_common.py: dyno motor fit B'),
    'fit_b_stall_a': _e(2.2, 'A', 'A', NONE, '_common.py: dyno motor fit B'),
    'fit_b_hold_a': _e(0.80, 'A', 'A', NONE, '_common.py: dyno hold row'),
    'wire_gauges_awg': _e((20, 26), 'AWG', 'A', NONE, 'assumed, not sourced: compared harness gauges'),
    'buck_candidate_r_ohm': _e((4.7e3, 8.2e3, 12e3, 18e3, 27.4e3, 39e3), 'ohm', 'A', NONE,
                               'assumed, not sourced: compensation resistor candidates'),
    'buck_candidate_c_f': _e((10e-9, 22e-9, 47e-9, 100e-9), 'F', 'A', NONE,
                             'assumed, not sourced: compensation capacitor candidates'),
    'buck_candidate_pole_f': _e((47e-12, 100e-12, 220e-12, 470e-12, 1e-9), 'F', 'A', NONE,
                                'assumed, not sourced: compensation pole capacitor candidates'),
    'buck_phase_score_cap_deg': _e(90, 'degree', 'A', NONE,
                                   'assumed, not sourced: compensation ranking cap'),
    'buck_gain_score_cap_db': _e(30, 'dB', 'A', NONE,
                                 'assumed, not sourced: compensation ranking cap'),
}


def val(name):
    return C[name]['value']


def main():
    print('%-20s %-14s %-3s %s' % ('name', 'value', 'tag', 'unit / note'))
    for k, e in C.items():
        print('%-20s %-14s [%s] %s | %s' % (k, e['value'], e['tag'], e['unit'], e['note']))
    n_a = [k for k, e in C.items() if e['tag'] == 'A']
    print('\n%d entries, %d tagged A: %s' % (len(C), len(n_a), ', '.join(n_a)))


def run():
    return {k: dict(e) for k, e in C.items()}


def report(res):
    main()


if __name__ == '__main__':
    main()
