"""Part sourcing for the gripper controller: MPN, supplier, unit price, the page each was read from.

Pure data, no side effects. Keyed by the `src` key of each part in design.py.
Tag S: part number, price and ratings read from `url` on `retrieved` (2026-10-11).
Tag A: assumed or taken from a search-result snippet, not read from the page; `notes` says why.
`price_usd` is the unit price at `price_qty` (the lowest tier the page offers unless noted).
Stock was read on the same day and is stated in `notes` where it is zero or tiny.
"""

D = '2026-10-11'
LCSC = 'https://www.lcsc.com/product-detail/%s.html'
DK = 'https://www.digikey.com/en/products/detail/'
DIGI = 'DigiKey'


def s(mpn, mfr, supplier, spn, price_usd, price_qty, url, notes, datasheet=None, tag='S'):
    return {'mpn': mpn, 'mfr': mfr, 'supplier': supplier, 'spn': spn, 'price_usd': price_usd,
            'price_qty': price_qty, 'url': url, 'datasheet': datasheet or url, 'retrieved': D,
            'tag': tag, 'notes': notes}


def lc(mpn, mfr, c, price, qty, notes, tag='S', datasheet=None):
    return s(mpn, mfr, 'LCSC', c, price, qty, LCSC % c, notes + ' LCSC number is also the JLCPCB assembly part number.',
             datasheet, tag)


SRC = {
    # ---- resistors (0603)
    'r_100k': lc('0603WAF1003T5E', 'UNI-ROYAL', 'C25803', 0.0031, 100, '100 kOhm 1 % 100 mW thick film 0603; in stock.'),
    'r_100r': lc('0603WAF1000T5E', 'UNI-ROYAL', 'C22775', 0.0032, 100, '100 Ohm 1 % 100 mW thick film 0603; in stock.'),
    'r_10k': lc('RC0603FR-0710KL', 'YAGEO', 'C98220', 0.0034, 100, '10 kOhm 1 % 100 mW thick film 0603; in stock (5.0 M).'),
    'r_10r': lc('0603WAF100JT5E', 'UNI-ROYAL', 'C22859', 0.0032, 20, '10 Ohm 1 % 100 mW thick film 0603; in stock.'),
    'r_1k': lc('0603WAF1001T5E', 'UNI-ROYAL', 'C21190', 0.0026, 100, '1 kOhm 1 % 100 mW thick film 0603; in stock.'),
    'r_243k': lc('RC0603FR-07243KL', 'YAGEO', 'C137764', 0.0018, 100,
                 '243 kOhm 1 % 100 mW 0603 (R4, RT). LCSC page showed OUT OF STOCK on retrieval; an LCSC search result '
                 'snippet showed 8,700 in stock, so check the live page; any 243 kOhm 1 % 0603 is equivalent.'),
    'r_27k4': lc('CRCW060327K4FKEA', 'VISHAY', 'C843937', 0.0107, 50,
                 '27.4 kOhm 1 % 100 mW thick film 0603 (R5); in stock. Yageo RC0603FR-0727K4L (C165753, $0.0029 at 100) was out of stock.'),
    'r_294k': lc('CRCW0603294KFKEA', 'VISHAY', 'C2092132', 0.0035, 20,
                 '294 kOhm 1 % 100 mW thick film 0603 (R2); only 220 in stock on retrieval, enough for one board.'),
    'r_2k2': lc('0603WAF2201T5E', 'UNI-ROYAL', 'C4190', 0.0018, 100, '2.2 kOhm 1 % 100 mW thick film 0603; in stock.'),
    'r_330r': lc('0603WAF3300T5E', 'UNI-ROYAL', 'C23138', 0.0026, 100, '330 Ohm 1 % 100 mW thick film 0603; in stock.'),
    'r_4k7': lc('0603WAF4701T5E', 'UNI-ROYAL', 'C23162', 0.0028, 100, '4.7 kOhm 1 % 100 mW thick film 0603; in stock.'),
    'r_0r': lc('0603WAF0000T5E', 'UNI-ROYAL', 'C21189', 0.0022, 100, '0 Ohm jumper 0603. Both uses (R14, R23) are DNP.'),
    'r_43k2': s('RC0603FR-0743K2L', 'YAGEO', DIGI, '311-43.2KHRCT-ND', 0.0122, 100,
                'https://www.digikey.com/en/products/result?keywords=RC0603FR-0743K2L',
                '43.2 kOhm 1 % 0603 thick film (R3). DigiKey page read: $0.10 at 1, $0.0188 at 25, $0.0122 at 100, $0.00661 at 1,000 '
                '(cut tape); 5,000 reel $0.00469; manufacturer lead time 22 weeks; the page stock figure (26,964) was not clearly tied '
                'to this part, so check stock. Substitute listed by DigiKey: Bourns CR0603-FX-4322ELF (17,070 available). '
                'RS Online lists the same MPN (100 ppm/C, 75 V).'),
    'r_71k5_p1': s('RT0603BRD0771K5L', 'YAGEO', DIGI, 'YAG1727CT-ND', 0.10, 1,
                   'https://www.digikey.com/en/products/result?keywords=RT0603BRD0771K5L',
                   '71.5 kOhm 0.1 % thin film 0603, 25 ppm/C, 1/10 W (R6; with R24 768 Ohm in series it sets the 6.58 V servo rail). '
                   'DigiKey page read: $0.10 at 1, $0.07 at 10, $0.058 at 100; only 4 IN STOCK on retrieval, 5,000 reel $0.04304. '
                   'Future Electronics showed 0 stock and an 18 week lead time, so order early or accept a longer lead. '
                   'A 72.3 kOhm 0.1 % single part had no distributor listing, so the E96 value plus a trim resistor is used.'),
    'r_768r': s('RC0603FR-07768RL', 'YAGEO', DIGI, '311-768HRCT-ND', 0.0122, 100,
                'https://www.digikey.com/en/products/result?keywords=RC0603FR-07768RL',
                '768 Ohm 1 % thick film 0603, 100 ppm/C (R24, trim in series with R6; its 1 % adds 0.011 % to the divider). '
                'DigiKey page read: $0.10 at 1, $0.025 at 10, $0.0122 at 100, $0.00661 at 1,000 (cut tape); 26,026 in stock; reel $0.00469 at 5,000. '
                'No LCSC number found for the 0603 value in two tries (LCSC search page returned no listing).'),
    'tvs_servo': s('SMBJ7.0A', 'Littelfuse', DIGI, 'SMBJ7.0ALFCT-ND', 0.53, 1,
                   DK + 'littelfuse-inc/SMBJ7-0A/285960',
                   'Unidirectional TVS, 600 W 10/1000 us, SMB (D8, clamps the servo rail if the servo is back-driven; the buck cannot sink '
                   'current). DigiKey page read: stand-off 7.0 V, breakdown min 7.78 V, clamp max 12 V at 50 A; 33,733 in stock; $0.53 at 1, '
                   '$0.328 at 10, $0.2077 at 100. Breakdown max 8.60 V at 10 mA and maximum reverse leakage 200 uA are from a mirror page '
                   '(Semiware, Farnell/RS snippets); none states the leakage test voltage, and the Littelfuse datasheet returned HTTP 403. '
                   'Series convention is IR at the stand-off voltage, so assume 200 uA max at 7.0 V; on the 6.58 V rail expect less, but '
                   'budget up to 200 uA.',
                   datasheet='https://www.littelfuse.com/assetdocs/tvs-diodes-smbj-series-datasheet?assetguid=ba555e99-a12d-4f72-a0b6-86b06c67171e'),
    'r_10k_p1': s('RT0603BRD0710KL', 'YAGEO', DIGI, 'YAG1236CT-ND', 0.10, 1,
                  DK + 'yageo/RT0603BRD0710KL/1072198',
                  '10 kOhm 0.1 % thin film 0603, 25 ppm/C, 1/10 W (R7). DigiKey page read: 269,413 in stock; $0.10 at 1, $0.07 at 10, '
                  '$0.058 at 100, $0.05096 at 500.'),
    'r_2k7_p1': s('RT0603BRD072K7L', 'YAGEO', DIGI, 'YAG1623CT-ND', 0.10, 1,
                  DK + 'yageo/RT0603BRD072K7L/1072440',
                  '2.7 kOhm 0.1 % thin film 0603, 25 ppm/C, 1/10 W (R15); 3,893 in stock. $0.07 at 10, $0.058 at 100.'),
    # ---- capacitors
    'c_100n': lc('CC0603KRX7R9BB104', 'YAGEO', 'C14663', 0.0141, 50, '100 nF 50 V X7R +/-10 % 0603; 4,600 in stock.'),
    'c_22n': lc('CL10B223KB8NNNC', 'Samsung Electro-Mechanics', 'C21122', 0.0084, 50, '22 nF 50 V X7R +/-10 % 0603; in stock.'),
    'c_10n': lc('CL10B103KB8NNNC', 'Samsung Electro-Mechanics', 'C1589', 0.0097, 50, '10 nF 50 V X7R +/-10 % 0603; in stock.'),
    'c_470p': lc('CL10C471JB8NNNC', 'Samsung Electro-Mechanics', 'C27694', 0.009, 100, '470 pF 50 V C0G +/-5 % 0603; in stock.'),
    'c_1u25': lc('CL10A105KB8NNNC', 'Samsung Electro-Mechanics', 'C15849', 0.0166, 50,
                 '1 uF X5R +/-10 % 0603; the page shows 50 V (more than the 25 V needed). Note the page title read CL10A105KB8NNNC.'),
    'c_10u50': lc('GRM32ER71H106KA12L', 'muRata', 'C77102', 0.3324, 5,
                  '10 uF 50 V X7R +/-10 % 1210 (C2, C3). OUT OF STOCK at LCSC on retrieval; a search snippet listed other 1210 10 uF 50 V '
                  'parts C116808, C172721. Murata part is also on DigiKey/Mouser.'),
    'c_47u16': lc('CL32A476KOJNNWE', 'Samsung Electro-Mechanics', 'C730498', 0.3663, 1,
                  '47 uF 16 V X5R +/-10 % 1210 (C8, C9). Only 2 in stock at LCSC on retrieval; Samsung CL32A476KOJNNNE and '
                  'CL32A476MOJNNNE are the same value on DigiKey/Mouser. X5R loses capacitance with DC bias, see calc/.'),
    'c_100u35': s('EEU-FR1V101', 'Panasonic', DIGI, 'P124225-ND', 0.71, 1, DK + 'panasonic-industry/EEU-FR1V101/9921024',
                  '100 uF 35 V radial electrolytic, 8 mm dia, 3.5 mm pitch, 105 C 6000 h; impedance 56 mOhm; ripple 950 mA at 100 kHz; '
                  '1,829 in stock. $0.443 at 10.'),
    'c_1000u16': s('EEU-FR1C102B', 'Panasonic', DIGI, 'P15331CT-ND', 1.13, 1, DK + 'panasonic-electronic-components/EEU-FR1C102B/2504095',
                   '1000 uF 16 V low-ESR radial electrolytic, 10 mm dia, 5 mm pitch, 17.5 mm tall; impedance 28 mOhm; ripple 1.79 A at 100 kHz '
                   '(1.343 A at 120 Hz). DigiKey stock 0, 500 expected 22-Jan-2027; EEU-FR1C102 (same size, DigiKey 2433532) '
                   'had 4,955 at Mouser per a search snippet. Price at 10 $0.721.'),
    # ---- semiconductors and power
    'barrel': s('PJ-102AH', 'Same Sky (CUI Devices)', DIGI, 'CP-102AH-ND', 0.77, 1,
                'https://www.digikey.com/product-detail/en/PJ-102AH/CP-102AH-ND/408448',
                'DC jack right angle, 24 V 5 A; centre pin 2.0 mm ID for a 5.5 mm OD plug (mates a 2.1 mm plug); 62,706 in stock. $0.65 at 10.',
                datasheet='https://www.mouser.com/datasheet/2/670/pj-102ah-1312852.pdf'),
    'screw2': s('1715721', 'Phoenix Contact', DIGI, '277-1263-ND', 1.16, 1, DK + 'phoenix-contact/1715721/260631',
                'MKDS 1,5/ 2-5,08, 2 position 5.08 mm, 300 V 15 A; 675 in stock. $0.955 at 10.'),
    'screw3': s('1715734', 'Phoenix Contact', DIGI, '277-1264-ND', 1.71, 1, DK + 'phoenix-contact/1715734/260632',
                'MKDS 1,5/ 3-5,08, 3 position 5.08 mm, 300 V 15 A; 4,556 in stock. $1.403 at 10.'),
    'ptc': lc('SMD1812P260TF/16', 'RUILON', 'C20814', 0.1498, 5,
              '1812 resettable fuse: hold 2.6 A, trip 5 A, V max 16 V, resistance 10 mOhm (50 mOhm max after trip); 1,310 in stock. '
              'V max 16 V meets the 16 V requirement but not the 24 V preference; a 24 V part was not found on LCSC in one search.'),
    'pfet': lc('AO4407A', 'MSKSEMI', 'C7379957', 0.0618, 5,
               'P-channel 30 V, 12 A, 9 mOhm at 10 V, SOP-8, a second-source part marked AO4407A. OUT OF STOCK at LCSC on retrieval. '
               'Genuine Alpha and Omega AO4407A (30 V, -12 A, 13 mOhm max) is on DigiKey/Mouser; search snippets also listed LCSC '
               'C5155211 (JSMSEMI) and C6430946 (GOODWORK).', datasheet='https://aosmd.com/products/mosfets/p-channel-mosfets-8v-60v/ao4407a'),
    'zener': lc('BZT52C15', 'JSCJ', 'C2104', 0.0202, 50, '15 V (13.8 to 15.6 V) 500 mW zener SOD-123; 28,150 in stock.'),
    'tvs': lc('SMBJ16A-M3/52', 'VISHAY', 'C1979375', 0.1836, 1,
              'Unidirectional TVS, stand-off 16 V, breakdown 19.7 V, clamp 26 V at 23.1 A, 600 W 10/1000 us, DO-214AA (SMB). '
              'OUT OF STOCK at LCSC on retrieval; Littelfuse/Taiwan Semi/MCC SMBJ16A are equivalent on DigiKey/Farnell.'),
    'buck': s('TPS54560BDDAR', 'Texas Instruments', DIGI, '296-TPS54560BDDARCT-ND', 5.80, 1, DK + 'texas-instruments/TPS54560BDDAR/10820404',
              '60 V 5 A buck, HSOIC-8 PowerPAD, active, 9,113 in stock. $4.44 at 10, $3.7247 at 100. TI product page says a newer '
              'version exists (LM70660, LM76005). Not stocked at LCSC (only TPS54560DDAR C31966, a different variant).',
              datasheet='https://www.ti.com/product/TPS54560B'),
    'schottky': lc('B540C-13-F', 'DIODES', 'C72264', 0.2332, 5, '40 V 5 A Schottky, Vf 550 mV at 5 A, SMC; 44,350 in stock.'),
    'inductor': s('SRP1245A-100M', 'Bourns', DIGI, 'SRP1245A-100MCT-ND', 1.47, 1, 'https://www.digikey.com/en/products/result?keywords=SRP1245A-100M',
                  '10 uH +/-20 % shielded. DigiKey page read: Isat 16 A, DCR 25.5 mOhm max, current rating 9 A (not labelled Irms), '
                  '692 in stock, lead time 21 weeks; $1.47 at 1, $1.212 at 10, $0.9969 at 100, reel $0.71585 at 5,000. Isat meets the '
                  '>= 7.5 A requirement by 2x. Isat as listed by DigiKey; the Bourns datasheet itself was not opened.',
                  datasheet='https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/18/SRP_Series_Bltn.pdf'),
    'shunt': lc('PE2512FKE7W0R1L', 'YAGEO', 'C165698', 0.1933, 5,
                '0.1 Ohm 1 % 2 W 2512 metal film, 50 ppm/C. OUT OF STOCK at LCSC on retrieval; the same part is on DigiKey/Mouser.'),
    'ina219': lc('INA219AIDR', 'Texas Instruments', 'C138706', 0.9571, 1, 'Current monitor SOIC-8; 7,970 in stock. $0.7634 at 10.',
                 datasheet='https://www.ti.com/lit/ds/symlink/ina219.pdf'),
    'ldo5': s('MCP1703AT-5002E/DB', 'Microchip', DIGI, 'MCP1703AT-5002E/DBCT-ND', 0.84, 1,
              DK + 'microchip-technology/MCP1703AT-5002E-DB/3131481',
              '5.0 V 250 mA LDO SOT-223, 16 V max input (2.7 to 16 V), dropout 0.65 V max at 250 mA; 8,542 in stock; $0.704 at 25. '
              'Microchip notice of 2026-06-09 covers a new fab for this family. Input is V_BUCK 6.58 V, 1.1 V of dropout headroom exists.',
              datasheet='https://ww1.microchip.com/downloads/en/DeviceDoc/20005122B.pdf'),
    'd_5v': s('BAT60AE6327HTSA1', 'Infineon', DIGI, 'BAT60AE6327HTSA1CT-ND', 0.64, 1,
              'https://www.digikey.com/en/products/result?keywords=BAT60AE6327HTSA1',
              'BAT60A Schottky SOD-323, 10 V, 3 A. Infineon datasheet (2007-04-19) read: Vf at 100 mA is 0.15 min, 0.20 typ, 0.23 V max '
              '(10 mA: 0.10/0.12/0.15 V; 1 A: 0.22/0.30/0.37 V), pulsed, 25 C, so the <= 0.25 V requirement is met by 0.02 V on the max. '
              'IR at 8 V: 0.6 mA typ, 2.6 mA max (5 V: 0.3 mA typ, 1 mA max), large for a Schottky, check against the 5 V node load. '
              'DigiKey page read: $0.64 at 1, $0.393 at 10, $0.2503 at 100; stock not shown, lead time 39 weeks, so check availability. '
              'The LCSC sibling BAT60B is C91059.',
              datasheet='https://static.chipdip.ru/lib/378/DOC012378990.pdf'),
    'ahct': lc('SN74AHCT1G125DBVR', 'Texas Instruments', 'C7484', 0.1009, 5, 'Single buffer SOT-23-5, TTL-level inputs; 27,020 in stock.',
               datasheet='https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf'),
    'esd': lc('PESD5V0S1BA,115', 'Nexperia', 'C19224', 0.0861, 5, 'Bidirectional ESD diode SOD-323, 5 V stand-off, 14 V clamp; 44,990 in stock.',
              datasheet='https://www.nexperia.com/product/PESD5V0S1BA'),
    'led': lc('TJ-S2012SW8TGLC2G-A5', 'TOGIALED', 'C192319', 0.0337, 20, 'Emerald green LED 0805, 520 nm (525 nm peak); 56,540 in stock.'),
    # ---- connectors and mechanical
    'devkitc': s('ESP32-DEVKITC-32E', 'Espressif', DIGI, '1965-ESP32-DEVKITC-32E-ND', 10.00, 1,
                 DK + 'espressif-systems/ESP32-DEVKITC-32E/12091810',
                 'ESP32-WROOM-32E 4 MB board. DigiKey stock 0 (252 expected 11-Jun-2027); Mouser also 0 per a search snippet. The two 1x19 '
                 '2.54 mm female sockets are bought with it and priced in socket19. Check Mouser (356-ESP32-DEVKITC32E, $10.00) and Amazon for stock.',
                 datasheet='https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html'),
    'socket19': s('HDR-29-G', 'ProtoSupplies', 'ProtoSupplies', 'HDR-29-G', 0.80, 1, 'https://protosupplies.com/product/header-female-1x19/',
                  '2-pack of 1x19 female 2.54 mm headers: exactly the two sockets for the DevKitC; 7 in stock. One pack per board.'),
    'hdr3': s('Break-away 0.1 in 36-pin male header (10-pack)', 'Adafruit', 'Adafruit', '392', 0.495, 10, 'https://www.adafruit.com/product/392',
              '2.54 mm gold male header, 36-pin strips, $4.95 per 10 so $0.495 per strip; one strip is cut for each header. Adafruit page '
              'showed OUT OF STOCK; any 2.54 mm break-away male header (DigiKey, Pololu) is equivalent.'),
    'hdr8': s('Break-away 0.1 in 36-pin male header (10-pack)', 'Adafruit', 'Adafruit', '392', 0.495, 10, 'https://www.adafruit.com/product/392',
              'Same strip as hdr3, cut to 8 pins. Out of stock at Adafruit on retrieval.'),
    'xh4': lc('B4B-XH-A(LF)(SN)', 'JST', 'C144395', 0.0599, 10, '4-pin 2.5 mm top-entry header; 157,130 in stock. Mates with XHP-4.'),
    'tact': s('Tactile Button switch 6 mm (20-pack)', 'Adafruit', 'Adafruit', '367', 0.125, 20, 'https://www.adafruit.com/product/367',
              '6.0 x 6.0 x 5.0 mm through-hole tactile switch; $2.50 per 20 so $0.125 each; in stock. Pin count not on the page (the '
              'common 4-pin 6 mm footprint SW_PUSH_6mm is expected).'),
    'tp': s('5000', 'Keystone Electronics', DIGI, '36-5000-ND', 0.35, 1, DK + 'keystone-electronics/5000/255326',
            'Miniature PC test point, red, 1.02 mm hole; 740,195 in stock. $0.263 at 10, $0.1994 at 100.'),
}

HARNESS = [
    dict(s('WPA-1774 (12 V 3 A wall adapter)', 'Pololu', 'Pololu', '1774', 21.95, 1, 'https://www.pololu.com/product/1774',
           'Regulated 12 VDC, up to 3 A (36 W), 100 to 240 VAC input, 1.5 m cord, centre-positive 5.5 x 2.1 mm plug, UL listed.'),
         item='12 V 3 A regulated DC adapter, 5.5 x 2.1 mm centre positive', qty=1),
    dict(s('Silicone Wire (1M Red, 1M Black) 20 AWG, SKU X8-1424-24', 'Pyrodrone', 'Pyrodrone', 'X8-1424-24', 5.99, 1,
           'https://pyrodrone.com/products/1ft-silicone-wire-choose-color-and-gauge',
           'Page read: one pack is 1 m red + 1 m black, 20 AWG $5.99, in stock. 1.2 m of each is needed, so buy 2 packs. Adafruit 6179 '
           '(20 AWG, 10 black wires, $5.50 per metre, 2 in stock) has no red.'),
         item='20 AWG silicone stranded wire, red + black, 1.2 m each (servo power pair)', qty=2),
    dict(s('Silicone Cover Stranded-Core Wire 2 m 26 AWG', 'Adafruit', 'Adafruit', '1877 (red), 1880 (green), 1882 (white), 1883 (orange), 1884 (gray)',
           0.95, 1, 'https://www.adafruit.com/product/1877',
           '26 AWG silicone, 1.4 to 1.5 mm OD, 123 ohm/km, -60 to 200 C; 2 m spool $0.95. Buy one spool in each of five colours '
           '(red page read; other colours priced from search snippets).'),
         item='26 AWG silicone stranded wire, five colours, 1.2 m each (signal conductors)', qty=5),
    dict(s('XHP-4 + SXH-001T-P0.6', 'JST', DIGI, '455-2267-ND (XHP-4), 455-1135TR-ND (SXH-001T-P0.6)', 0.29, 1,
           DK + 'jst-sales-america-inc/XHP-4/683353',
           '4-position XH housing, 2.5 mm, crimp. XHP-4 page read: 106,705 in stock, $0.10 at 1, $0.0555 at 100. Contacts SXH-001T-P0.6 '
           'take 22 to 28 AWG (the 26 AWG wire fits); the DigiKey page read is the reel only (8,000 at $0.02351, 1.9 M in stock) and no '
           'cut-tape page was read: $0.047 each is the highest of four contact listings on the search page, taken as the small-quantity '
           'price (0.10 + 4 x 0.047 = 0.29), so the total is an estimate.', tag='A'),
         item='JST XH 4-position housing XHP-4 with 4 crimp contacts SXH-001T-P0.6', qty=1),
    dict(s('SMP-04V-BC + SMR-04V-B', 'JST', DIGI, '455-3248-ND (SMP-04V-BC), 455-3247-ND (SMR-04V-B)', 0.34, 1,
           'https://www.digikey.com/en/products/result?keywords=SMP-04V-BC',
           'JST SM 4-pin wire-to-wire housing pair, 2.5 mm, 3 A. DigiKey pages read: SMP-04V-BC $0.16 at 1 (32,925 in stock), SMR-04V-B '
           '$0.18 at 1 (14,813 in stock, 16 week lead time); $0.34 is the housing pair only. Crimp contacts for both housings (8 in all) '
           'were not priced and the contact part numbers were not confirmed, so the line stays assumed.', tag='A'),
         item='4-position latching wire-to-wire pair (wrist end), plug and receptacle', qty=1),
    dict(s('Servo Extension Cable 30 cm', 'Adafruit', 'Adafruit', '972', 1.95, 1, 'https://www.adafruit.com/product/972',
           '3-pin shrouded male plug (mates the servo lead) and 3-pin female at 30 cm; red/black/white; in stock. $1.76 at 10.'),
         item='3-pin 0.1 in servo extension lead (male end mates the servo plug)', qty=1),
    dict(s('EEU-FR1C471', 'Panasonic', DIGI, 'P14394-ND', 0.71, 1, DK + 'panasonic-industry/EEU-FR1C471/2433528',
           '470 uF 16 V low-ESR radial electrolytic, 8 mm dia, 3.5 mm pitch; impedance 56 mOhm; ripple 950 mA at 100 kHz; 1,040 in stock.'),
         item='470 uF 16 V low-ESR radial electrolytic (forearm-end capacitor)', qty=1),
    dict(s('65801-002LF / COM-14194', 'Amphenol FCI', 'SparkFun', 'COM-14194', 2.95, 1,
           'https://www.sparkfun.com/amphenol-fci-clincher-connector-2-position-female.html',
           '2-position 0.1 in female Clincher connector for a flex sensor tail; in stock. $2.66 at 100.'),
         item='Amphenol Clincher 2-position female for the FSR 402 tail', qty=1),
    dict(s('D2F-01L', 'Omron (Aratas)', DIGI, 'SW154-ND', 1.44, 1, DK + 'aratas-formerly-omron-components/D2F-01L/83264',
           'Subminiature snap-action SPDT, 0.1 A 30 V, hinge lever. DigiKey page: operating force 80 gf (about 0.78 N); mass not listed on '
           'the page and not found elsewhere. $1.188 at 10; 81,936 in stock. Suffix variants cost more.'),
         item='Subminiature lever microswitch for the jaw-open limit', qty=1),
    dict(s('Versaflex 1/4 inch expandable braided sleeve', 'TE Connectivity Raychem', DIGI, '484-VERSAFLEX-1/4-0-SP-DS-ND', 2.01, 1,
           DK + 'te-connectivity-raychem-cable-protection/VERSAFLEX-1-4-0-SP/24399324',
           'Digi-Spool sold per metre; ID 6.00 mm relaxed, 9.52 mm expanded. Page read: $2.01 at 1 m, $1.656 at 5 m. Buy 2 m for a 1.5 m run. '
           'DigiKey stock is 0 m (estimated 12-Apr-2027, lead time 26 weeks): find another source or a shorter-lead sleeve before ordering.'),
         item='Braided sleeve 1.5 m', qty=2),
    dict(s('Black Nylon Machine Screw and Stand-off Set M3', 'Adafruit', 'Adafruit', '4685', 16.95, 1, 'https://www.adafruit.com/product/4685',
           'Page read: $16.95 (1 to 9), 96 in stock; 420 pieces including 20 x 10 mm F-F standoffs, 40 x M3x10 screws and 120 nuts. A kit '
           'far larger than the 4 standoffs needed, so a loose M3 standoff pack from any distributor is equivalent and cheaper if found.'),
         item='M3 standoffs, 4 off (with screws)', qty=1),
    dict(s('USB A to Micro-B cable 1 m', 'Adafruit', 'Adafruit', '592', 2.95, 1, 'https://www.adafruit.com/product/592',
           'USB 2.0 A to micro-B, 3 ft; in stock. $2.66 at 10.'),
         item='USB cable for the DevKitC (micro-B)', qty=1),
]

# JLCPCB two-layer FR-4 capabilities, read from the capabilities page on retrieval.
_CAP = 'https://jlcpcb.com/capabilities/pcb-capabilities'


def _f(value, tag='S', url=_CAP, note=''):
    return {'value': value, 'url': url, 'retrieved': D, 'tag': tag, 'note': note}


FAB = {
    'fabricator': _f('JLCPCB', note='Two-layer capabilities, 1 oz copper'),
    'min_track_mm': _f(0.10, note='4 mil'),
    'min_space_mm': _f(0.10, note='4 mil'),
    'min_drill_mm': _f(0.15, note='0.1 mm drill only for boards up to 1 mm thick, ENIG or OSP, at extra cost'),
    'min_via_hole_mm': _f(0.15),
    'min_via_pad_mm': _f(0.25, note='page recommends a pad at least 0.1 mm larger than the hole, 0.15 mm preferred'),
    'min_annular_ring_mm': _f(0.18, note='absolute minimum; 0.25 mm or more recommended for PTH, 1 oz'),
    'edge_copper_clearance_mm': _f(0.2, note='routed outline'),
    'min_silk_width_mm': _f(0.15, note='minimum text height 1.0 mm'),
    'thickness_std_mm': _f([0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0]),
    'copper_oz': _f(1, note='outer layers 1 oz standard; 2, 2.5, 3.5 and 4.5 oz also offered'),
    'max_size_cheapest_class_mm': _f([100, 100], tag='A', url='https://hwdocs.hackclub.dev/user-contrib-guides/jlc-cost-optimizing/',
                                     note='Hack Club guide says the lowest price class holds at or under 100 x 100 mm; the JLCPCB page '
                                          'does not name a price class (it gives 670 x 600 mm as the 2-layer maximum). Check the PCB outline '
                                          'against 100 x 100 mm.'),
    'price_5_boards_usd': _f(2.0, url='https://jlcpcb.com/',
                             note='JLCPCB home page read: FR-4 PCBs "From $2.00 / 5 pcs", 1 to 32 layers; the page names no size limit for '
                                  'that price (the instant quote tool decides) and shipping is extra (forum posts: $8 to $17).'),
}

# Short sourced findings. Tag A where the claim comes from search results or retailer pages rather than a primary page read.
EVIDENCE = {
    'servo_signal_level': {
        'finding': 'No manufacturer datasheet found gives a signal-pin threshold for the DS3218MG; listings give only 4.8 to 6.8 V power and '
                   '500 to 2500 us pulses. A general article puts typical servo input thresholds at 1.8 to 2.5 V (so 3.3 V is usually read, '
                   'with about 1.5 V margin) but says some servos need about 3.0 V or full 5 V and ignore 3.3 V pulses, and a Pololu forum '
                   'thread says not all servos accept 3.3 V. So reliability at 3.3 V is unproven for this servo; the 5 V buffer is the safe path.',
        'url': 'https://zbotic.in/servo-signal-wire-pwm-timing-signal-voltage-level-shifting/',
        'retrieved': D, 'tag': 'A'},
    'servo_lead': {
        'finding': 'Servo Database lists the DS3218 MG lead as 300 mm with a JR-style connector, and AIFitLab gives 300 +/- 5 mm. '
                   'No page gave the wire gauge.',
        'url': 'https://servodatabase.com/servo/dsservo/ds3218-mg', 'retrieved': D, 'tag': 'A'},
    'devkitc_power': {
        'finding': 'Espressif lists three mutually exclusive ways to power the board (micro-USB port, the default; 5V and GND header pins; '
                   '3V3 and GND header pins) and warns to use only one source at a time, since more than one can damage the board or the supply. '
                   'The board has an on-board diode from USB only, so the D7 OR-ing into the 5V pin has USB and the board rail both live.',
        'url': 'https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html',
        'retrieved': D, 'tag': 'S'},
    'devkitc_dimensions': {
        'finding': 'The Espressif guide text gives no header row spacing, pitch or outline numbers (only a dimension drawing and a DXF link, '
                   'plus 19 pins on each of J2 and J3); I could not read the drawing, so 25.4 mm row pitch, 54.4 x 27.9 mm are unverified. '
                   'Measure a physical board before ordering PCBs.',
        'url': 'https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html',
        'retrieved': D, 'tag': 'A'},
    'fsr_tail': {
        'finding': 'The FSR 400 data sheet and brochure give up to 10 million actuations (tested at 1 kg, 4 Hz for a related UX part). '
                   'Soldering guidance and tail minimum bend radius are in the Interlink integration guide EIG-10000, which I could not read '
                   '(the PDF fetch returned binary); the data sheet also mentions female-connector and short-tail versions.',
        'url': 'https://interlinkelectronics.com/fsr-ux-400', 'retrieved': D, 'tag': 'A'},
    'flex_wire': {
        'finding': 'Cable makers most often give about 10x outer diameter as the minimum dynamic bend radius (5x to 15x across sources; Parker '
                   'Trilogy: 5x absolute, 10x preferred) with finely stranded conductors; none gives a cycle count tied to a multiple, so the '
                   'cable supplier test data should decide. A 1.4 to 1.5 mm OD 26 AWG silicone lead gives a 10x radius of about 15 mm.',
        'url': 'https://www.telewiretech.com/blogs/technical-resources/the-ultimate-guide-to-calculating-cable-bend-radius-static-vs-dynamic-limitations',
        'retrieved': D, 'tag': 'A'},
    'jlc_assembly': {
        'finding': 'JLCPCB help pages did not load. Third-party guides say assembly needs a BOM with a column headed "LCSC Part #", a CPL '
                   'placement file (designator, mid X, mid Y, rotation, layer) and Gerbers; Basic and preferred extended parts carry no '
                   'feeder fee and other extended parts $3 each. Whether economic assembly covers a single-side 2-layer board was not '
                   'confirmed from JLCPCB.',
        'url': 'https://zbotic.in/bom-management-in-kicad-and-easyeda-export-for-jlcpcb/', 'retrieved': D, 'tag': 'A'},
}


# Calculation input provenance. `quote` is the short printed value (in the
# document's units), not a conversion of constants.C. A record marked A keeps
# the calculation's value as an assumption until evidence for that *part* is
# available. Page numbers are the numbers printed on the PDFs.
def _calc_source(mpn, maker, url, revision, page, table, quote, tag='S', reason=''):
    return dict(mpn=mpn, manufacturer=maker, datasheet_url=url,
                datasheet_revision=revision, page=page, table=table,
                quote=quote, tag=tag, reason=reason)


CALC_CONSTANTS = {}


def _calc_group(mpn, maker, url, revision, rows):
    for key, page, table, quote in rows:
        CALC_CONSTANTS[key] = _calc_source(mpn, maker, url, revision, page, table, quote)


_calc_group('TPS54560BDDAR', 'Texas Instruments',
            'https://www.ti.com/lit/ds/symlink/tps54560b.pdf', 'SLVSF00, January 2019', [
    ('tps_vin_min', 5, '6.5 Electrical Characteristics', '4.5 V minimum operating input'),
    ('tps_vin_max', 5, '6.5 Electrical Characteristics', '60 V maximum operating input'),
    ('tps_vref', 5, '6.5 Electrical Characteristics', '0.8 V typical reference'),
    ('tps_vref_min', 5, '6.5 Electrical Characteristics', '0.792 V minimum reference'),
    ('tps_vref_max', 5, '6.5 Electrical Characteristics', '0.808 V maximum reference'),
    ('tps_ea_gm', 6, '6.5 Electrical Characteristics', '350 uA/V typical transconductance'),
    ('tps_ea_gain', 5, '6.5 Electrical Characteristics', '10,000 V/V dc gain'),
    ('tps_ea_imax', 5, '6.5 Electrical Characteristics', '+/-30 uA source/sink'),
    ('tps_ps_gm', 5, '6.5 Electrical Characteristics', '17 A/V COMP to SW'),
    ('tps_ilim_min', 5, '6.5 Electrical Characteristics', '6.3 A minimum current limit'),
    ('tps_ilim_typ', 5, '6.5 Electrical Characteristics', '7.9 A typical current limit'),
    ('tps_en_thresh', 5, '6.5 Electrical Characteristics', '1.2 V typical enable threshold'),
    ('tps_en_thresh_min', 5, '6.5 Electrical Characteristics', '1.1 V minimum enable threshold'),
    ('tps_en_thresh_max', 5, '6.5 Electrical Characteristics', '1.3 V maximum enable threshold'),
    ('tps_en_i1', 5, '6.5 Electrical Characteristics', '-1.2 uA typical below threshold'),
    ('tps_en_ihys', 5, '6.5 Electrical Characteristics', '-3.4 uA typical hysteresis current'),
    ('tps_rt_coeff', 7, 'Figure 6', 'fsw (kHz) = 92471 x RT (kOhm)^-0.991'),
    ('tps_rt_exp', 7, 'Figure 6', 'exponent -0.991'),
    ('tps_uvlo_rise', 5, '6.5 Electrical Characteristics', '4.3 V typical rising UVLO'),
    ('tps_uvlo_hyst', 5, '6.5 Electrical Characteristics', '325 mV UVLO hysteresis'),
    ('tps_ton_min', 14, '7.3.9 Switching Frequency', '135 ns typical minimum controllable on-time'),
    ('tps_rds_typ', 5, '6.5 Electrical Characteristics', '92 mOhm typical on-resistance'),
    ('tps_rds_max', 5, '6.5 Electrical Characteristics', '190 mOhm maximum on-resistance'),
    ('tps_rth_ja', 4, '6.4 Thermal Information', '42 degC/W junction-to-ambient'),
    ('tps_iq', 5, '6.5 Electrical Characteristics', '146 uA typical nonswitching current'),
    ('tps_en_i1_min', 5, '6.5 Electrical Characteristics', '-0.58 uA below threshold'),
    ('tps_en_i1_max', 5, '6.5 Electrical Characteristics', '-1.8 uA below threshold'),
    ('tps_en_ihys_min', 5, '6.5 Electrical Characteristics', '-2.2 uA hysteresis'),
    ('tps_en_ihys_max', 5, '6.5 Electrical Characteristics', '-4.5 uA hysteresis'),
])

_calc_group('INA219AIDR', 'Texas Instruments',
            'https://www.ti.com/lit/ds/symlink/ina219.pdf', 'SBOS448G, December 2015', [
    ('ina_vos_pga1', 5, '7.5 Electrical Characteristics', '+/-100 uV maximum, PGA /1'),
    ('ina_vos_pga2', 5, '7.5 Electrical Characteristics', '+/-125 uV maximum, PGA /2'),
    ('ina_vos_pga4', 5, '7.5 Electrical Characteristics', '+/-150 uV maximum, PGA /4'),
    ('ina_vos_pga8', 5, '7.5 Electrical Characteristics', '+/-200 uV maximum, PGA /8, A grade'),
    ('ina_gain_err_typ', 5, '7.5 Electrical Characteristics', '+/-40 m% typical current-sense gain error'),
    ('ina_meas_err_max', 5, '7.5 Electrical Characteristics', '+/-0.5% maximum at 25 degC, A grade'),
    ('ina_gain_tc', 5, '7.5 Electrical Characteristics', '1 m%/degC gain drift'),
    ('ina_conv_12bit', 5, '7.5 Electrical Characteristics', '532 us typical 12-bit conversion'),
    ('ina_conv_12bit_max', 5, '7.5 Electrical Characteristics', '586 us maximum 12-bit conversion'),
    ('ina_default_cfg', 18, 'Table 2', '399F hex configuration reset value'),
    ('ina_fs_pga8', 19, 'Table 4', '+/-320 mV PGA /8 range'),
    ('ina_lsb', 5, '7.5 Electrical Characteristics', '10 uV shunt-voltage LSB'),
    ('ina_ibias', 5, '7.5 Electrical Characteristics', '20 uA typical active input bias'),
    ('ina_filter_note', 11, 'Figure 14 and 8.4.1', '10 Ohm series; 0.1 to 1 uF ceramic'),
    ('ina_input_impedance_ohm', 5, '7.5 Electrical Characteristics', '320 kOhm IN- input impedance'),
    ('ina_average_codes_samples', 20, 'Table 5', 'codes 8..F: 1, 2, 4, 8, 16, 32, 64, 128 samples'),
    ('ina_sadc_mask', 20, '8.6.2 Configuration Register', 'SADC uses four bits, bits 3..6'),
    ('ina_sadc_shift', 20, '8.6.2 Configuration Register', 'SADC starts at bit 3'),
])

_calc_group('MCP1703AT-5002E/DB', 'Microchip',
            'https://ww1.microchip.com/downloads/en/DeviceDoc/20005122B.pdf', 'DS20005122B, 2013', [
    ('mcp_vin_max', 3, 'DC Characteristics', '16.0 V maximum operating input'),
    ('mcp_dropout_typ', 4, 'DC Characteristics', '330 mV typical at 250 mA, VR = 5.0 V'),
    ('mcp_dropout_max', 4, 'DC Characteristics', '650 mV maximum at 250 mA, VR = 5.0 V'),
    ('mcp_vout_tol', 3, 'DC Characteristics', 'VR +/-3.0% standard output regulation'),
    ('mcp_isc', 3, 'DC Characteristics', '400 mA typical short-circuit current at stated test condition'),
    ('mcp_iout_max', 3, 'DC Characteristics', '250 mA maximum output current for VR >= 2.5 V'),
])

_calc_group('ESP32-D0WD', 'Espressif Systems',
            'https://documentation.espressif.com/esp32_datasheet_en.pdf', 'ESP32 Series v5.3', [
    ('esp_vdd_min', 51, 'Table 5-2', '2.3 V minimum for chip without in-package flash'),
    ('esp_vdd_min_flash', 51, 'Table 5-2 note 2', '3.0 V minimum for chip with in-package 3.3 V flash'),
    ('esp_vdd_max', 51, 'Table 5-2', '3.6 V maximum operating supply'),
    ('esp_i_active_nowifi', 52, 'Table 5-4', '30 to 68 mA CPU active, radio off'),
    ('esp_i_wifi_rx', 53, 'Table 5-5', '95 to 100 mA Wi-Fi receive'),
    ('esp_i_wifi_tx_peak', 53, 'Table 5-5', '240 mA typical, 802.11b 1 Mbps +19.5 dBm'),
    ('esp_adc_min_mv', 44, 'ADC Calibration Results', '150 mV lower end at attenuation 3'),
    ('esp_adc_max_mv', 44, 'ADC Calibration Results', '2450 mV upper end at attenuation 3'),
    ('esp_adc_err_mv', 44, 'ADC Calibration Results', '+/-60 mV total calibrated error at attenuation 3'),
    ('fsr_adc_min_mv', 44, 'ADC Calibration Results', '150 mV lower end at attenuation 3'),
    ('fsr_adc_max_mv', 44, 'ADC Calibration Results', '2450 mV upper end at attenuation 3'),
])

_calc_group('MF-MSMF260/16X', 'Bourns',
            'https://www.bourns.com/docs/Product-Datasheets/mfmsmf.pdf', 'MF-MSMF series, current web PDF', [
    ('f1_hold', 2, 'Electrical Characteristics', '2.60 A hold at 23 degC'),
    ('f1_trip', 2, 'Electrical Characteristics', '5.00 A trip at 23 degC'),
    ('f1_rmin', 2, 'Electrical Characteristics', '0.015 Ohm Rmin'),
    ('f1_r1max', 2, 'Electrical Characteristics', '0.050 Ohm R1max'),
    ('f1_vmax', 2, 'Electrical Characteristics', '16 V maximum'),
    ('f1_ttrip', 2, 'Electrical Characteristics', '5.0 s maximum at 8.0 A'),
])

_calc_group('AO4407A', 'Alpha & Omega Semiconductor',
            'https://www.aosmd.com/res/data_sheets/AO4407A.pdf', 'Rev. 11.1, March 2024', [
    ('q1_rds', 1, 'Product Summary', '13 mOhm maximum at VGS = -10 V'),
    ('q1_rds_6v', 1, 'Product Summary', '17 mOhm maximum at VGS = -6 V'),
])

# These are reference or seller pages, rather than a selected manufacturer's
# datasheet. Retain the quoted observation but do not present it as part proof.
for _key, _mpn, _maker, _url, _where, _quote, _why in [
    ('servo_vmin', 'DS3218MG', 'unconfirmed', 'https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories', 'vendor product page', '4.8 V operating low end', 'No manufacturer datasheet identified.'),
    ('servo_vmax', 'DS3218MG', 'unconfirmed', 'https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories', 'vendor product page', '6.8 V operating high end', 'No manufacturer datasheet identified.'),
    ('harness_adapter_cord_mm', '1774', 'Generic / Pololu listing', 'https://www.pololu.com/product/1774', 'Details for item #1774', '1.5 m (5 ft) DC power cord', 'Seller listing; no manufacturer datasheet.'),
    ('harness_usb_cable_mm', '592', 'Adafruit', 'https://www.adafruit.com/product/592', 'Description', 'Approximately 3 feet / 1 meter long', 'Seller states approximate length; 914 mm is a conversion, not a specified tolerance.'),
    ('harness_od_26awg_mm', '1877', 'Adafruit', 'https://www.adafruit.com/product/1877', 'product description', '', 'No manufacturer datasheet specifying 1.5 mm OD was verified.'),
]:
    CALC_CONSTANTS[_key] = _calc_source(_mpn, _maker, _url, 'undated web page', _where, '', _quote,
                                        tag='A', reason=_why)

for _key, _gauge in [('awg20_ohm_m', 20), ('awg22_ohm_m', 22),
                     ('awg24_ohm_m', 24), ('awg26_ohm_m', 26),
                     ('awg28_ohm_m', 28)]:
    CALC_CONSTANTS[_key] = _calc_source('unselected AWG %s conductor' % _gauge,
        'unselected', 'https://en.wikipedia.org/wiki/American_wire_gauge',
        'undated reference page', 'web page', 'wire resistance table', 'AWG %s reference resistance' % _gauge,
        tag='A', reason='A general copper-wire reference is not the selected stranded harness wire datasheet.')

for _key, _quote in [('ipc_k_ext', 'k = 0.048 external'),
                     ('ipc_b', 'b = 0.44'), ('ipc_c', 'c = 0.725'),
                     ('ipc_mil_per_oz', '1.378 mil/oz')]:
    CALC_CONSTANTS[_key] = _calc_source('IPC-2221 curve fit', 'AdvancedPCB',
        'https://www.advancedpcb.com/en-us/tools/trace-width-calculator/',
        'undated calculator', 'web page', 'Notes / external-layer formula', _quote,
        tag='A', reason='Secondary calculator, not the IPC standard or a part datasheet.')

CALC_CONSTANTS['mcp_rth_sot223'] = _calc_source('MCP1703AT-5002E/DB', 'Microchip',
    'https://ww1.microchip.com/downloads/en/DeviceDoc/20005122B.pdf',
    'DS20005122B, 2013', 'page 15', '6.4 Thermal Considerations',
    '62.9 degC/W SOT-223', tag='A',
    reason='Stored 62.0 K/W differs from the printed 62.9 degC/W; value retained pending design review.')
CALC_CONSTANTS['power_3v3_minus_3pct_mv'] = _calc_source('MCP1703AT-5002E/DB', 'Microchip',
    'https://ww1.microchip.com/downloads/en/DeviceDoc/20005122B.pdf',
    'DS20005122B, 2013', 'page 3', 'DC Characteristics',
    'VR +/-3.0%', tag='A',
    reason='3.3 V rail is on the DevKitC, not the 5.0 V MCP1703A; the PDF does not state 3201 mV.')

CALC_CONSTANTS['esp_vdd_min_flash']['tag'] = 'A'
CALC_CONSTANTS['esp_vdd_min_flash']['reason'] = (
    'The 3.0 V footnote applies to chips with in-package flash; the WROOM-32E module has external flash.')
for _key in ('f1_hold', 'f1_trip', 'f1_rmin', 'f1_r1max', 'f1_vmax', 'f1_ttrip'):
    CALC_CONSTANTS[_key]['tag'] = 'A'
    CALC_CONSTANTS[_key]['reason'] = (
        'Bourns data do not qualify the selected RUILON SMD1812P260TF/16; obtain its datasheet.')
for _key in ('q1_rds', 'q1_rds_6v'):
    CALC_CONSTANTS[_key]['tag'] = 'A'
    CALC_CONSTANTS[_key]['reason'] = (
        'AOS data do not qualify the selected MSKSEMI AO4407A second-source device.')
