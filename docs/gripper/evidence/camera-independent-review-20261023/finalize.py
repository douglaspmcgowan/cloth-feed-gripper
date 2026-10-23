"""Assemble the partial result from immutable captured evidence; never rerun a failed scenario."""
from pathlib import Path
import hashlib, json, subprocess, datetime

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
load=lambda p:json.loads((OUT/p).read_text(encoding='utf-8-sig'))
execution=load('execution.json')
independent=load('independent-results.json')
suite=load('browser/camera-assertions.json')
counts=load('browser/control-counts.json')
baseline=json.loads((ROOT/'docs/gripper/evidence/camera-resume-20261023/source2-red/control-counts.json').read_text())
framing=[]
for width in [390,768,1440]:
    for row in load(f'ind-framing-{width}.json'):
        b=row['bounds']
        framing.append({'width':width,'pose':row['pose'],'explode':b['explode'],'margins_px':b['margins'],'all_meshes':len(b['all_meshes']),'shown_meshes':len(b['visible_names']),'vertices':b['vertex_population'],'hidden_mesh_names':[m['name'] for m in b['all_meshes'] if not m['shown']],'depth':b['depth'],'evidence':f'ind-framing-{width}.json'})
camera=[r for r in suite['results'] if 'camera' in r.get('name','') or 'resize' in r.get('name','') or 'orbit' in r.get('name','')]
pngs=sorted(OUT.rglob('*.png'))
images=[]
for p in pngs:
    name=p.relative_to(OUT).as_posix()
    if 'finding-gap' in name: note='Read the selected fastener pair and 0.01 mm gap label; location inset distinguishes local detail from assembly context.'
    elif 'finding-overlap' in name: note='Read 736 mm3, green by-design overlap and the two fingers; label remains readable.'
    elif 'dependency-initial' in name: note='Loading the model and Reload are distinct from live geometry.'
    elif 'dependency-still' in name: note='Still-loading text offers reload or continuing in Parts.'
    elif 'dependency-terminal' in name: note='Terminal missing-library message is explicit and Reload remains visible.'
    elif 'fit-cold' in name or 'fit-warm' in name: note='Phone screenshot is dominated by introductory text; only top of canvas appears. This image alone cannot prove camera equivalence.'
    elif 'fit-late-host' in name: note='Rendered local pads inspection and green volume label are visible after host attachment.'
    elif 'ind-fit-selected' in name: note='7 degree jaw and 40 degree wrist roll controls, Copy link and selected pads explanation are readable; canvas is partly above viewport after controls scroll.'
    elif 'orbit' in name: note='New oblique bearing exposes separated fasteners and fingers; gripper remains within canvas. Cropped white arm context is retained.'
    elif 'exploded' in name: note='Separated fingers and fasteners remain framed at useful inspection scale; white arm context may be cropped.'
    else: note='Complete blue gripper and orange fingers are legible at useful assembled scale; upper white arm context is intentionally cropped.'
    images.append({'path':name,'native_dimensions_inspected':True,'reviewer':'gpt-6.1-sol','observation':note})
copied=load('copied-permalink.json')
encoded=copied['copied'].split('~c=')[1].split('~')[0]
encoded_camera=[float(x) for x in encoded.split(',')]
copy_deltas=[abs(a-b) for a,b in zip(copied['linked']['camera'],encoded_camera)]
source_commit=subprocess.check_output(['git','rev-parse','ed77773'],cwd=ROOT,text=True).strip()
original=subprocess.check_output(['git','show',source_commit+'^:cad/gripper/viewer.html'],cwd=ROOT)
candidate=(ROOT/'cad/gripper/viewer.html').read_bytes()
original_data=next(line for line in original.splitlines() if line.startswith(b'const D='))
candidate_data=next(line for line in candidate.splitlines() if line.startswith(b'const D='))
data_identity={'original_source_ref':source_commit+'^:cad/gripper/viewer.html','candidate_ref':execution['head']+':cad/gripper/viewer.html','literal':'const D= embedded model and fit data','original_sha256':hashlib.sha256(original_data).hexdigest(),'candidate_sha256':hashlib.sha256(candidate_data).hexdigest(),'identical':original_data==candidate_data,'method':'Read and hash the embedded data literal only; no geometry or data replacement.'}
fixture_manifest=json.loads(Path('C:/Users/dougl/Projects/product-design-system/gripper-ui-fixture/package/package.json').read_text())
result={
 'status':'COULD_NOT_TELL',
 'reviewed_input_hash':execution['head'],
 'reviewed_source_commit':source_commit,
 'reviewer':'gpt-6.1-sol at xhigh; new independent reviewer, single-reader visual assessment',
 'scope':'Two camera requirements only. No engineering or whole C2 acceptance; hardware is unbuilt.',
 'started_at':execution['started_at'],'finished_at':execution['finished_at'],
 'commands':execution['commands']+[{'command':'Invoke-ImpeccableDetector.ps1 -Json cad/gripper/viewer.html','exit':1,'evidence':'detector.json'}],
 'summary':'Focused browser suite passed 28 result records. Independent geometry and native visual inspection support framing at all three widths. The independent real copied-link scenario stopped on a review-script TypeError before cold/warm/late-host replay; no rerun is permitted, so complete independent acceptance is withheld.',
 'findings':[
  {'rank':1,'severity':'acceptance blocker','kind':'review execution defect, not a proven product defect','locator':'independent.cjs:49','observed':'TypeError: URL is not a constructor. The local string named URL shadows the standard URL constructor. Browser finally closed.','evidence':['independent-results.json','independent-browser.stdout.txt','copied-permalink.json'],'user_impact':'Cannot certify a newly orbited, actually copied permalink against independent cold/warm/reveal six-component measurements. Actual CDN scenario and separately authored control-count pass were also not reached.','next_owner':'parent review coordinator; a separately authorized review may correct the reviewer helper and complete only missing acceptance, without reopening source production','fix_direction':'Rename the review helper URL constant before any future independently authorized run. This lane stops under its no-rerun instruction.','observed_vs_inferred':'Observed exception and unexecuted tail; no inference that the product fails.'},
  {'rank':2,'severity':'coverage gap','kind':'partial state coverage','locator':'copied-permalink.json before.section and linked.section','observed':'Actual copied link captured pads, jaw 7, roll 40 and a newly orbited camera; section was off. Independent reload/reveal and non-default section retention were not proven.','evidence':['copied-permalink.json','ind-fit-selected-orbit.png'],'user_impact':'The broader state-retention claim remains incomplete.','next_owner':'parent review coordinator','fix_direction':'Include an enabled section on a supported finding in any future authorized independent acceptance.','observed_vs_inferred':'Observed state and missing proof.'}
 ],
 'visual_judgment':{'useful':True,'looks_good':'Yes for the bounded technical inspection task: complete assembled gripper, separated fasteners/fingers and readable highlights. Light and dark native images inspected.','is_clear':'Assembled/exploded views, labels and recovery states were clear to this reader. Saved-view conceptual outcome remains incomplete because the independent replay was not executed.','smallest_improvement':'Finish the missing independent copied-link replay evidence; no source visual change is justified by this review.'},
 'present':{'rubric_authored_before_images':'rubric.md','axis_A':'partial: A1/A2 pass; A3 confused due incomplete restoration proof','axis_B':'partial: B1/B3 pass; B2 confused due incomplete independent replay','single_reader_limit':'gpt-6.1-sol only; not universal user comprehension','items':[
  {'id':'A1','axis':'discrete-data','grade':'pass','observation':'I can identify both orange fingers, blue housing and the separated fasteners at all three widths. All 63 gripper meshes stayed visible with positive measured margins.','control_reachability':'Real Explode and Jaw controls exercised; manual orbit changed the bearing.'},
  {'id':'A2','axis':'discrete-data','grade':'pass','observation':'I can read Fasteners, side B, Fasteners, body and 0.01 mm; the pads view says 736 mm3 by design.','control_reachability':'Real finding selector used for pads; focused runner additionally selected and rendered gap/overlap at three widths.'},
  {'id':'A3','axis':'discrete-data','grade':'confused','observation':'I can read jaw 7 degrees, roll 40 degrees and copy the actual inspection URL, but I cannot confirm its restored state because my replay did not run.','fix':'Complete an authorized independent replay and enabled-section case.'},
  {'id':'B1','axis':'abstract-conceptual','grade':'pass','observation':'Assembled shows the working gripper; Explode separates its components; Fit isolates a named gap or intentional pad overlap.'},
  {'id':'B2','axis':'abstract-conceptual','grade':'confused','observation':'The supplied explicit-link regression restored numerically, but I did not independently reopen my new saved bearing; I cannot certify the same inspection context.','fix':'Complete cold, warm and late-host replay of the actual copied link.'},
  {'id':'B3','axis':'abstract-conceptual','grade':'pass','observation':'Loading, still loading and failed are visibly distinct; Reload and Parts are named recovery routes.','control_reachability':'Focused runner exercised keyboard Enter on Reload, Parts during failure and delayed-library recovery.'}
 ]},
 'viewports':[{'width':390,'height':844,'theme':'light and focused fit dark'},{'width':768,'height':1024,'theme':'dark'},{'width':1440,'height':1000,'theme':'light and focused fit dark'}],
 'framing_independent':framing,
 'embedded_model_and_fit_data_identity':data_identity,
 'framing_scope_note':'Independent oracle projects every vertex from all descendant mesh buffers with full ancestor visibility. All observed 63/63 meshes and 240240 vertices were retained. No component was hidden or reclassified. The UI transition sample happened to catch explode=0; the focused suite independently captured an explicit 0.5 midpoint at all widths. Do not mislabel that UI transition as a midpoint.',
 'focused_suite':{'exit':0,'passed':suite['passed'],'result_records':len(suite['results']),'failures':suite['failures'],'claims_executed':['three-width gap and overlap labels and insets','initial/still/terminal loading','keyboard Reload','Parts during missing dependency','delayed dependency recovery','three-width assembled, midpoint, endpoint framing','supplied explicit permalink cold/warm/late host','manual orbit after fit','ordinary resize aspect update with camera preserved','rendered model/fit/Parts/Assembly controls'],'evidence':'browser/camera-assertions.json','limitation':'Existing runner is complementary evidence, not a substitute for the failed independent copied-link replay.'},
 'six_component_measurements':{'component_order':['camera.x','camera.y','camera.z','target.x','target.y','target.z'],'tolerance':0.1,'focused_runner':camera,'independent_real_copy':{'before':copied['before'],'linked':copied['linked'],'actual_copied_url':copied['copied'],'encoded_camera':encoded_camera,'serialization_deltas':copy_deltas,'cold':None,'warm':None,'late_host':None,'later_readiness':None,'resize':None,'reason':'Review script stopped before replay. Serialization alone is not restoration proof.'}},
 'controls':{'actual_focused_counts':{k:v['total'] for k,v in counts.items()},'whole_control_records_equal_original_baseline':counts==baseline,'baseline':'../camera-resume-20261023/source2-red/control-counts.json','independent_second_count':'not reached','reset_camera_only':[{'scenario':s['name'],'observed':s['reset_camera_only']} for s in independent['scenarios']]},
 'console':{'independent_errors':independent['console_errors'],'independent_page_errors':independent['page_errors'],'independent_failed_requests':independent['requests_failed'],'focused_runner_console':'not collected by existing runner; empty stderr is not proof of zero console errors','server_http_errors':'favicon.ico 404 retained in server.log; not a JavaScript exception'},
 'dependency':{'fixture':'Only exact pinned Three 0.186.1 URL prefix fulfilled from original declared fixture; no source, HTML, geometry or fit-data interception.','fixture_manifest_version':fixture_manifest['version'],'cached_module_sha256':hashlib.sha256(Path('C:/Users/dougl/Projects/product-design-system/gripper-ui-runtime/cdn-three.module.min.js').read_bytes()).hexdigest(),'actual_cdn_availability':'not exercised: independent runner stopped before un-intercepted context; no claim of real CDN availability','pygments':'not exercised or installed; inherited static results are not an independent result'},
 'legacy_gaps_separate':[
  {'locator':'DESIGN.md:172-181','observed':'Stack-selection section explicitly says template, six answers and slots were not recorded; static vanilla stack is documented.','next_owner':'stack/documentation owner','scope':'Historical gap, not caused by camera patch; no migration requested.'},
  {'locator':'detector.json, cad/gripper/viewer.html:504 and related data-img elements','observed':'Canonical detector scanned the target and reported eight broken-image warnings for img elements whose source is populated dynamically.','next_owner':'existing design/browser harness owner','scope':'Static detector finding only; those drawing sheets were not inspected, so no live broken-image claim or camera-blocker inference.'}
 ],
 'inspected_images':images,
 'inspected_png_count':len(images),
 'cleanup':{**execution['cleanup'],**independent['cleanup'],'focused_browser_closed':'existing runner completed its explicit browser.close on exit 0','all_opened_tabs':'owned Playwright browsers closed; no user tabs opened or closed','no_other_processes_stopped':True},
 'preservation':{'source_tests_SPEC_TASK_LOG_public_geometry_changes':'none; git diff scoped verification performed','task_state':'No enrollment, repair or reconcile. Brief used as lane scope.','failed_run_policy':'No rerun or production repair after independent helper failure.','reviewed_bytes':'Raw PNG and JSON evidence preserved; local .gitattributes disables text normalization. Staged blob hashes verified before commit.','commit_push':'Own agent/gripper-camera-review-20261023 branch only; no PR/default merge/deploy. Final commit and remote reachability are returned to parent after verification.'},
 'receipt':'Canonical Write-DesignReviewReceipt.ps1, verdict partial, under receipt/; exact inputs hashed there.'
}
(OUT/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf8')
manifest=[{'path':p.relative_to(OUT).as_posix(),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print(json.dumps({'status':result['status'],'images':len(images),'framing_observations':len(framing),'control_counts':result['controls']['actual_focused_counts'],'focused_results':len(suite['results'])}))
