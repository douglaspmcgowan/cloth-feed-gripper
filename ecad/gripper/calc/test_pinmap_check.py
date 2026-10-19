"""pinmap_check.py: parser, rules, and the repository's own pin map."""
import os

import _common as cm
import design
import pinmap_check as pm


def test_config_h_defines_parse_and_match_design():
    cfg = pm.parse_config()
    assert len(cfg) == len(design.GPIO_NETS) == 14
    assert cfg['PIN_FSR_ADC'] == 34 and cfg['PIN_SERVO_PWM'] == 18
    for gpio, (net, macro) in design.GPIO_NETS.items():
        assert cfg[macro] == gpio


def test_socket_pin_numbers_by_hand():
    # J2 is pins 1-19 (3V3, EN, IO36, IO39, IO34, ...): IO34 is the fifth pin; J3 pin 1 is socket pin 20 (GND)
    assert design.devkit_pin_number(34) == 5
    assert design.devkit_pin_number(32) == 7
    assert design.devkit_pin_number(18) == 28
    assert design.devkit_pin_number(23) == 21


def test_the_repository_pin_map_passes():
    r = pm.run()
    assert all(x['match'] for x in r['lines'])
    assert all(x['ok'] for x in r['socket'])
    assert all(x['ok'] for x in r['rules'])
    assert r['ok'] is True


def test_rules_reject_bad_pins(monkeypatch):
    bad = dict(design.GPIO_NETS)
    bad[12] = ('BTN_IN', 'PIN_BUTTON')           # GPIO 12 is a strapping pin
    del bad[25]
    monkeypatch.setattr(design, 'GPIO_NETS', bad)
    r = pm.run()
    row12 = [x for x in r['rules'] if x['gpio'] == 12][0]
    assert 'strapping' in row12['notes']
    assert not r['ok']                              # config.h says PIN_BUTTON is 25, not 12


def test_netlist_parser_and_matching(tmp_path):
    text = '(export (version "E") (nets (net (code "1") (name "/PWM_3V3") (node (ref "U5") (pin "28")) (node (ref "U4") (pin "2"))) (net (code "2") (name "GND") (node (ref "U5") (pin "1")))))'
    p = tmp_path / 'x.net'
    p.write_text(text, encoding='utf-8', newline='\n')
    pins = pm.netlist_pins(str(p))
    assert pins[('U5', '28')] == '/PWM_3V3' and pins[('U5', '1')] == 'GND'
    assert pm.net_matches('/PWM_3V3', 'PWM_3V3') and not pm.net_matches('GND', 'PWM_3V3')
    assert not pm.net_matches(None, 'X')
