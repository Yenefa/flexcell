"""The object set the skills may act on, configured rather than hardcoded.

Adding or removing a same-spec box is a parameter change: every skill validates
against this set, so no control logic has to learn new names.
"""

DEFAULT_OBJECTS = ('target_box_a', 'target_box_b')

_objects = set(DEFAULT_OBJECTS)


def configure(names):
    """Replace the accepted set; called once per server from its parameters."""
    global _objects
    values = [str(name) for name in names if str(name).strip()]
    if not values:
        raise ValueError('the tracked object list cannot be empty')
    _objects = set(values)
    return sorted(_objects)


def known():
    return sorted(_objects)


def require(name, what='object'):
    if name not in _objects:
        raise ValueError('%s %r is not a configured object; known=%s'
                         % (what, name, sorted(_objects)))
    return name
