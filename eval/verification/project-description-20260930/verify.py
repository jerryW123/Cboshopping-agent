"""核查文案调整范围，不运行服务或读取业务数据。"""
from pathlib import Path
import ast
import difflib
import hashlib
import json
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
TARGETS = [
    'README.md', 'pyproject.toml', 'docs/设计演进记录.md',
    'app/infrastructure/persistence/sql/tables.py',
    'app/application/agents/context_policy.py',
    'scripts/eval/run_product_recall.py',
    'scripts/eval/run_category_recall.py',
    'scripts/eval/validate_datasets.py',
]
INDEX = 'docs/改动记录/README.md'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline():
    protected = {}
    for folder in ['app', 'scripts', 'frontend', 'docs', 'tests/contracts', 'eval/verification']:
        for path in (ROOT / folder).rglob('*'):
            if not path.is_file() or OUT in path.parents:
                continue
            if any(part in path.parts for part in ['node_modules', '__pycache__']):
                continue
            name = path.relative_to(ROOT).as_posix()
            if name in TARGETS + [INDEX] or name.endswith('.tsbuildinfo'):
                continue
            protected[name] = digest(path)
    value = {
        'targets': {name: (ROOT / name).read_text(encoding='utf-8') for name in TARGETS + [INDEX]},
        'protected_sha256': protected,
    }
    with (OUT / 'before.json').open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    print(f'Baseline saved: {len(TARGETS)} content files, one index, {len(protected)} protected files')


def without_module_docstring(source):
    tree = ast.parse(source)
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        tree.body.pop(0)
    return ast.dump(tree, include_attributes=False)


def verify():
    before = json.loads((OUT / 'before.json').read_text(encoding='utf-8'))
    checks = {}
    diff = []
    for name in TARGETS + [INDEX]:
        old = before['targets'][name]
        new = (ROOT / name).read_text(encoding='utf-8')
        diff.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='before/' + name, tofile='after/' + name))
        if name.endswith('.py'):
            checks['python_behavior:' + name] = without_module_docstring(old) == without_module_docstring(new)
        if name == 'pyproject.toml':
            checks['toml_values_unchanged'] = tomllib.loads(old) == tomllib.loads(new)
        if name != INDEX:
            checks['current_copy_no_course_reference:' + name] = re.search('教学|教程|课程|实战项目', new) is None
    changed_protected = [name for name, sha in before['protected_sha256'].items() if not (ROOT / name).is_file() or digest(ROOT / name) != sha]
    checks['protected_files_unchanged'] = not changed_protected
    old_design = before['targets']['docs/设计演进记录.md']
    new_design = (ROOT / 'docs/设计演进记录.md').read_text(encoding='utf-8')
    checks['design_history_unchanged'] = old_design.split('## 每日工程更新', 1)[1] == new_design.split('## 每日工程更新', 1)[1]
    old_index = before['targets'][INDEX]
    new_index = (ROOT / INDEX).read_text(encoding='utf-8')
    checks['old_index_preserved'] = '\n'.join(line for line in new_index.split('\n') if not line.startswith('| [2026-09-30]')) == old_index
    link_docs = ['README.md', 'docs/设计演进记录.md', INDEX, 'docs/改动记录/2026-09-30/README.md', 'docs/改动记录/2026-09-30/项目说明与工程文档入口整理.md']
    missing = []
    for name in link_docs:
        source = ROOT / name
        for raw in re.findall(r'\]\(([^)]+)\)', source.read_text(encoding='utf-8')):
            target = raw.strip('<>').split('#')[0]
            if not target or '://' in target or target.startswith('mailto:'):
                continue
            if not (source.parent / target).exists():
                missing.append({'source': name, 'target': target})
    preexisting_missing = []
    for item in missing:
        old_source = before['targets'].get(item['source'], '')
        old_targets = [raw.strip('<>').split('#')[0] for raw in re.findall(r'\]\(([^)]+)\)', old_source)]
        if item['target'] in old_targets:
            preexisting_missing.append(item)
    new_missing = [item for item in missing if item not in preexisting_missing]
    checks['no_new_missing_local_document_links'] = not new_missing
    result = {
        'checks': checks, 'passed': all(checks.values()),
        'protected_files_checked': len(before['protected_sha256']),
        'changed_protected_files': changed_protected, 'missing_links': missing,
        'preexisting_missing_links': preexisting_missing, 'new_missing_links': new_missing,
        'sha256': {name: digest(ROOT / name) for name in TARGETS + [INDEX]},
        'limits': '静态检查；不验证链接锚点，不运行应用回归、外部链路或效果验收。',
    }
    (OUT / 'changes.diff').write_text(''.join(diff), encoding='utf-8')
    (OUT / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['baseline']:
        baseline()
    else:
        raise SystemExit(verify())
