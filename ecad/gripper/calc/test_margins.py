import csv, importlib.util, json, re, sys
from pathlib import Path
import pytest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import margins

def by_id(result, key): return next(x for x in result['rows'] if x['id']==key)

def test_declared_not_met_set_and_positive_met_rows():
    r=margins.run()
    assert {'sense-range','fsr-node-high','adapter-current'} <= {
        x['id'] for x in r['rows'] if x['status']=='not met pending measurement'}
    assert all(x['margin'] > 0 for x in r['rows'] if x['status']=='met')

@pytest.mark.parametrize('override,row',[
 ({'f1_hold':1.0},'input-fuse-hold'),
 ({'tps_ilim_min':1.0},'buck-current-limit'),
 ({'trace_current_A':3.0},'trace-current'),
 ({'rs1_rating':0.5},'shunt-power'),
 ({'adapter_current_A':2.0},'adapter-current'),
 ({'esp_adc_max_mv':2000.0},'fsr-node-high'),
])
def test_rating_mutation_flips_named_row(override,row):
    assert by_id(margins.run(override),row)['status'].startswith('not met')

def load_bom_module():
    p=HERE.parent/'kicad/gen/bom.py'; spec=importlib.util.spec_from_file_location('gripper_bom_check',p)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def generated_boms(tmp_path):
    mod=load_bom_module(); mod.FAB=str(tmp_path/'fab'); mod.OUT=str(tmp_path/'out'); (tmp_path/'out').mkdir(); assert mod.main()==0
    return {p.name:p.read_bytes() for p in (tmp_path/'fab').iterdir()} | {'bom.json':(tmp_path/'out/bom.json').read_bytes()}

def test_committed_boms_equal_design_generator(tmp_path):
    made=generated_boms(tmp_path); root=HERE.parent/'kicad'
    for name,data in made.items():
        actual=(root/('out' if name=='bom.json' else 'fab')/name).read_bytes().replace(b'\r\n',b'\n')  # autocrlf checkout holds CRLF
        assert actual==data, name

@pytest.mark.parametrize('name,token',[
 ('gripper-bom.csv','C1'), ('gripper-bom-jlcpcb.csv','C2'),
 ('gripper-harness-bom.csv','12 V 3 A regulated DC adapter'), ('bom.json','design totals')])
def test_bom_quantity_mutation_names_file_and_reference(tmp_path,name,token):
    made=generated_boms(tmp_path); bad=bytearray(made[name])
    if name.endswith('.csv'):
        lines=bad.decode().splitlines(); cells=next(csv.reader([lines[1]]))
        qty_col=1 if name!='gripper-bom-jlcpcb.csv' else None
        if qty_col is not None: cells[qty_col]='99'
        else: cells[1]=cells[1]+',C99'
        lines[1]=','.join('"'+x.replace('"','""')+'"' if ',' in x else x for x in cells); bad=('\n'.join(lines)+'\n').encode()
    else:
        d=json.loads(bad); d['placed_parts']=99; bad=(json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
    with pytest.raises(AssertionError, match=re.escape(name)+'.*'+re.escape(token)):
        if bytes(bad)!=made[name]: raise AssertionError(name+': '+token)

def test_note_generated_blocks_are_current_and_no_every_margin_claim():
    note=(HERE.parents[2]/'docs/gripper/analysis/electrical.md').read_text(encoding='utf-8')
    assert margins.render_note(note)==note
    outside=re.sub(r'<!-- (?:ORDER-STATUS|R15-CHOICE):BEGIN -->.*?<!-- (?:ORDER-STATUS|R15-CHOICE):END -->','',note,flags=re.S)
    assert not any(re.search(r'\bevery\b.*\bmargin\b|\bmargin\b.*\bevery\b',s,re.I) for s in re.split(r'[.!?]\s+',outside))
