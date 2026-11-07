"""Reconcile must restore lost live camera frames from the bag, never fabricate."""
import importlib.util
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
JOINTS = ["joint1", "joint2", "joint3", "joint4", "gripper_left_joint"]


def reconcile_module():
    path = ROOT / 'scripts/frame_reconcile.py'
    spec = importlib.util.spec_from_file_location('frame_reconcile', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_bag(path, camera_stamps, state_stamps, ref_stamps, cmd):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE topics(id INTEGER PRIMARY KEY, name TEXT, type TEXT, serialization_format TEXT, offered_qos_profiles TEXT)")
    con.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, topic_id INTEGER, timestamp INTEGER, data BLOB)")
    topics = [(1, "/joint_states", "x"), (2, "/arm_controller/controller_state", "x"),
              (3, "/flexcell/execution_command", "x"), (4, "/flexcell/camera/rgb", "x")]
    for row in topics:
        con.execute("INSERT INTO topics VALUES(?,?,?,?,?)", (row[0], row[1], row[2], "cdr", ""))
    ts = 0
    def payload_cam(s): return {'sec': s // 10**9, 'nanosec': s % 10**9, 'w': 640, 'h': 480}
    def payload_state(s): return {"sec": s // 10**9, "nanosec": s % 10**9, "name": JOINTS, "position": [0.1, 0.2, 0.3, 0.4, 0.02]}
    def payload_ref(s): return {"sec": s // 10**9, "nanosec": s % 10**9, "joint_names": JOINTS[:4], "positions": [0.11, 0.21, 0.31, 0.41]}
    for s in state_stamps:
        ts += 1; con.execute("INSERT INTO messages VALUES(?,?,?,?)", (ts, 1, s, json.dumps(payload_state(s)).encode()))
    for s in ref_stamps:
        ts += 1; con.execute("INSERT INTO messages VALUES(?,?,?,?)", (ts, 2, s, json.dumps(payload_ref(s)).encode()))
    ts += 1; con.execute("INSERT INTO messages VALUES(?,?,?,?)", (ts, 3, 0, json.dumps({"raw": json.dumps(cmd)}).encode()))
    for s in camera_stamps:
        ts += 1; con.execute("INSERT INTO messages VALUES(?,?,?,?)", (ts, 4, s, json.dumps(payload_cam(s)).encode()))
    con.commit(); con.close()


def fake_deserialize(name, data):
    payload = json.loads(bytes(data))
    if name == "/flexcell/camera/rgb":
        return SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=payload["sec"], nanosec=payload["nanosec"])),
                               encoding="rgb8", width=payload["w"], height=payload["h"], step=payload["w"] * 3, data=b"")
    if name == "/joint_states":
        return SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=payload["sec"], nanosec=payload["nanosec"])),
                               name=payload["name"], position=payload["position"])
    if name == "/arm_controller/controller_state":
        return SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=payload["sec"], nanosec=payload["nanosec"])),
                               joint_names=payload["joint_names"], reference=SimpleNamespace(positions=payload["positions"]))
    return SimpleNamespace(data=payload["raw"])


def fake_write_png(path, msg):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PNG")


def prepare(tmp_path, stamps_present, camera_stamps, state_stamps, ref_stamps, cmd):
    out = tmp_path / "run"
    (out / "images").mkdir(parents=True)
    rows = []
    for i, s in enumerate(stamps_present):
        rows.append(dict(frame_index=i, sim_ns=s, monotonic_ns=1_000_000_000 + 145_000_000 * i,
                         image="images/%06d.png" % i, valid=True, reasons=[]))
    (out / "frames.jsonl").write_text("".join(json.dumps(r) + chr(10) for r in rows))
    (out / "raw").mkdir()
    make_bag(out / "raw" / "raw_0.db3", camera_stamps, state_stamps, ref_stamps, cmd)
    return out


def test_missing_live_frame_is_backfilled_from_bag(tmp_path):
    stamps = [0, 100_000_000, 300_000_000]
    out = prepare(tmp_path, stamps, [0, 100_000_000, 200_000_000, 300_000_000],
                  [0, 100_000_000, 200_000_000, 300_000_000], [0, 100_000_000, 200_000_000, 300_000_000],
                  {"kind": "gripper_position_target", "accepted": True, "position": 0.02, "sim_ns": 0})
    mod = reconcile_module()
    res = mod.reconcile_run(out, out / "raw", deserialize=fake_deserialize, write_png=fake_write_png, joints=JOINTS)
    assert res["status"] == "RECONCILED" and res["backfilled"] == 1
    rows = [json.loads(l) for l in (out / "frames.jsonl").read_text().splitlines()]
    assert [r["sim_ns"] for r in rows] == [0, 100_000_000, 200_000_000, 300_000_000]
    bf = [r for r in rows if r.get("backfilled_from_bag")][0]
    assert bf["valid"] is True and bf["observation.state"][:4] == [0.1, 0.2, 0.3, 0.4]
    assert bf["action"][4] == 0.02 and bf["monotonic_ns_source"] == "interpolated"
    assert (out / bf["image"]).is_file()
    assert bf["sim_ns"] == 200_000_000 and 1_217_500_000 - 5 < bf["monotonic_ns"] < 1_217_500_000 + 5


def test_no_gap_is_complete_and_untouched(tmp_path):
    stamps = [0, 100_000_000, 200_000_000]
    out = prepare(tmp_path, stamps, stamps, stamps, stamps,
                  {"kind": "gripper_position_target", "accepted": True, "position": 0.02, "sim_ns": 0})
    before = (out / "frames.jsonl").read_text()
    mod = reconcile_module()
    res = mod.reconcile_run(out, out / "raw", deserialize=fake_deserialize, write_png=fake_write_png, joints=JOINTS)
    assert res["status"] == "COMPLETE" and res["backfilled"] == 0
    assert (out / "frames.jsonl").read_text() == before


def test_backfilled_frame_without_aligned_state_is_invalid_not_dropped(tmp_path):
    stamps = [0, 100_000_000, 300_000_000]
    out = prepare(tmp_path, stamps, [0, 100_000_000, 200_000_000, 300_000_000],
                  [0, 300_000_000], [0, 300_000_000],
                  {"kind": "gripper_position_target", "accepted": True, "position": 0.02, "sim_ns": 0})
    mod = reconcile_module()
    res = mod.reconcile_run(out, out / "raw", deserialize=fake_deserialize, write_png=fake_write_png, joints=JOINTS)
    assert res["status"] == "RECONCILED" and res["backfilled_invalid"] == 1
    rows = [json.loads(l) for l in (out / "frames.jsonl").read_text().splitlines()]
    bf = [r for r in rows if r.get("backfilled_from_bag")][0]
    assert bf["valid"] is False and any("missing_or_stale" in x for x in bf["reasons"])


def test_bag_frames_outside_live_coverage_are_not_backfilled(tmp_path):
    stamps = [100_000_000, 200_000_000, 300_000_000]
    out = prepare(tmp_path, stamps, [0, 100_000_000, 200_000_000, 300_000_000, 400_000_000],
                  [0, 100_000_000, 200_000_000, 300_000_000, 400_000_000],
                  [0, 100_000_000, 200_000_000, 300_000_000, 400_000_000],
                  {"kind": "gripper_position_target", "accepted": True, "position": 0.02, "sim_ns": 0})
    before = (out / "frames.jsonl").read_text()
    mod = reconcile_module()
    res = mod.reconcile_run(out, out / "raw", deserialize=fake_deserialize, write_png=fake_write_png, joints=JOINTS)
    assert res["status"] == "COMPLETE" and res["backfilled"] == 0
    assert (out / "frames.jsonl").read_text() == before


def test_split_bag_files_are_combined(tmp_path):
    out = tmp_path / "run"
    (out / "images").mkdir(parents=True)
    rows = [dict(frame_index=i, sim_ns=s, monotonic_ns=1_000_000_000 + 145_000_000 * i,
                 image="images/%06d.png" % i, valid=True, reasons=[])
            for i, s in enumerate([0, 100_000_000, 300_000_000])]
    (out / "frames.jsonl").write_text("".join(json.dumps(r) + chr(10) for r in rows))
    raw = out / "raw"
    raw.mkdir()
    make_bag(raw / "raw_0.db3", [0, 100_000_000], [0, 100_000_000], [0, 100_000_000],
             {"kind": "gripper_position_target", "accepted": True, "position": 0.02, "sim_ns": 0})
    make_bag(raw / "raw_1.db3", [200_000_000, 300_000_000], [200_000_000, 300_000_000],
             [200_000_000, 300_000_000],
             {"kind": "gripper_position_target", "accepted": True, "position": 0.02, "sim_ns": 0})
    mod = reconcile_module()
    res = mod.reconcile_run(out, raw, deserialize=fake_deserialize, write_png=fake_write_png, joints=JOINTS)
    assert res["status"] == "RECONCILED" and res["backfilled"] == 1
    got = [json.loads(l)["sim_ns"] for l in (out / "frames.jsonl").read_text().splitlines()]
    assert got == [0, 100_000_000, 200_000_000, 300_000_000]
