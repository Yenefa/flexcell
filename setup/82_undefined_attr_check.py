#!/usr/bin/env python3
"""Static audit: find self.X attributes with no definition in their class.

Catches the `self._gate` class of landmine (used-but-undefined node attribute
that crashes at runtime and, via rclpy's default-result fallback, masquerades
as action SUCCESS). Pure AST, no imports of scanned code. Definitions are
class-scoped and include class members and bases found in the scanned source.
This is a declaration check, not control-flow or initialization-order analysis.

Usage: python 82_undefined_attr_check.py <src_root>
Exit: 0 = clean, 1 = missing attributes, 2 = invalid/unreadable scan input.
"""
import argparse
import ast
import sys
from pathlib import Path

NODE_API = {
    'create_publisher', 'create_subscription', 'create_client', 'create_service', 'create_timer',
    'declare_parameter', 'get_parameter', 'get_parameters', 'get_logger',
    'get_clock', 'get_name', 'destroy_node', 'set_parameters',
    'count_subscribers', 'count_publishers', 'resolve_topic_name',
    'destroy_publisher', 'destroy_subscription', 'destroy_client',
    'destroy_service', 'destroy_timer',
}


class InstanceAccess(ast.NodeVisitor):
    def __init__(self):
        self.assigned, self.used = set(), set()

    def visit_ClassDef(self, node):
        # A nested class has its own self, even inside an enclosing method.
        pass

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'self':
            target = self.assigned if isinstance(node.ctx, ast.Store) else self.used
            target.add(node.attr)
        self.generic_visit(node)


class ClassScope(ast.NodeVisitor):
    def __init__(self, node):
        self.assigned, self.used = set(), set()
        for statement in node.body:
            self.visit(statement)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.assigned.add(node.id)

    def visit_ClassDef(self, node):
        self.assigned.add(node.name)

    def visit_ListComp(self, node):
        # Comprehension targets are local to the comprehension, not the class.
        pass

    visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_ListComp

    def visit_FunctionDef(self, node):
        self.assigned.add(node.name)
        access = InstanceAccess()
        access.visit(node)
        self.assigned.update(access.assigned)
        self.used.update(access.used)

    visit_AsyncFunctionDef = visit_FunctionDef


def module_name(path):
    parts = [] if path.name == '__init__.py' else [path.stem]
    parent = path.parent
    while (parent / '__init__.py').is_file():
        parts.insert(0, parent.name)
        parent = parent.parent
    return '.'.join(parts) or path.parent.name


class ModuleScope(ast.NodeVisitor):
    def __init__(self, path, tree):
        self.path, self.name = path, module_name(path)
        self.imports, self.classes = {}, {}
        self.package = self.name if path.name == '__init__.py' else self.name.rpartition('.')[0]
        self.visit(tree)
        self.index_classes(tree)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports[alias.asname or alias.name.split('.')[0]] = (
                alias.name if alias.asname else alias.name.split('.')[0])

    def visit_ImportFrom(self, node):
        source = node.module
        if node.level:
            package = self.package.split('.')
            prefix = package[:len(package) - node.level + 1]
            source = '.'.join(prefix + ([node.module] if node.module else []))
        for alias in node.names:
            if alias.name != '*':
                self.imports[alias.asname or alias.name] = '.'.join(filter(None, (source, alias.name)))

    def visit_ClassDef(self, node):
        # Class/method imports are not module bindings.
        pass

    def visit_FunctionDef(self, node):
        pass

    visit_AsyncFunctionDef = visit_FunctionDef

    def index_classes(self, node, parents=()):
        # Include conditional and function-local classes, while keeping their
        # members separate from those of enclosing and sibling classes.
        for child in ast.iter_child_nodes(node):
            scope = parents
            if isinstance(child, ast.ClassDef):
                scope += (child.name,)
                self.classes['.'.join(scope)] = (child, ClassScope(child))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope += (child.name, '<locals>')
            self.index_classes(child, scope)

    def base_name(self, base, classname, classes):
        if isinstance(base, ast.Subscript):
            base = base.value
        parts = []
        while isinstance(base, ast.Attribute):
            parts.insert(0, base.attr)
            base = base.value
        if not isinstance(base, ast.Name):
            return None
        parts.insert(0, base.id)
        name = '.'.join(parts)
        # A lexical class definition takes precedence over an imported name.
        parents = classname.split('.')[:-1]
        for length in range(len(parents), -1, -1):
            candidate = '.'.join([self.name] + parents[:length] + [name])
            if candidate in classes:
                return candidate
        if parts[0] in self.imports:
            return '.'.join([self.imports[parts[0]]] + parts[1:])
        return None


def scan(root):
    if not root.is_dir():
        raise ValueError('source root is not a directory: %s' % root)
    paths = [path for path in sorted(root.rglob('*.py'))
             if not {'test', 'tests', '__pycache__'}.intersection(path.relative_to(root).parts)]
    if not paths:
        raise ValueError('no Python source files found: %s' % root)
    classes = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        module = ModuleScope(path, tree)
        for name, (node, scope) in module.classes.items():
            key = module.name + '.' + name
            if key in classes:
                raise ValueError('ambiguous class identity %s in %s and %s' % (
                    key, classes[key][0].path, path))
            classes[key] = (module, name, node, scope)

    def definitions(key, seen=frozenset()):
        if key in seen:
            return set()
        module, name, node, scope = classes[key]
        assigned = set(scope.assigned)
        for base in node.bases:
            parent = module.base_name(base, name, classes)
            if parent == 'rclpy.node.Node':
                assigned.update(NODE_API)
            elif parent in classes:
                assigned.update(definitions(parent, seen | {key}))
        return assigned

    problems = []
    for key, (module, name, node, scope) in sorted(classes.items()):
        missing = scope.used - definitions(key)
        if missing:
            problems.append((module.path, name, sorted(missing)))
    return len(paths), problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('src_root', type=Path)
    args = parser.parse_args(argv)
    try:
        scanned, problems = scan(args.src_root)
    except (OSError, SyntaxError, UnicodeError, ValueError) as error:
        print('SCAN ERROR: %s' % error, file=sys.stderr)
        return 2
    for path, name, missing in problems:
        print('MISSING %s %s -> %s' % (path, name, ', '.join('self.' + m for m in missing)))
    print('SCAN COMPLETE: %d files scanned, %d files with problems' % (
        scanned, len({path for path, _, _ in problems})))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
