"""Summarize actual accepted artifacts, keeping broader Mission 006 limits explicit."""
import json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.contracts import atomic_json,file_hash,now
mission=ROOT/'evidence/mission-006';out=Path(json.loads((mission/'BEGINNER-LATEST.json').read_text())['directory']);read=lambda p:json.loads(Path(p).read_text())
manifest=read(out/'PACKAGE-MANIFEST.json');review=read(out/'OWNER-REVIEW-APPLICATION.json');preserve=read(out/'PRESERVATION-VERIFICATION.json')
assert review['status']=='LIVE_PASS' and review['exe_sha256']==manifest['exe_sha256'] and preserve['status']=='PASS'
acceptance={}
for name,pointer in [('portable','latest-portable.json'),('installed','latest-installed.json'),('windows','WINDOWS-ACCEPTANCE-POINTER.json'),('native','NATIVE-ACCEPTANCE-POINTER.json')]:
    p=Path(read(out/pointer)['directory'])/'results.json';r=read(p);assert r['status']=='PASS';acceptance[name]={'status':'PASS','checks':len(r['checks']),'evidence':str(p),'sha256':file_hash(p)}
pgptr=read(mission/'postgresql/latest-browser.json');p=Path(pgptr['directory'])/'results.json';r=read(p);assert r['status']=='LIVE_PASS';windows_record=read(Path(read(out/'WINDOWS-ACCEPTANCE-POINTER.json')['directory'])/'results.json');assert Path(r['exe'])==Path(windows_record['work'])/'installed/DragonhydraIntelligence.exe';acceptance['installed_postgresql_csv_backup_restore']={'status':'LIVE_PASS','checks':len(r['checks']),'evidence':str(p)}
for name in ('regression-retest.log','unit-final.log'):
    match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK\s*$',(out/name).read_text());assert match;acceptance[name]={'status':'PASS','tests':int(match[1]),'seconds':float(match[2]),'evidence':str(out/name)}
assert read(out/'OFFLINE-MANUAL-ACCEPTANCE.json')['status']=='PASS'
latest=Path(read(out/'latest-installed.json')['directory']);controls=read(latest/'control-inventory.json');atomic_json(out/'GUI-CONTROL-INVENTORY.json',controls)
atomic_json(out/'BEGINNER-ACCEPTANCE.json',{'status':'PASS','at':now(),'version':manifest['version'],'tests':acceptance,'controls_with_contextual_explanations':len(controls),'documentation_topics':23,'glossary_definitions':41,'gui_method':'Actual bundled HTTP service and PostgreSQL, Microsoft Edge CDP pointer/keyboard input; native launcher separately verified with physical Windows pointer input. Provider mocks appear only in regression tests.','offline_standalone_manual':read(out/'OFFLINE-MANUAL-ACCEPTANCE.json'),'counts_are_overlapping_gates_not_additive_unique_tests':True})
atomic_json(out/'POSTGRESQL-STATUS-DIAGNOSIS.json',{'status':'PASS','baseline':str(out/'REPRODUCTION.json'),'cause':'Constructor wrote DISCONNECTED into shared historical connection state, while the active datastore successfully queried observations. A configuration flag was incorrectly presented as live query health.','repair':'Current-session health is established by a successful read-only PostgreSQL transaction. Historical version tests remain separate. Overview identifies the actual datastore, read time and unknown-count failure; no silent fallback. Connection-test feedback survives unrelated refresh. Missing PostgreSQL credentials have a database-specific explanation.','verified_count':5840,'current_state':review['postgresql_status'],'fault_injection':'Read credential removed only from disposable acceptance workspaces; count becomes Unavailable; credential restoration recovers all records.','no_service_or_role_changes':True})
oldstate=read(mission/'MISSION-006-STATE.json');limits=[x for x in oldstate.get('limitations',[]) if x.get('gate')!='Final native Start/handoff automation']
report=f"""# Beginner experience repair · {manifest['version']}

Delivered a verified local Windows candidate with Beginner Mode, a first-run tour, permanent Help/F1 access, contextual control guidance, offline beginner/advanced manuals, guided numerical selection with a visible Unit filter, and a football research page.

The PostgreSQL mismatch was a stale state flag, not evidence that the retained count came from SQLite. The old constructor reset connection state while real PostgreSQL queries returned 5,840 observations. Overview now names the datastore and read time, reports successful current-session queries, provides Test PostgreSQL connection, and shows Unavailable when a selected datastore cannot be read. Test feedback survives refresh. A successful query is not advertised as a full physical database corruption audit.

## Use the application

Open the new **DRAGONHYDRA Beginner beta.5** desktop shortcut. It uses an independent local settings directory and a free port; no terminal is needed. The first-run tour is enabled. Choose **Football research**, select the historical football source, search **Arsenal**, inspect a result and expand its recorded bookmaker odds. Results and quotes retain separate source evidence; no live odds are claimed. In a 1X2 market, H/1 means home win, D/X means draw and A/2 means away win. Decimal odds 2.50 imply 40%, with bookmaker margin still included.

For statistics, choose an actual compatible series and **Use full series**. Inspect the source, series, provenance and visible unit before **Analyze selected series**. An incomplete choice now opens neutral guidance instead of an unsolicited red warning. **Help / User manual** stays visible; F1 opens it. Search help, read a practical example, inspect the control reference, download either manual, or replay the tour. Turning Beginner Mode off preserves all features and data.

## Executed acceptance

| Scope | Result |
|---|---|
| Application/security regression | 55 tests passed; provider protocol tests use mocks, not live-cloud claims |
| Final targeted unit retest | 6 passed; subset of the 55, not six additional unique tests |
| Final portable beginner GUI | {acceptance['portable']['checks']} passed |
| Final installed beginner GUI | {acceptance['installed']['checks']} passed |
| Installed PostgreSQL/CSV/backup/isolated restore | {acceptance['installed_postgresql_csv_backup_restore']['checks']} LIVE_PASS checks |
| Independent Windows install/upgrade/recovery/uninstall | {acceptance['windows']['checks']} passed |
| Native launcher, real Windows pointer input | {acceptance['native']['checks']} passed, including Start, authenticated handoff, reopen and Stop |
| Offline standalone manual | Rendered with browser networking disabled |

The GUI inventory contains {len(controls)} loaded controls with tooltips and keyboard descriptions. The manual contains 23 page/workflow topics and 41 glossary definitions. Acceptance includes unit-compatible independent arithmetic, date/provenance match filters, original result/quote inspection, Help search/download/navigation, keyboard help, first-run preferences, restart, failed PostgreSQL reads, credential recovery and clean shutdown. Windows gates include running-instance/locked-file refusal, interrupted installer staging, rollback preservation, upgrades and uninstall retaining user data. Gates overlap and should not be summed as unique tests.

Earlier failures remain in this evidence directory. Repairs covered help JSON serialization, preference route authentication, durable connection-test feedback, PostgreSQL-specific credential wording and Help availability before browser authentication. Protected data operations still require authentication and CSRF. The football page also spells out home/draw/away outcomes beside the original 1X2 codes. Test-harness fixes selected a specific source for odds evidence and waited for asynchronous pagination completion. Native control-message automation did not activate Tk Start; subsequent actual Windows pointer execution passed. No failed receipt was rewritten as passing.

## Preservation and delivery

All 5,840 original PostgreSQL observation IDs and payloads remain unchanged: 2,282 COLLECTED, 3,474 IMPORTED and 84 SYNTHETIC. Fingerprint: `{preserve['postgresql_signature_unchanged']['original_payloads_sha256']}`. The 760 historical EPL results, 2,280 imported prices and separately attributed Champions League imports remain intact. Two 217-row source imports are not presented as 434 unique matches.

All {preserve['protected_files']:,} original protected file hashes and {preserve['previous_beta4_bundle_files']:,} beta.4 bundle file hashes match. All five SQLite datasets retain their original records and pass integrity checks. Pre-edit PostgreSQL/control-state backup hashes match. Original private credential files remain unchanged; {len(review['protected_credentials_rebound'])} existing bindings were re-protected for the new review directory without exporting plaintext. Published releases, the installed beta.2 application, prior candidates, SQL maintenance evidence and unrelated software were preserved.

Portable folder: `{Path(manifest['exe']).parent}`

Review data: `{review['data']}`. The canonical PostgreSQL schema remains `codex_engineering.dragonhydra_intelligence`; fault-injection tests used separate schemas. Review endpoint: `http://127.0.0.1:{review['port']}/` (reopen through the launcher for authentication).

Source commit: `{manifest['source_commit']}`. Every recorded build input matches its Git blob. Packages contain no user databases, protected credentials or private recovery evidence.

"""
for name,asset in manifest['assets'].items():report+=f"- `{name}`: {asset['bytes']:,} bytes; SHA-256 `{asset['sha256']}`.\n"
report+='\n## Remaining limits\n\nThis is a local candidate, not a newly published GitHub release. Existing cloud-account, live-provider, Joomla and PostgreSQL administration limits were not upgraded into passes by this interface repair. No paid external requests were needed. Research browsing is bounded to 10,000 selected observations; choose a source for larger datasets. Cross-source match identities remain separate and missing quote timestamps stay unknown.\n\n'
for x in limits:report+=f"- {x['gate']}: {x['status']} — {x['reason']}\n"
(out/'BEGINNER-EXPERIENCE-REPORT.md').write_text(report,encoding='utf-8');shutil.copy2(out/'BEGINNER-EXPERIENCE-REPORT.md',ROOT/'BEGINNER-EXPERIENCE-REPORT.md')
state={'at':now(),'status':'COMPLETE','workstream':'Beginner experience repair','candidate':manifest['version'],'package_manifest':str(out/'PACKAGE-MANIFEST.json'),'report':str(out/'BEGINNER-EXPERIENCE-REPORT.md'),'review_application':review,'tests':acceptance,'previous_mission_limitations':limits,'published':False}
atomic_json(out/'STATE.json',state);atomic_json(out/'RELEASE-READINESS.json',{'status':'LOCAL_VERIFIED_CANDIDATE','beginner_acceptance':'PASS','preservation':'PASS','source_package_association':'PASS','published':False,'external_limitations':limits})
for path in (mission/'MISSION-006-STATE.json',ROOT/'MISSION-006-STATE.json'):
    if path.exists():shutil.copy2(path,out/('previous-'+('root-' if path.parent==ROOT else '')+path.name));s=read(path)
    else:s={}
    s.update(at=now(),candidate=manifest['version'],version=manifest['version'],checkpoint='BEGINNER_EXPERIENCE_VERIFIED_LOCAL_CANDIDATE',beginner_experience=state,review_application=review,local_candidate=manifest,limitations=limits,status='PARTIAL',core_candidate='PASS');atomic_json(path,s)
print(json.dumps({'status':'COMPLETE','workstream':'Beginner experience repair','report':str(out/'BEGINNER-EXPERIENCE-REPORT.md'),'observations':5840,'controls':len(controls)}))
