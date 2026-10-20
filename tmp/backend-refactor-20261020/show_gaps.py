import ast
import json
from pathlib import Path
import sys

report=json.loads(Path(__file__).with_name('coverage-progress.json').read_text())
for name,data in report['files'].items():
    if len(sys.argv)>1 and not any(part in name for part in sys.argv[1:]): continue
    if not data['missing_lines'] and not data['missing_branches']: continue
    path=Path(name)
    lines=path.read_text(encoding='utf-8-sig').splitlines()
    print('\n'+name+'  '+str(data['summary']['percent_covered'])+'%')
    for start in sorted(set(data['missing_lines'] + [b[0] for b in data['missing_branches']])):
        print(' | '.join(f'{i+1}: {lines[i].strip()}' for i in range(max(0,start-2),min(len(lines),start+2))))
    print('BRANCHES',data['missing_branches'])
