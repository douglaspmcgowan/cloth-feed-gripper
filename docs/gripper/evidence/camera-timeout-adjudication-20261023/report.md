# Camera source2 timeout adjudication

**Decision: validate the existing candidate only. Production remains stopped.** Source attempts and failed execution outcomes remain **2/2**. The timed-out route is not a successful implementation or fresh visual acceptance.

Input `b6c7712c292dc83cbfe17a89aae3e4ef0fa2d20d` preserves only the maker report after source `ed77773de9654ac05940a5ea3f623be5cdb46a8a`. Exact diff `214f7c8..ed77773` contains 78 paths: six source/spec/ledger/test paths and 72 evidence paths. This lane verified the 87 unchanged input hashes and all seven original source blob hashes at both prepared and baseline commits. Preserved report SHA-256 matches the preservation receipt.

The continuation contract's failure policy stops production and requires report-only tactics; it does not require discarding the artifact. The checkpoint's terminal READY precondition was not achieved by the route. Maker READY cannot satisfy that precondition. Independent validation can assess the preserved artifact without renewing its producer or resetting either failure.

Actual receipts contain 21 red result rows with nine failures and 28 green rows with none. These include control inventory and existing scenarios, not 28 independent camera assertions. Parent host proof is now complete at the exact preserved candidate: static log reports **29 passed, 1 skipped**, generator and focused-browser exits are zero, and browser JSON has 28 rows/zero failures. Parent records deterministic generation and unchanged geometry before/after. These are inspected parent receipts, not suites rerun by this lane.

No remaining product defect is demonstrated by this bounded source inspection. Concrete verification limits: Reset is not clicked by the regression; control counts do not prove interaction parity; depth counts are recorded but not asserted (all nine green pose records have zero outside-depth vertices); late attachment starts from an already ready model. Fresh review should exercise Reset, retained controls, model framing and cold/warm permalink restoration, inspect native renders, and return acceptance or rejection at this exact candidate. No general audit or new production is warranted here.

**Remaining gate:** parent-owned NEW independent browser-capable design-review/user/present acceptance. Host proof and this report do not supply that verdict. Rejection means stop under the existing boundary; no automatic third producer, repair, clock renewal, A1/C4 restart or publication.

Route `78847bd7` remains `timed-out-with-work`, adapter exit 124, with confirmed work and no worker potentially live. Fresh remote listing in this lane failed `SEC_E_NO_CREDENTIALS`; route-recorded push confirmation is distinguished from fresh remote proof. Original helper 29048 cleanup remains unverified here. No server or process cleanup was attempted.

Exact evidence, authorities, counts and uncertainties are in `report.json`. Only these adjudication reports were authored.
