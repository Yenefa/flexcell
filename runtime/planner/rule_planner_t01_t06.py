#!/usr/bin/env python3
"""Baseline A-prime rules for the T01-T06 family: written AFTER seeing the templates.

WHY THIS IS LEGITIMATE AND WHY IT MUST BE LABELLED
  Writing rules after reading the six instructions makes full coverage almost inevitable, so a high
  score here proves nothing about generalisation. What it DOES prove is what the mission asks for:
  whether a deterministic parser matches the LLM on these templates. If it does, the LLM's
  measurable value on T01-T06 is zero, and any agent advantage must be shown where rules fail.
  Reporting this as agent capability would be fraud; reporting it as a saturation measurement is
  the only honest use.

WHAT IT READS: instruction, visible objects, measured zone positions. NOT expected_goal, NOT
constraints, NOT template_id, NOT the seed. Left/right is resolved from measured y, so the parser
derives direction the same way the robot must.

WHAT IT CANNOT DO: anything whose shape it has not been shown. That limitation is the point.
"""
import math
import re


def _zones_by_side(zones):
    left = max(zones, key=lambda z: z['position'][1])
    right = min(zones, key=lambda z: z['position'][1])
    return {'left': left['name'], 'right': right['name']}


def _by_colour(objects):
    return {str(o.get('color', '')).lower(): o['name'] for o in objects}


RE_T01 = r'put the (\w+) block in the (left|right) bin and the (\w+) block in the (left|right) bin'
RE_T02 = r'clear the table into the (left|right) bin, except the (\w+) block, which must stay put'
RE_T03 = r'move blocks into the (left|right) bin in this order:\s*the (\w+),\s*then the (\w+)'
RE_T04 = r'put the block that is further from the robot base into the (left|right) bin, and the nearer block into the (left|right) bin'
RE_T05 = r'move the (\w+) block to the (left|right) bin, passing through the (left|right) bin first'
RE_T06 = r'put the (\w+) block in the (left|right) bin, then move it on to the (left|right) bin'


def plan(observation):
    text = str(observation.get('instruction') or '')
    objects = observation.get('objects') or []
    zones = observation.get('zones') or []
    if not objects or not zones:
        return [], [], 'no scene'
    side = _zones_by_side(zones)
    colour = _by_colour(objects)

    m = re.search(RE_T01, text, re.I)
    if m:
        c1, s1, c2, s2 = (m.group(1).lower(), m.group(2).lower(),
                          m.group(3).lower(), m.group(4).lower())
        if c1 in colour and c2 in colour:
            return ([{'object': colour[c1], 'zone': side[s1], 'why': 'T01 clause 1'},
                     {'object': colour[c2], 'zone': side[s2], 'why': 'T01 clause 2'}],
                    [], 'T01 parsed')

    m = re.search(RE_T02, text, re.I)
    if m:
        keep = colour.get(m.group(2).lower())
        target = side[m.group(1).lower()]
        moves = [{'object': o['name'], 'zone': target, 'why': 'T02 clear'}
                 for o in objects if o['name'] != keep]
        if keep and moves:
            return moves, [keep], 'T02 parsed'

    m = re.search(RE_T03, text, re.I)
    if m:
        target = side[m.group(1).lower()]
        a, b = colour.get(m.group(2).lower()), colour.get(m.group(3).lower())
        if a and b:
            return ([{'object': a, 'zone': target, 'why': 'T03 first'},
                     {'object': b, 'zone': target, 'why': 'T03 second'}], [], 'T03 parsed')

    m = re.search(RE_T04, text, re.I)
    if m:
        if len(objects) < 2:
            return [], [], 'T04 needs two blocks'
        far = max(objects, key=lambda o: math.hypot(o['position'][0], o['position'][1]))
        near = min(objects, key=lambda o: math.hypot(o['position'][0], o['position'][1]))
        return ([{'object': far['name'], 'zone': side[m.group(1).lower()],
                  'why': 'T04 further, measured'},
                 {'object': near['name'], 'zone': side[m.group(2).lower()],
                  'why': 'T04 nearer, measured'}], [], 'T04 parsed')

    m = re.search(RE_T05, text, re.I)
    if m:
        name = colour.get(m.group(1).lower())
        final, relay = side[m.group(2).lower()], side[m.group(3).lower()]
        if name:
            rest = [o['name'] for o in objects if o['name'] != name]
            return ([{'object': name, 'zone': relay, 'why': 'T05 relay hop'},
                     {'object': name, 'zone': final, 'why': 'T05 final hop'}],
                    rest, 'T05 parsed')

    m = re.search(RE_T06, text, re.I)
    if m:
        name = colour.get(m.group(1).lower())
        first, second = side[m.group(2).lower()], side[m.group(3).lower()]
        if name:
            rest = [o['name'] for o in objects if o['name'] != name]
            return ([{'object': name, 'zone': first, 'why': 'T06 first landing'},
                     {'object': name, 'zone': second, 'why': 'T06 second landing'}],
                    rest, 'T06 parsed')

    return [], [], 'no rule matched - declined'