#!/usr/bin/env python3
"""Static audit: find self._X attributes that are used but never assigned.

Catches the `self._gate` class of landmine (used-but-undefined node attribute
that crashes at runtime and, via rclpy's default-result fallback, masquerades
as action SUCCESS). Pure AST, no ROS imports.

Usage: python 82_undefined_attr_check.py <src_root>
"""
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1])
problems = []
scanned = 0
NODE_API = {
    'create_publisher', 'create_subscription', 'create_client', 'create_timer',
    'declare_parameter', 'get_parameter', 'get_parameters', 'get_logger',
    'get_clock', 'get_name', 'destroy_node', 'set_parameters',
    'count_subscribers', 'count_publishers', 'resolve_topic_name',
    'destroy_publisher', 'destroy_subscription', 'destroy_client',
    'destroy_service', 'destroy_timer',
}
for py in sorted(root.rglob('*.py')):
    if 'test' in py.parts:
        continue
    scanned += 1
    tree = ast.parse(py.read_text(encoding='utf-8'), filename=str(py))
    assigned, used = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assigned.add(node.name)
        elif (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == 'self'):
            if isinstance(node.ctx, ast.Store):
                assigned.add(node.attr)
            else:  # Load / Del
                used.add(node.attr)
    missing = (used - assigned) - NODE_API
    if missing:
        problems.append((str(py), sorted(missing)))

for path, missing in problems:
    print('MISSING %s -> %s' % (path, ', '.join('self.' + m for m in missing)))
print('SCAN COMPLETE: %d files scanned, %d files with problems' % (scanned, len(problems)))
