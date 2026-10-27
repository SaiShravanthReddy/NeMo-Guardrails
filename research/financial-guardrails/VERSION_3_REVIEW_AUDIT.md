# Version 3 development-review audit

Status: packet correction and assistant audit completed on 2026-10-27.
The original review has a documented blinding limitation. This report does not
amend the frozen protocol or certify its blinded human-review requirement.

## Completed review and provenance

The review set contains 60 unique development cases. The project owner confirmed
that two different people independently reviewed all 60 model-assisted labels
without seeing each other's answers, and that a person reviewed and approved the
reconciliation. These are owner-attested review facts; reviewer identities are
not stored in this aggregate report.

All 60 final rows use the allowed labels and match the comparison artifact.
The 31 cases with at least one disagreement have reconciled choices. Labels on
the 29 cases with complete agreement were preserved.

Agreement before reconciliation, computed from the supplied reviewed files:

| Field | Agreements | Agreement rate | Cohen's kappa |
| --- | ---: | ---: | ---: |
| Threat assessment | 41/60 | 68.3% | 0.497 |
| Control action | 47/60 | 78.3% | 0.624 |
| Authorization context | 40/60 | 66.7% | 0.403 |

These statistics describe agreement between the supplied model-assisted human
reviews. They do not establish accuracy or independent unaided human agreement.

## Packet defect and correction

Case-ID masking did not remove every benchmark hint. Sixteen cases retained
scenario descriptions or vulnerability-target tags. Auditing additional scoring
feedback expanded the affected set to 21 cases.

A versioned private packet removes identified scenario descriptions,
business-scenario tags, vulnerability-target fields, vulnerability feedback,
attack-intent flags, benchmark risk-flag containers, and security-alert
annotations. Both positive and negative annotation values are removed.
User messages and agent calls remain byte-for-byte unchanged. Message order,
roles, concrete tool results and errors, and specific compliance-tool outputs
are preserved. Those tool outputs remain evidence, not trusted authorization.

Validation checked all 60 cases for stable IDs, preserved user/call contents,
stable message counts/order/roles, removal of the targeted fields, and
idempotence. Synthetic regression checks verified that removal does not erase
malicious instructions, tool errors, authorization evidence, or control limits.
Original files are preserved with checksums. All case-level artifacts remain
private and Git-ignored.

This removes identified hints; it does not establish that every possible cue is
absent. The original reviewers' exposure cannot be undone by editing the packet.

## Assistant audit of affected cases

At the owner's request, Codex (gpt-6-astra) assessed the 21 affected cases using
cleaned request, action, and result evidence. Prior reviews were visible. This
was a model-assisted audit, not a new blinded human review.

- Seventeen cases retained their three labels.
- Three cases received a proposed change from `sanitize` to `block` at an
  actual tool call that explicitly suppresses required disclosures. A safe
  rewrite can be offered separately; it does not authorize that original call.
- One case received a proposed uncertainty label and `allow` for inspection
  only: the request asks to check a configuration and contains no executed
  deployment. This never authorizes deployment with bypass settings.

The private audit records evidence indexes, reasons, prior labels, proposed
labels, and hashes. The four proposed corrections have model provenance; the
original human-approved labels have not been overwritten. Labels on the other
39 cases were carried forward, not newly semantically certified by this audit.

## Use and remaining limits

The corrected packet and audit can inform exploratory policy design with this
limitation disclosed. They do not retroactively satisfy the ratified blinded
review procedure. A qualifying claim needs either new blinded review evidence
or an explicitly approved protocol change that acknowledges the limitation.
No such new approval is claimed here.

The 60 selected cases cover 12 development source groups, with 48 unavoidable
group repeats. Excluding these groups leaves 405 qualification cases, including
36 normal cases. One fold has only six normal cases from two normal groups.
This remains limited development evidence; the independent-holdout requirement
still applies.

The review correction changes no benchmark labels, runtime adapters, frozen
results, or model configuration.

## Evaluation-input audit and matched comparison

The detector input audit found another leakage route: raw event IDs contain
benchmark case IDs. CNFinBench IDs expose `harmful` or `harmless` in the judge
prompt; some FinVault IDs expose scenario information. FinVault tool results
also contain generator annotations, including vulnerability targets and risk
flags. The earlier Version 1 model results used these raw inputs and therefore
cannot serve as a clean efficacy baseline without a matched rerun.

The optional `v3_clean` input view replaces raw event IDs with stable opaque
IDs, masks bracketed case references, and removes identified FinVault generator
annotations from tool results. It preserves message order, tool arguments,
and concrete business evidence. The default `legacy_raw` view remains for
reproducing old artifacts. The selected input view and reviewed-group manifest
checksum are recorded in the run manifest and checkpoint identity.

The private reviewed-group manifest identifies 12 development source groups.
Version 3 qualification folds exclude all cases from those groups. The
remaining folds contain 60, 119, 118, and 108 cases; their normal-case counts
are 6, 11, 10, and 9. These small denominators limit any FPR claim.

Local verification covered all 642 CNFinBench and 1,043 FinVault cases under
the clean view, with no raw event IDs or targeted annotation fields remaining.
A rules-only 60-case fold smoke run verified the exclusion and artifact path;
it is not model-performance evidence. Before claiming an improvement, rerun
Version 1 and Version 3 with the same clean view and exact remaining cases.
