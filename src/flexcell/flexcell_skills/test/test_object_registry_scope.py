"""P1-E: the addressable object set is node-scoped, not process-global."""
import threading
import unittest

from flexcell_skills import known_objects


class TestRegistryScope(unittest.TestCase):

    def test_two_registries_do_not_pollute_each_other(self):
        a = known_objects.Registry(["box_a"])
        b = known_objects.Registry(["box_b"])
        self.assertEqual(a.known(), ["box_a"])
        self.assertEqual(b.known(), ["box_b"])
        a.configure(["box_c"])
        self.assertEqual(a.known(), ["box_c"])
        self.assertEqual(b.known(), ["box_b"])

    def test_a_registry_starts_from_the_default_set(self):
        registry = known_objects.Registry()
        self.assertEqual(registry.known(), sorted(known_objects.DEFAULT_OBJECTS))

    def test_an_empty_list_is_refused_and_leaves_the_set_intact(self):
        registry = known_objects.Registry(["box_a"])
        with self.assertRaises(ValueError):
            registry.configure([])
        self.assertEqual(registry.known(), ["box_a"])

    def test_require_is_registry_local(self):
        a = known_objects.Registry(["box_a"])
        b = known_objects.Registry(["box_b"])
        self.assertEqual(a.require("box_a"), "box_a")
        with self.assertRaises(ValueError):
            a.require("box_b")
        with self.assertRaises(ValueError):
            b.require("box_a")

    def test_for_owner_prefers_the_node_registry(self):
        class Node:
            pass
        node = Node()
        node._objects = known_objects.Registry(["only_here"])
        self.assertIs(known_objects.for_owner(node), node._objects)
        self.assertEqual(known_objects.for_owner(node).known(), ["only_here"])

    def test_for_owner_falls_back_to_the_process_default(self):
        class Partial:
            pass
        self.assertIs(known_objects.for_owner(Partial()), known_objects.DEFAULT)

    def test_concurrent_configuration_never_corrupts_the_set(self):
        registry = known_objects.Registry(["seed"])
        errors = []

        def worker(index):
            try:
                for _ in range(50):
                    registry.configure(["box_%d" % index])
                    snapshot = registry.known()
                    if len(snapshot) != 1:
                        errors.append(snapshot)
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(registry.known()), 1)


if __name__ == "__main__":
    unittest.main()
