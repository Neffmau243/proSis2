"""One-off source extraction helpers; not imported by the application."""
import ast
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[2]

def source(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')

def method(path, cls, name):
    text = source(path)
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
    start = min([fn.lineno] + [d.lineno for d in fn.decorator_list])
    return '\n'.join(text.splitlines()[start-1:fn.end_lineno]) + '\n'

def replace_method(path, cls, name, replacement):
    text = source(path)
    node = next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name==cls)
    fn = next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name==name)
    start = min([fn.lineno] + [d.lineno for d in fn.decorator_list])
    lines = text.splitlines(keepends=True)
    write(path, ''.join(lines[:start-1]) + replacement + ''.join(lines[fn.end_lineno:]))

def write(path, text):
    destination = ROOT / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding='utf-8')

def imports(path):
    text = source(path)
    return '\n'.join(ast.get_source_segment(text, n) for n in ast.parse(text).body if isinstance(n,(ast.Import,ast.ImportFrom))) + '\n'

def standalone_method(path, cls, name, newname=None):
    result = method(path, cls, name)
    if newname:
        result = result.replace('def '+name+'(', 'def '+newname+'(', 1)
    return result
