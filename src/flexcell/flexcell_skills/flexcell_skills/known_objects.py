"""The object set the skills may act on, configured rather than hardcoded.

Adding or removing a same-spec box is a parameter change: every skill validates
against this set, so no control logic has to learn new names.

P1-E: the registry is NODE-SCOPED. Before this, one module-level mutable set was
shared by every server in the process, so two nodes with different
`tracked_objects` parameters overwrote each other and a test could leak state
into the next one. `Registry` is the real thing; the module-level functions are
a thin facade kept for callers that pass no registry (single-skill scripts and
the existing tests), and they delegate to one process-level DEFAULT registry.
"""

import threading

DEFAULT_OBJECTS = ('target_box_a', 'target_box_b')


class Registry:
    """A node-scoped, thread-safe set of addressable object names."""

    def __init__(self, names=None):
        self._lock = threading.Lock()
        self._objects = frozenset(self._normalise(
            DEFAULT_OBJECTS if names is None else names))

    @staticmethod
    def _normalise(names):
        values = [str(name) for name in names if str(name).strip()]
        if not values:
            raise ValueError('the tracked object list cannot be empty')
        return values

    def configure(self, names):
        """Replace the accepted set; called once per server from its parameters."""
        values = frozenset(self._normalise(names))
        with self._lock:
            self._objects = values
        return sorted(values)

    def known(self):
        with self._lock:
            return sorted(self._objects)

    def require(self, name, what='object'):
        with self._lock:
            present = name in self._objects
            known = sorted(self._objects)
        if not present:
            raise ValueError('%s %r is not a configured object; known=%s'
                             % (what, name, known))
        return name

    def __len__(self):
        with self._lock:
            return len(self._objects)


#: process-level registry used by the compatibility facade below
DEFAULT = Registry()


def configure(names):
    """Configure the process-level registry (compatibility facade)."""
    return DEFAULT.configure(names)


def known():
    return DEFAULT.known()


def for_owner(owner):
    """The registry belonging to `owner`, falling back to the process default.

    A node that configured its own registry (P1-E) gets that one; a partially
    built node or a single-skill script keeps the process-level default, so the
    long-standing module-level contract still works.
    """
    registry = getattr(owner, "__dict__", {}).get("_objects")
    return registry if isinstance(registry, Registry) else DEFAULT


def require(name, what='object'):
    return DEFAULT.require(name, what)
