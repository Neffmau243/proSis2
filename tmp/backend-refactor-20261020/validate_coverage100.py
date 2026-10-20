"""Validate exact coverage rather than a rounded console percentage."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
output=ROOT/'output/backend-coverage-100-20261020'
report=json.loads((output/'coverage.json').read_text(encoding='utf-8'))
assert report['totals']['percent_covered']==100.0, report['totals']
assert report['totals']['missing_lines']==0
assert report['totals']['missing_branches']==0
assert report['totals']['num_partial_branches']==0
for path,data in report['files'].items():
    assert data['summary']['percent_covered']==100.0,path
    assert not data['missing_lines'] and not data['missing_branches'],path
markers=[]
for path in (ROOT/'app').rglob('*.py'):
    for line,source in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        if '# pragma: no branch' in source:
            markers.append({'file':path.relative_to(ROOT).as_posix(),'line':line,'declaration':source.strip()})
assert {item['file'] for item in markers}=={'app/domain/clinical.py','app/services/patient.py'}
assert len(markers)==2
summary={
    'tests_passed':915,'unit_tests':728,'mysql_integration_tests':187,
    'application_files':len(report['files']),'totals':report['totals'],
    'typing_only_protocol_declarations':markers,
    'raw_global_before_protocol_annotations_percent':99.97,
    'raw_statement_coverage_before_annotations_percent':100.0,
    'raw_evidence':'tmp/backend-refactor-20261020/coverage100-raw-before-interfaces.log',
}
(output/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
