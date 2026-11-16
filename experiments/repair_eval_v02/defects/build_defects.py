"""Build the two pre-registered defect instances as reproducible artifacts.

TASKS.md pre-registered DEF-F1-REG and DEF-F2-MAP but left their realization to
#252: an override file with its sha256, and a patch with its sha256 and the list
of affected files. Until those exist the manifest's slots cannot be run against
the defect the protocol actually names, and running them against a stand-in -
which is what the synthetic fixtures in dry_run_matrix.py are - would mean
filling pre-registered rows with a different experiment.

This script derives both artifacts from the repository's own files so the
digests are reproducible rather than typed.
"""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONFIG = ROOT / "src" / "flexcell" / "flexcell_skills" / "config" / "week1.yaml"
FSM = ROOT / "src" / "flexcell" / "flexcell_skills" / "flexcell_skills" / "task_fsm_server.py"

F1_DIR = HERE / "DEF-F1-REG"
F2_DIR = HERE / "DEF-F2-MAP"

WRONG_ASSIGNMENT = "((self._obj_a, 'zone_2'), (self._obj_b, 'zone_1'))"
RIGHT_ASSIGNMENT = "((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_f1():
    """Config injection: the perception service registers no objects.

    TASKS.md says the repair surface for F1 is configuration, so the injection is
    a configuration file, not a source edit.

    The first version of this function DELETED the tracked_objects key, on the
    reasoning that a missing registry is the defect. That reasoning was wrong and
    it would have produced a run with no defect in it at all: observe_server
    declares

        declare_parameter('tracked_objects', ['target_box_a', 'target_box_b'])

    so removing the key makes the node fall back to its default, which tracks
    both objects. The candidates would have been handed a healthy system labelled
    broken, and every condition would have looked equally capable.

    An explicitly empty list does not work either, and that was measured rather
    than assumed. All three of these were run against the built node on
    2026-11-16:

        params file with tracked_objects: []            -> ParameterUninitializedException
        --ros-args -p "tracked_objects:=[]"             -> ParameterUninitializedException
        --ros-args -p "tracked_objects:=['ghost_object']" -> starts, logs tracked=['ghost_object']

    An empty YAML list is not a typed rclpy parameter override, so it leaves the
    parameter uninitialised and the node dies at startup. A node that dies is a
    different mechanism from a node that runs without any usable registry, and
    the difference is visible to the repairer.

    So the injection registers an object the world does not contain. The declared
    mechanism in TASKS.md ("registry missing") is not expressible through this
    parameter, and RUN_MANIFEST records that deviation instead of letting the
    artifact quietly stand in for it.
    """
    source = CONFIG.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    hits = [i for i, l in enumerate(lines) if l.lstrip().startswith("tracked_objects:")]
    assert len(hits) == 1, "expected exactly one tracked_objects line"
    i = hits[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    # a name that does not exist in the world: the registry is populated, but
    # with nothing the perception layer can ever observe
    lines[i] = indent + "tracked_objects: ['ghost_object']" + chr(10)
    override = "".join(lines)
    assert override != source, "override did not change anything"
    F1_DIR.mkdir(parents=True, exist_ok=True)
    (F1_DIR / "override.yaml").write_text(override, encoding="utf-8")
    (F1_DIR / "manifest.json").write_text(json.dumps({
        "defect_id": "DEF-F1-REG",
        "family": "F1_OBJECT_REGISTRATION",
        "repair_surface": "configuration",
        "injection_point": str(CONFIG.relative_to(ROOT)),
        "mechanism": "no real object is registered -> the perception layer publishes "
                     "no B for the demo objects -> the task layer cannot fetch B",
        "declared_mechanism_deviation":
            "TASKS.md says 'registry missing'. Measured 2026-11-16: an empty "
            "tracked_objects list (params file or CLI) raises "
            "ParameterUninitializedException, so the node dies instead of running "
            "without a registry. The realization therefore registers a name the "
            "world does not contain, which leaves the node running and no real "
            "object observed. The difference is visible to the repairer and is "
            "recorded rather than glossed.",
        "artifact": "override.yaml",
        "artifact_sha256": sha(override),
        "pristine_sha256": sha(source),
        "affected_files": [str(CONFIG.relative_to(ROOT))],
        "expected_observable": "observe_server has an empty tracked list, so no "
                               "object state is published for the demo objects",
        "pinned_by": ["src/flexcell/flexcell_skills/test/test_level_release_profile.py:76",
                      "src/flexcell/flexcell_skills/test/test_three_object_scene.py:30"],
    }, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")


def build_f2():
    """Source injection: the demo assignment maps objects to the wrong zones."""
    source = FSM.read_text(encoding="utf-8")
    assert source.count(RIGHT_ASSIGNMENT) == 1, "expected exactly one demo assignment"
    injured = source.replace(RIGHT_ASSIGNMENT, WRONG_ASSIGNMENT)
    diff = "".join(difflib.unified_diff(
        source.splitlines(keepends=True), injured.splitlines(keepends=True),
        fromfile="a/" + str(FSM.relative_to(ROOT)),
        tofile="b/" + str(FSM.relative_to(ROOT))))
    F2_DIR.mkdir(parents=True, exist_ok=True)
    (F2_DIR / "inject.patch").write_text(diff, encoding="utf-8")
    (F2_DIR / "manifest.json").write_text(json.dumps({
        "defect_id": "DEF-F2-MAP",
        "family": "F2_GOAL_MAPPING",
        "repair_surface": "source",
        "injection_point": str(FSM.relative_to(ROOT)),
        "mechanism": "the mapping source resolves an object to the wrong zone -> "
                     "PLACE_B fails or lands in the wrong zone",
        "artifact": "inject.patch",
        "artifact_sha256": sha(diff),
        "pristine_sha256": sha(source),
        "affected_files": [str(FSM.relative_to(ROOT))],
        "expected_observable": "the demo assignment pairs target_box_a with zone_2",
        "verified_how": "test_defects.py extracts the demo assignment from the patched "
                        "source, resolves it with the node's declared object_a/object_b "
                        "defaults, and hands it to the repository's own FSMPolicy: the "
                        "plan order is unchanged and each object is assigned the other "
                        "zone. Decision.target carries only the object id, so the zone "
                        "is checked where it lives - in the assignments the executor "
                        "reads.",
        "pinned_by": [],
        "not_used": "a wrong zone coordinate in configuration is a different "
                    "mechanism and is explicitly excluded by TASKS.md 2.3",
    }, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")


if __name__ == "__main__":
    build_f1()
    build_f2()
    print("DEF-F1-REG override sha256:", json.loads((F1_DIR / "manifest.json").read_text())["artifact_sha256"])
    print("DEF-F2-MAP  patch    sha256:", json.loads((F2_DIR / "manifest.json").read_text())["artifact_sha256"])
