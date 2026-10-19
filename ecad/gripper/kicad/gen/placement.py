"""Board outline, part placement and routing classes for the gripper controller board.

Coordinates are board-local millimetres, origin at the top-left board corner, y down. Rotation is
KiCad's (degrees, counter-clockwise seen from the top). Every through-hole header sits on a 1.27 mm
multiple so the router's 0.127 mm grid lands on pad centres and on the midline between pads.

Floor plan (top view):
  top strip, left to right   12 V in (J1 barrel, J2 screw) -> F1 -> Q1 -> D1, C1..C4 -> U1 buck -> L1
  right column, top to bottom  C8/C9 -> RS1 shunt (R8/R9 Kelvin taps, U2 INA219) -> C12 -> J3 servo
  bottom left                ESP32-DevKitC on sockets, USB to the left, antenna to the right
  bottom right               sensor connector J4, FSR divider, button, LED, expansion headers
  middle                     5 V regulator U3, PWM buffer U4, test-point row
The servo current loop (C8, C9, C12, RS1, J3) stays in the right column; the FSR divider and its
filter return to ground at the DevKitC pins on the opposite side of the board.
"""

BOARD_W = 100.0
BOARD_H = 85.0
ORIGIN = (50.8, 50.8)          # where the board's top-left corner sits on the KiCad page, mm

# ref: (x, y, rotation, side of the footprint the reference text sits on)
PLACE = {
    'H1': (4.0, 4.0, 0, 'N'), 'H2': (96.0, 4.0, 0, 'N'), 'H3': (4.0, 81.0, 0, 'N'), 'H4': (96.0, 81.0, 0, 'N'),
    # 12 V input and protection
    'J1': (15.24, 13.97, 270, 'B'),
    'J2': (6.35, 26.67, 270, 'R'),
    'F1': (22.86, 13.97, 0, 'T'),
    'Q1': (31.75, 13.97, 180, 'T'),
    'R1': (38.1, 8.89, 0, 'T'),
    'DZ1': (38.1, 11.43, 180, 'R'),
    'D1': (41.91, 17.78, 270, 'B'),
    'C1': (49.53, 12.7, 270, 'T'),
    'C2': (56.515, 14.605, 270, 'T'),
    'C3': (60.325, 14.605, 270, 'T'),
    'C4': (63.5, 13.97, 270, 'T'),
    # buck
    'U1': (69.215, 13.97, 0, 'T2'),
    'C7': (69.215, 9.525, 0, 'T'),
    'L1': (82.55, 11.43, 0, 'T'),
    'D2': (76.2, 23.495, 270, 'B'),
    'R2': (64.77, 18.415, 0, 'L'), 'R3': (64.77, 20.955, 180, 'L'), 'R4': (64.77, 23.495, 180, 'L'),
    'R5': (69.85, 18.415, 0, 'N'), 'C5': (69.85, 20.955, 0, 'N'), 'C6': (69.85, 23.495, 0, 'N'),
    'R7': (69.85, 26.035, 0, 'N'), 'R24': (69.85, 28.575, 0, 'N'), 'R6': (69.85, 31.115, 0, 'N'),
    # output, shunt, current monitor
    'C8': (86.36, 21.59, 180, 'R'), 'C9': (86.36, 25.4, 180, 'R'),
    'RS1': (92.71, 26.035, 270, 'T'),
    'R8': (97.155, 24.765, 0, 'T'), 'R9': (97.155, 27.305, 0, 'N'),
    'C10': (97.98, 29.845, 90, 'L'),
    'U2': (94.615, 34.925, 0, 'N'),
    'C11': (89.535, 30.48, 270, 'N'),
    'C12': (86.36, 34.29, 180, 'N'),
    'C13': (85.09, 41.91, 0, 'L'),
    'D8': (83.82, 46.99, 180, 'T'),
    'J3': (93.98, 52.07, 90, 'N'),
    'J7': (76.2, 43.18, 0, 'T'),
    # 5 V rail and PWM buffer
    'U3': (22.225, 36.83, 0, 'T'),
    'C14': (15.24, 34.29, 0, 'T'), 'C15': (15.24, 39.37, 180, 'T'), 'D7': (15.24, 42.545, 0, 'L'),
    'U4': (68.58, 44.45, 0, 'B'),
    'C16': (68.58, 41.275, 180, 'T'),
    'R12': (64.135, 44.45, 0, 'T'),
    'R13': (72.39, 46.99, 0, 'N'), 'R14': (72.39, 49.53, 0, 'N'), 'D3': (72.39, 52.07, 0, 'B'),
    'R10': (59.69, 37.465, 180, 'T'), 'R11': (59.69, 40.005, 180, 'B'),
    # MCU
    'U5': (35.56, 67.31, 270, 'N'),
    # sensors and I/O
    'R16': (46.355, 50.8, 0, 'L'), 'C17': (49.53, 50.8, 0, 'R'),
    'R18': (33.655, 50.8, 0, 'L'), 'C18': (36.83, 50.8, 0, 'R'),
    'SW1': (68.58, 60.325, 0, 'T'),
    'R19': (72.39, 68.58, 0, 'L'), 'R20': (72.39, 70.485, 0, 'L'), 'C19': (72.39, 72.39, 0, 'L'),
    'J4': (77.47, 80.645, 0, 'N'),
    'D4': (76.2, 75.565, 180, 'T'), 'R15': (80.01, 75.565, 0, 'T'), 'R17': (84.455, 75.565, 0, 'T'),
    'D5': (88.9, 75.565, 0, 'T'),
    'R21': (66.04, 78.74, 0, 'T'), 'D6': (66.04, 81.28, 0, 'B'),
    'J5': (91.44, 60.96, 0, 'B'),
    'R22': (86.36, 60.96, 180, 'T'), 'C20': (86.36, 62.865, 0, 'N'), 'R23': (86.36, 64.77, 0, 'B'),
    'J6': (97.155, 57.15, 0, 'N'),
    # test points: a row above the DevKitC, plus the three power rails where they are made
    'TP4': (11.43, 46.99, 0, 'N'), 'TP6': (15.24, 46.99, 0, 'N'), 'TP5': (19.05, 46.99, 0, 'N'),
    'TP13': (22.86, 46.99, 0, 'N'), 'TP14': (26.67, 46.99, 0, 'N'), 'TP15': (30.48, 46.99, 0, 'N'),
    'TP16': (34.29, 46.99, 0, 'N'), 'TP12': (38.1, 46.99, 0, 'N'), 'TP11': (41.91, 46.99, 0, 'N'),
    'TP10': (45.72, 46.99, 0, 'N'), 'TP9': (49.53, 46.99, 0, 'N'), 'TP7': (53.34, 46.99, 0, 'N'),
    'TP1': (46.99, 24.13, 0, 'N'), 'TP2': (81.915, 23.495, 0, 'N'),
    'TP3': (81.28, 52.07, 0, 'N'), 'TP8': (85.09, 52.07, 0, 'N'),
}

# Silkscreen label next to each test point (the net it probes) and each connector pin-out.
TP_LABEL = {'TP1': 'VIN', 'TP2': 'VBUCK', 'TP3': 'VSRV', 'TP4': '5V', 'TP5': '3V3', 'TP6': 'GND', 'TP7': 'GND',
            'TP8': 'GND', 'TP9': 'PWM5', 'TP10': 'PWM3', 'TP11': 'FSRS', 'TP12': 'FSRA', 'TP13': 'SDA',
            'TP14': 'SCL', 'TP15': 'BTN', 'TP16': 'LIM'}

# (text, x, y, size mm, rotation)
SILK = [
    ('SO-101 GRIPPER CTRL  rev A', 42.0, 29.5, 1.5, 0),
    ('12V IN  centre +', 10.0, 22.6, 0.9, 0),
    ('+12V', 15.5, 26.67, 1.0, 0), ('GND', 15.2, 30.6, 1.0, 0),
    ('J3 top to bottom: SIG 6.5V GND', 84.0, 56.8, 0.8, 0),
    ('J4: 3V3 FSR LIM GND', 81.5, 72.8, 0.8, 0),
    ('G', 78.7, 43.18, 0.8, 0), ('+', 78.7, 45.72, 0.8, 0), ('S', 78.7, 48.26, 0.8, 0),
    ('FB', 88.75, 60.96, 0.8, 0), ('3V', 88.75, 63.5, 0.8, 0), ('G', 88.75, 66.04, 0.8, 0),
    ('A1', 94.25, 57.15, 0.8, 0), ('A2', 94.25, 59.69, 0.8, 0), ('SL', 94.25, 62.23, 0.8, 0),
    ('FL', 94.25, 64.77, 0.8, 0), ('EA', 94.25, 67.31, 0.8, 0), ('EB', 94.25, 69.85, 0.8, 0),
    ('3V', 94.25, 72.39, 0.8, 0), ('G', 94.25, 74.93, 0.8, 0),
    ('ANT keep clear', 60.3, 67.31, 0.8, 90),
]

# Rule area under the ESP32 module antenna: no copper on either layer.
ANTENNA_KEEPOUT = (57.6, 58.6, 63.4, 76.0)

# Routing classes. Wide nets carry the servo or input current; pins not listed in WIDE_PINS are light
# branches (sense taps, small capacitors, test points) and get the signal width.
W_SIGNAL = 0.25
W_LOGIC_POWER = 0.4
W_WIDE = 2.0
W_NECK = 0.6
NECK_REACH = 2.5

WIDE_PINS = {
    'VIN_RAW': ['J1.1', 'F1.1', 'J2.1'],
    'VIN_F': ['F1.2', 'Q1.5', 'Q1.6', 'Q1.7', 'Q1.8'],
    'VIN_P': ['Q1.1', 'Q1.2', 'Q1.3', 'D1.1', 'C1.1', 'C2.1', 'C3.1', 'U1.2'],
    'SW': ['U1.8', 'L1.1', 'D2.1'],
    'V_BUCK': ['L1.2', 'C8.1', 'C9.1', 'RS1.1'],
    'SERVO_V': ['RS1.2', 'C12.1', 'J3.2', 'D8.1', 'J7.2'],
}
LOGIC_POWER_NETS = ['+5V', 'DEVKIT_5V', '+3V3']
# Nets routed before the general signals, in this order.
FIRST_NETS = ['SNS_P', 'SNS_N', 'BOOT', 'COMP', 'COMP_RC', 'FB', 'FB_MID', 'EN', 'RT', 'Q1_G', 'FSR_ADC', 'FSR_SIG']

# Ground vias per surface-mount ground pad (default 1). Pads that return switching or servo current get more.
GND_VIAS = {'D2.2': 4, 'C2.2': 2, 'C3.2': 2, 'C8.2': 3, 'C9.2': 3, 'D1.2': 2, 'D8.2': 2, 'U3.2': 2}

# Kelvin taps: explicit thin tracks from the inner edge of each shunt pad to its filter resistor.
# (net, [(x, y), ...]) in board coordinates; the tapped pins are then treated as already connected.
KELVIN = [
    ('V_BUCK', [(93.98, 23.5), (95.245, 24.765), (96.33, 24.765)], 'R8.1'),
    ('SERVO_V', [(93.98, 28.575), (95.25, 27.305), (96.33, 27.305)], 'R9.1'),
]
