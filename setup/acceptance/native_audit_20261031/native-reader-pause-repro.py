"""Deterministic, read-only reproduction of Follower's sequential-drain risk.

Run from a repository checkout, or pass --source /path/to/native_cycle_window.py:
    py -3 -B native-reader-pause-repro.py --source /path/to/native_cycle_window.py

Only the original Follower class is compiled from its AST. ROS/Gazebo imports
and worker/main are never evaluated. Files are read, never created or changed.
The clock and append-only streams are in-memory doubles. The pause is modeled,
not measured. This proves a possible mechanism, NOT the cause of historical CI.
Startup alignment is out of scope: these doubles begin at complete new records,
as an already aligned follower does during a cycle.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import platform
import sys


class Clock:
    def __init__(self):
        self.now = 1_000_000_000

    def monotonic(self):
        return self.now / 1e9

    def monotonic_ns(self):
        return self.now

    def sleep(self, seconds):
        self.now += int(seconds * 1e9)


class Stream:
    def __init__(self, records, before_first=None):
        self.records = records
        self.position = 0
        self.before_first = before_first

    def tell(self):
        return self.position

    def seek(self, position):
        self.position = position

    def readline(self):
        if self.before_first:
            callback, self.before_first = self.before_first, None
            callback()
        if self.position == len(self.records):
            return ""
        row = self.records[self.position]
        self.position += 1
        return json.dumps(row) + "\n"


def require(ok, reason):
    if not ok:
        raise ValueError("contact evidence: " + reason)


def emit(**record):
    print(json.dumps(record, sort_keys=True))


def load_follower(source, clock):
    text = source.read_text(encoding="utf-8-sig")
    tree = ast.parse(text, filename=str(source))
    cls = next(node for node in tree.body
               if isinstance(node, ast.ClassDef) and node.name == "Follower")
    namespace = dict(json=json, time=clock, require=require)
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(source), "exec"), namespace)
    emit(case="source_identity", source=str(source.resolve()),
         source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
         follower_sha256=hashlib.sha256(ast.get_source_segment(text, cls).encode()).hexdigest(),
         python=sys.version.split()[0], platform=platform.system(),
         mode="original Follower AST; virtual clock; in-memory append-only streams")
    return namespace["Follower"]


def follower_from(Follower, streams, tables=None):
    follower = Follower.__new__(Follower)
    follower.streams = streams
    follower.tables = tables if tables is not None else [{}, {}]
    follower.align_new_record = [False, False]
    return follower


def sequential_drain_pause(Follower, clock):
    physics = [dict(sim_ns=2_000_000, monotonic_ns=clock.now)]
    contacts = [dict(physics[0])]

    def reader_pause_with_healthy_producer():
        # Physics has already reached EOF. While the reader is paused before
        # consuming contact, BOTH modeled sources continue every 2 ms.
        start = clock.now
        for index in range(1, 301):
            row = dict(sim_ns=(index + 1) * 2_000_000,
                       monotonic_ns=start + index * 2_000_000)
            physics.append(row)
            contacts.append(dict(row))
        clock.now += 600_000_000

    follower = follower_from(Follower, [Stream(physics),
                                       Stream(contacts, reader_pause_with_healthy_producer)])
    try:
        follower.wait(lambda p, c: True)
    except ValueError as exc:
        assert "native stream stale; age_ns=600000000" in str(exc), str(exc)
        keys = sorted(follower.tables[0].keys() & follower.tables[1].keys())
        emit(case="sequential_drain_reader_pause", result="REJECTED", error=str(exc),
             producer_rows_per_stream=len(physics), producer_max_gap_ns=2_000_000,
             source_latest_mono=physics[-1]["monotonic_ns"], now=clock.now,
             common_latest_mono=follower.tables[0][keys[-1]]["monotonic_ns"],
             physics_table_latest_mono=follower.tables[0][max(follower.tables[0])]["monotonic_ns"],
             contact_table_latest_mono=follower.tables[1][max(follower.tables[1])]["monotonic_ns"])
    else:
        raise AssertionError("The original stale-stream guard did not reject the old common cohort")

    # Counterfactual inspection only. The failed call above remains REJECTED.
    # This is not an approved retry/catch-up fix or a reclassification of CI.
    keys = follower.collect()
    age = clock.now - follower.tables[0][keys[-1]]["monotonic_ns"]
    assert age == 0, age
    emit(case="counterfactual_second_collect", latest_common_age_ns=age,
         failed_call_remains="REJECTED", proposed_workaround=False)


def earliest_contract(Follower, clock, *, old_eligible, age_ns):
    old = dict(sim_ns=1, monotonic_ns=clock.now - age_ns, eligible=old_eligible)
    fresh = dict(sim_ns=2, monotonic_ns=clock.now, eligible=True)
    follower = follower_from(Follower, [Stream([]), Stream([])],
                             [{1: old, 2: fresh}, {1: dict(old), 2: dict(fresh)}])
    try:
        answer = follower.wait(lambda p, c: p["eligible"], earliest=True)
    except ValueError as exc:
        assert old_eligible and "native candidate stale" in str(exc), str(exc)
        emit(case="earliest_contract", old_eligible=old_eligible, old_age_ns=age_ns,
             result="REJECTED", error=str(exc))
    else:
        assert not old_eligible and answer[0]["sim_ns"] == 2
        emit(case="earliest_contract", old_eligible=old_eligible, old_age_ns=age_ns,
             result="SELECTED", selected_tick=answer[0]["sim_ns"])


def strict_stream_boundary(Follower, clock):
    row = dict(sim_ns=1, monotonic_ns=clock.now - 500_000_000)
    follower = follower_from(Follower, [Stream([]), Stream([])],
                             [{1: row}, {1: dict(row)}])
    try:
        follower.wait(lambda p, c: True)
    except ValueError as exc:
        assert "native stream stale; age_ns=500000000" in str(exc), str(exc)
        emit(case="strict_500ms_stream_boundary", result="REJECTED", error=str(exc))
    else:
        raise AssertionError("Exactly 500 ms must still fail the strict <500 ms guard")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path.cwd() / "scripts/native_cycle_window.py")
    args = parser.parse_args()
    clock = Clock()
    Follower = load_follower(args.source, clock)
    sequential_drain_pause(Follower, clock)
    earliest_contract(Follower, clock, old_eligible=False, age_ns=600_000_000)
    earliest_contract(Follower, clock, old_eligible=True, age_ns=600_000_000)
    earliest_contract(Follower, clock, old_eligible=True, age_ns=500_000_000)
    strict_stream_boundary(Follower, clock)
    emit(status="EXPECTED_MECHANISM_AND_GUARDS_REPRODUCED",
         historical_ci_pause_source="UNKNOWN", files_written=False,
         ros_or_gazebo_started=False, performance_benchmark=False)


if __name__ == "__main__":
    main()
