"""Exercise the CI scanner on real source files without importing their code."""
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


SCANNER = Path(__file__).resolve().parents[4] / 'setup/82_undefined_attr_check.py'


def scan(tmp_path, sources):
    for name, source in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding='utf-8')
    return subprocess.run([sys.executable, str(SCANNER), str(tmp_path)],
                          capture_output=True, text=True)


def test_class_and_instance_members_are_valid_without_executing_source(tmp_path):
    result = scan(tmp_path, {'backend.py': '''
        raise RuntimeError('the scanner must never import this module')
        class Backend:
            name = 'local'
            limit: int = 5
            def __init__(self):
                self.transport = None
            @property
            def label(self):
                return self.name
            async def classify(self):
                return self.transport, self.limit, self.label, self.health()
            def health(self):
                return True
    '''})
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 files scanned, 0 files with problems' in result.stdout


@pytest.mark.parametrize('definition', [
    "_gate = None", "def _gate(self): pass", "def __init__(self): self._gate = None",
])
def test_sibling_class_cannot_hide_a_ghost_attribute(tmp_path, definition):
    result = scan(tmp_path, {'skills.py': '''
        class Working:
            %s
        class Broken:
            def execute(self):
                return self._gate.set_attach()
    ''' % definition})
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'Broken' in result.stdout and 'self._gate' in result.stdout


def test_module_and_nested_function_names_are_not_methods(tmp_path):
    result = scan(tmp_path, {'skills.py': '''
        def _module_helper(): pass
        class Broken:
            def execute(self):
                def _nested_helper(): pass
                return self._module_helper(), self._nested_helper()
    '''})
    assert result.returncode == 1
    assert 'self._module_helper' in result.stdout
    assert 'self._nested_helper' in result.stdout


def test_nested_class_does_not_supply_outer_instance_attributes(tmp_path):
    result = scan(tmp_path, {'skills.py': '''
        class Outer:
            class Inner:
                def __init__(self):
                    self._gate = None
            def execute(self):
                return self._gate
    '''})
    assert result.returncode == 1
    assert 'Outer -> self._gate' in result.stdout


def test_function_local_and_conditional_classes_are_still_scanned(tmp_path):
    result = scan(tmp_path, {'skills.py': '''
        class Outer:
            def execute(self):
                class Inner:
                    def run(self): return self._missing
                return Inner()
        if True:
            class Conditional:
                def run(self): return self._gate
    '''})
    assert result.returncode == 1
    assert 'Outer.execute.<locals>.Inner -> self._missing' in result.stdout
    assert 'Conditional -> self._gate' in result.stdout
    assert 'Outer ->' not in result.stdout


def test_comprehension_variable_is_not_a_class_attribute(tmp_path):
    result = scan(tmp_path, {'skills.py': '''
        class Broken:
            values = [_gate for _gate in ()]
            def run(self): return self._gate
    '''})
    assert result.returncode == 1
    assert 'Broken -> self._gate' in result.stdout


def test_local_transitive_and_multiple_inheritance(tmp_path):
    result = scan(tmp_path, {'skills.py': '''
        class Root:
            name = 'base'
            def __init__(self): self._gate = None
        class Base(Root):
            def health(self): return True
        class Mixin:
            limit = 5
        class Child(Base, Mixin):
            def execute(self):
                return self.name, self._gate, self.health(), self.limit
    '''})
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('imports,base', [
    ('from .base import Base as Parent', 'Parent'),
    ('from pkg.base import Base', 'Base'),
    ('import pkg.base as backend', 'backend.Base'),
    ('import pkg.base', 'pkg.base.Base'),
])
def test_imported_bases_are_resolved_inside_the_scanned_package(tmp_path, imports, base):
    result = scan(tmp_path, {
        'pkg/__init__.py': '',
        'pkg/base.py': '''
            class Base:
                name = 'base'
                def __init__(self): self._client = None
                def health(self): return True
        ''',
        'pkg/child.py': '''
            %s
            class Child(%s):
                def execute(self):
                    return self.name, self._client, self.health()
        ''' % (imports, base),
    })
    assert result.returncode == 0, result.stdout + result.stderr


def test_inherited_definitions_do_not_merge_unrelated_modules(tmp_path):
    result = scan(tmp_path, {
        'pkg/__init__.py': '',
        'pkg/base.py': 'class Base: pass',
        'pkg/unrelated.py': 'class Base: _gate = None',
        'pkg/child.py': '''
            from .base import Base
            class Child(Base):
                def execute(self): return self._gate
        ''',
    })
    assert result.returncode == 1
    assert 'Child -> self._gate' in result.stdout


@pytest.mark.parametrize('imports,base', [
    ('from rclpy.node import Node as RosNode', 'RosNode'),
    ('import rclpy.node as ros', 'ros.Node'),
])
def test_ros_api_is_inherited_only_by_node_subclasses(tmp_path, imports, base):
    result = scan(tmp_path, {'skills.py': '''
        %s
        class Skill(%s):
            def start(self): return self.create_service(), self.get_logger()
        class Child(Skill):
            def start(self): return self.create_service()
        class Plain:
            def start(self): return self.create_service()
    ''' % (imports, base)})
    assert result.returncode == 1
    assert 'Plain -> self.create_service' in result.stdout
    assert 'Skill ->' not in result.stdout and 'Child ->' not in result.stdout


def test_test_files_are_excluded_without_hiding_production_errors(tmp_path):
    result = scan(tmp_path, {
        'skills.py': 'class Broken:\n    def run(self): return self._gate',
        'test/helper.py': 'class Fake:\n    def __init__(self): self._gate = None',
        'tests/test_bad.py': 'class Fake:\n    def run(self): return self._missing',
    })
    assert result.returncode == 1
    assert '1 files scanned, 1 files with problems' in result.stdout
    assert 'self._missing' not in result.stdout


@pytest.mark.parametrize('kind', ['missing', 'empty', 'syntax'])
def test_invalid_scan_input_fails_closed(tmp_path, kind):
    root = tmp_path / 'source'
    if kind != 'missing':
        root.mkdir()
    if kind == 'syntax':
        (root / 'broken.py').write_text('class Broken(', encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCANNER), str(root)],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'SCAN ERROR:' in result.stderr
    assert 'SCAN COMPLETE:' not in result.stdout
