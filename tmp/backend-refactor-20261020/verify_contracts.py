"""Compare the saved pre-refactor contracts without connecting to MySQL."""
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from app.main import app

before_api = json.loads((WORK/'openapi-before.json').read_text(encoding='utf-8'))
assert app.openapi() == before_api, 'Public HTTP schema changed'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

unchanged = []
unchanged_ast = []
for old in sorted((WORK/'before/domain').glob('*.py')):
    current = ROOT/'app/domain'/old.name
    assert ast.dump(ast.parse(old.read_text(encoding='utf-8-sig'))) == ast.dump(ast.parse(current.read_text(encoding='utf-8-sig'))), current
    unchanged_ast.append(str(current.relative_to(ROOT)))
    if digest(old) == digest(current):
        unchanged.append(str(current.relative_to(ROOT)))
for name in ['fua_print.py', 'nutrition_context.py']:
    assert digest(WORK/'before/services'/name) == digest(ROOT/'app/services'/name)
    unchanged.append('app/services/'+name)

def cls(path, name):
    return next(node for node in ast.parse(path.read_text(encoding='utf-8-sig')).body
                if isinstance(node, ast.ClassDef) and node.name == name)

sizes = {}
for name, filename in [('PatientService', 'patient.py'), ('AttentionService', 'attention.py')]:
    before = cls(WORK/'before/services'/filename, name)
    after = cls(ROOT/'app/services'/filename, name)
    public = lambda node: {item.name: ast.dump(item.args) for item in node.body
                          if isinstance(item, ast.FunctionDef) and not item.name.startswith('_')}
    assert public(before) == public(after), name+' public signatures changed'
    sizes[name] = {
        'before_lines': before.end_lineno-before.lineno+1,
        'after_lines': after.end_lineno-after.lineno+1,
        'before_methods': sum(isinstance(item,ast.FunctionDef) for item in before.body),
        'after_methods': sum(isinstance(item,ast.FunctionDef) for item in after.body),
    }
    if name == 'AttentionService':
        for label, node in [('before',before), ('after',after)]:
            method = next(item for item in node.body if isinstance(item,ast.FunctionDef) and item.name=='create')
            sizes[name][label+'_create_lines'] = method.end_lineno-method.lineno+1

export = cls(ROOT/'app/services/nutrition_export.py', 'NutritionExportService')
assert not export.bases
report = {'openapi_unchanged':True, 'public_service_signatures_unchanged':True,
          'export_independent':True, 'unchanged_clinical_sources':unchanged,
          'unchanged_domain_ast':unchanged_ast, 'size':sizes}
(WORK/'structural-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
