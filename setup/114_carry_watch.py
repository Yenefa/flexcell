#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Describe vertical patterns in recorded Gazebo poses; never grants admission.

SAWTOOTH: observed oscillation resembles the supplied pin period.
CONSTANT_OFFSET: low variation of vertical offset in the selected hold window.
NO_CARRY: no sufficiently long observed lift.
INDETERMINATE: insufficient hold or another shape.

Requires actual finite source timestamps and target poses. No invented clock,
interpolation, root-cause claim, full SE(3) judgment or deployment eligibility.
Exit 0 means analysis completed, 2 means unusable input. See docs/CARRY_WATCH.md.
"""

import argparse
import gzip
import json
import os
import statistics
import subprocess
import sys
import math

# --------------------------------------------------------------------------- #
# 默认参数
# --------------------------------------------------------------------------- #

WORLD_DEFAULT = "empty"          # Gazebo 世界名（不是 flexcell_world）
TOPIC_TMPL = "/world/{world}/dynamic_pose/info"

BOX_DEFAULT = "target_box_a"
GRIPPERS_DEFAULT = ["gripper_left_link", "gripper_right_link"]

GRIP_THR_DEFAULT = 0.15           # m，夹爪 z 超过它才算"抬到位"
LIFT_MARGIN_DEFAULT = 0.005       # m，箱子 z 高出静止高度多少才算"被带起来了"
GAP_DEFAULT = 3                   # 帧，抬升 mask 中断几帧以内算同一段
MIN_FRAMES_DEFAULT = 10           # 帧，短于此的抬升段丢弃
HOLD_SPEED_DEFAULT = 0.05         # m/s，夹爪速度低于它算"保持段"（振荡分析窗口）

PERIOD_DEFAULT = 0.100            # s，期望的 pin 周期
PERIOD_TOL_DEFAULT = 0.030        # s，周期容差 -> SAWTOOTH 需落在 [0.070, 0.130]
PP_THR_DEFAULT = 0.030            # m，单周期峰峰超过 30 mm 才算锯齿
OFFSET_TOL_DEFAULT = 0.005        # m，delta 变化小于 5 mm 才算稳定跟随
MIN_CYCLES_DEFAULT = 3            # 个，局部极小少于 3 个不谈周期

N_DEFAULT = 9000                  # --follow 时向 gz 要的帧数


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #

def _f(v, default=0.0):
    """Omitted proto3 fields are zero; malformed/nonfinite values are unusable."""
    try:
        value = float(v)
    except (TypeError, ValueError):
        raise ValueError('invalid numeric pose/stamp') from None
    if not math.isfinite(value):
        raise ValueError('nonfinite numeric pose/stamp')
    return value


def frame_time(rec):
    """header.stamp -> 秒。没有整个 stamp 返回 None，后续拒绝。"""
    header = rec.get("header") or {}
    if not isinstance(header, dict):
        raise ValueError('invalid header')
    stamp = header.get("stamp")
    if not isinstance(stamp, dict):
        return None
    return _f(stamp.get("sec", 0)) + _f(stamp.get("nsec", 0)) * 1e-9


def extract(rec, box_name, grip_names):
    """一帧 gz 位姿 -> (t, box_z, grip_z)。没见到的模型返回 None。

    grip_z 取左右指的均值；只见到一指就用一指。
    """
    if not isinstance(rec, dict):
        raise ValueError('pose frame must be an object')
    t = frame_time(rec)
    box_z = None
    grip_vals = []
    for p in rec.get("pose") or []:
        if not isinstance(p, dict):
            raise ValueError('invalid pose entry')
        name = p.get("name", "")
        pos = p.get("position") or {}
        if not isinstance(pos, dict):
            raise ValueError('invalid pose position')
        z = _f(pos.get("z", 0.0))
        if name == box_name:
            box_z = z
        elif name in grip_names:
            grip_vals.append(z)
    grip_z = (sum(grip_vals) / len(grip_vals)) if grip_vals else None
    if grip_z is not None and not math.isfinite(grip_z):
        raise ValueError('nonfinite combined gripper pose')
    return t, box_z, grip_z


def open_text(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "rt", encoding="utf-8", errors="replace")


def load_frames_from_file(path, box_name, grip_names):
    """离线：读 .jsonl / .jsonl.gz。返回 (frames, meta)。

    frames 里每项 {'t','box','grip'}，t 必须来自实际时间戳。
    """
    if not os.path.exists(path):
        raise IOError("找不到输入文件: %s" % path)
    frames = []
    seen_box = seen_grip = False
    bad = 0
    with open_text(path) as fh:
        for idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                raise ValueError('invalid JSON at line %d' % (idx + 1)) from None
            t, box_z, grip_z = extract(rec, box_name, grip_names)
            if box_z is not None:
                seen_box = True
            if grip_z is not None:
                seen_grip = True
            frames.append({"t": t, "box": box_z, "grip": grip_z, "i": idx})
    meta = {"path": path, "lines": len(frames), "bad_lines": bad,
            "seen_box": seen_box, "seen_grip": seen_grip}
    return frames, meta


# --------------------------------------------------------------------------- #
# 在线
# --------------------------------------------------------------------------- #

def follow(topic, n, box_name, grip_names, on_frame=None):
    """在线：起 gz topic 子进程，边读边回调。返回 frames。"""
    cmd = ["gz", "topic", "-e", "-t", topic, "-n", str(n), "--json-output"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1)
    except OSError as exc:
        raise IOError("起不了 `gz topic`（%s）。gz 在 PATH 上吗？ROS/Gazebo 环境 source 了吗？" % exc)

    frames = []
    try:
        for idx, line in enumerate(proc.stdout):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                raise ValueError('invalid live pose JSON') from None
            t, box_z, grip_z = extract(rec, box_name, grip_names)
            row = {"t": t, "box": box_z, "grip": grip_z, "i": idx}
            frames.append(row)
            if on_frame is not None:
                on_frame(row)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            proc.terminate()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except OSError:
                pass
    return frames


# --------------------------------------------------------------------------- #
# 分析
# --------------------------------------------------------------------------- #

def finish_times(frames):
    """Require actual increasing timestamps; never invent a 50 Hz clock."""
    out = [fr['t'] for fr in frames]
    if any(t is None or not math.isfinite(t) for t in out):
        raise ValueError('missing or nonfinite source timestamp')
    if any(b <= a for a, b in zip(out, out[1:])):
        raise ValueError('source timestamps are not strictly increasing')
    return out


def rest_height(frames):
    """箱子静止高度：整段里箱子 z 的中位数。

    大部分帧箱子都躺在桌上，所以中位数就是静止高度（35 mm 立方体 -> 0.0175 m）。
    """
    vals = [fr["box"] for fr in frames if fr["box"] is not None]
    return statistics.median(vals) if vals else 0.0


def lift_segments(frames, times, grip_thr, rest, margin, gap, min_frames):
    """抬升段 = 夹爪 z > grip_thr 且 箱子 z > rest + margin 的连续帧。

    中断不超过 gap 帧的合并成一段（锯齿的波谷会短暂掉到 margin 以下）。
    """
    keep = []
    for fr in frames:
        ok = (fr["grip"] is not None and fr["box"] is not None
              and fr["grip"] > grip_thr and (fr["box"] - rest) > margin)
        keep.append(ok)
    runs, start = [], None
    for i, ok in enumerate(keep):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            runs.append([start, i])
            start = None
    if start is not None:
        runs.append([start, len(keep)])
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] <= gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [m for m in merged if (m[1] - m[0]) >= min_frames]


def hold_window(frames, times, a, b, hold_speed):
    """在抬升段 [a,b) 里找最长的"夹爪几乎不动"的连续子段。

    为什么要这一步：抬升段的头尾夹爪本身在 commanded motion，delta 里混了指令运动，
    会稀释振荡幅度。真正的"保持段"里夹爪不动，delta 的变化就纯粹是箱子的振荡。
    """
    best = (None, None)
    i = a + 1
    while i < b:
        dt = times[i] - times[i - 1]
        if dt > 0 and abs(frames[i]["grip"] - frames[i - 1]["grip"]) / dt < hold_speed:
            j = i
            while j < b:
                dtj = times[j] - times[j - 1]
                if dtj <= 0 or abs(frames[j]["grip"] - frames[j - 1]["grip"]) / dtj >= hold_speed:
                    break
                j += 1
            if best[0] is None or (j - (i - 1)) > (best[1] - best[0]):
                best = (i - 1, j)
            i = j
        else:
            i += 1
    return best


def extrema(vals):
    """局部极小 / 极大（delta 序列）。相等值不重复计数。"""
    mins = [i for i in range(1, len(vals) - 1)
            if vals[i] < vals[i - 1] and vals[i] <= vals[i + 1]]
    maxs = [i for i in range(1, len(vals) - 1)
            if vals[i] > vals[i - 1] and vals[i] >= vals[i + 1]]
    return mins, maxs


def analyze_window(frames, times, a, b, kind):
    """在窗口 [a,b) 上算 delta 统计 + 周期 + 单周期峰峰。"""
    ts = times[a:b]
    delta = [frames[i]["grip"] - frames[i]["box"] for i in range(a, b)]

    mins, maxs = extrema(delta)
    period = None
    if len(mins) >= 2:
        period = statistics.mean(ts[mins[k + 1]] - ts[mins[k]]
                                 for k in range(len(mins) - 1))

    # 单周期峰峰：每个局部极小 -> 紧随其后的局部极大，取这些摆幅的均值。
    # 这是"一个 pin 周期里箱子掉下去多远"的直接度量（报告里叫"单周期回落"）。
    marks = sorted([(i, 0) for i in mins] + [(i, 1) for i in maxs])
    swings = [delta[marks[k + 1][0]] - delta[marks[k][0]]
              for k in range(len(marks) - 1)
              if marks[k][1] == 0 and marks[k + 1][1] == 1]
    cycle_pp = statistics.mean(swings) if swings else None

    dur = ts[-1] - ts[0] if len(ts) >= 2 else 0.0
    rate = (len(ts) - 1) / dur if dur > 0 else 0.0
    return {
        "window_kind": kind,
        "start_index": a,
        "end_index": b,
        "t0": ts[0] if ts else None,
        "t1": ts[-1] if ts else None,
        "duration_s": dur,
        "frames": len(ts),
        "sample_rate_hz": rate,
        "delta_min_m": min(delta) if delta else None,
        "delta_max_m": max(delta) if delta else None,
        "delta_mean_m": statistics.mean(delta) if delta else None,
        "delta_pp_m": (max(delta) - min(delta)) if delta else None,
        "local_minima": len(mins),
        "local_maxima": len(maxs),
        "mean_period_s": period,
        "cycle_pp_m": cycle_pp,
        "cycle_pp_n": len(swings),
    }


def judge(an, cfg, ctx):
    """判定 + 一句人话理由。an 为 None 表示没有抬升段。"""
    if an is None:
        # 说清是"夹爪没抬"还是"箱子没起来"——这两件事的修法完全不同。
        if ctx["grip_max"] <= cfg.grip_thr:
            return "NO_CARRY", ("没有抬升段：夹爪 z 全程最高 %.4f m，从未超过阈值 %.3f m。"
                                "（是不是录错了段，或夹爪根本没动？阈值用 --grip-thr 调。）"
                                % (ctx["grip_max"], cfg.grip_thr))
        if ctx["box_rise"] <= cfg.lift_margin:
            return "NO_CARRY", ("没有抬升段：夹爪抬到了 %.4f m，但箱子 z 最高只到 %.4f m，"
                                "仅比静止高度 %.4f m 高 %.1f mm（< %.1f mm）——箱子没被带起来。"
                                % (ctx["grip_max"], ctx["box_max"], ctx["rest"],
                                   ctx["box_rise"] * 1000.0, cfg.lift_margin * 1000.0))
        return "NO_CARRY", ("夹爪和箱子都动了，但没有不短于 %d 帧的连续抬升段"
                            "（--min-frames / --gap 可调）。" % cfg.min_frames)

    n_min = an["local_minima"]
    per = an["mean_period_s"]
    cpp = an["cycle_pp_m"]
    dpp = an["delta_pp_m"] or 0.0

    if an['window_kind'] != 'hold':
        return 'INDETERMINATE', '未观察到足够长的静止保持段；运动中的垂直变化不能用于机制判定。'

    if n_min >= cfg.min_cycles and per is not None and cpp is not None:
        if abs(per - cfg.period) <= cfg.period_tol and cpp > cfg.pp_thr:
            return "SAWTOOTH", (
                "delta 有 %d 个局部极小，平均周期 %.4f s（pin 周期 %.3f s ±%.3f），"
                "单周期峰峰 %.1f mm > %.1f mm：与 %.3f s pin 周期相符的垂直振荡；机制未确认。"
                % (n_min, per, cfg.period, cfg.period_tol,
                   cpp * 1000.0, cfg.pp_thr * 1000.0, cfg.period))

    if dpp < cfg.offset_tol:
        return "CONSTANT_OFFSET", (
            "本保持段垂直偏移只变化 %.1f mm (< %.1f mm)；不构成完整 SE(3) 或抓持准入证明。"
            % (dpp * 1000.0, cfg.offset_tol * 1000.0))

    extra = ""
    if n_min >= cfg.min_cycles and per is not None:
        extra = ("周期 %.4f s 与 %.3f s 差 %.4f s，超出 ±%.3f s；"
                 % (per, cfg.period, abs(per - cfg.period), cfg.period_tol))
    return "INDETERMINATE", (
        "%sdelta 峰峰 %.1f mm 超过 %.1f mm 且不符合 pin 周期；不能仅凭此确认原因。"
        % (extra, dpp * 1000.0, cfg.offset_tol * 1000.0))


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #

def _m(v, nd=4):
    return "n/a" if v is None else ("%.*f" % (nd, v))


def human_report(res):
    L = []
    src = res["source"]
    an = res["analysis"]
    L.append("=== carry watch ===")
    L.append("来源        : %s" % src["desc"])
    L.append("模型        : box=%s  gripper=%s" % (res["models"]["box"],
                                                   "+".join(res["models"]["grippers"])))
    L.append("总帧数      : %d   静止高度 box_z=%.4f m" % (res["frames_total"], res["rest_box_z"]))
    L.append("抬升段      : %d 段" % len(res["lift_segments"]))
    for s in res["lift_segments"]:
        tag = " <== 取这段" if s.get("primary") else ""
        L.append("   [%5d,%5d)  %3d 帧  %.3f s  t=[%.3f, %.3f]%s"
                 % (s["start_index"], s["end_index"], s["frames"],
                    s["duration_s"], s["t0"], s["t1"], tag))
    if an is None:
        L.append("")
        L.append("判定        : %s" % res["verdict"])
        L.append("理由        : %s" % res["reason"])
        return "\n".join(L)

    L.append("")
    L.append("分析窗口    : %s  [%d, %d)" % (an["window_kind"], an["start_index"], an["end_index"]))
    L.append("时长 / 帧数 : %.3f s / %d 帧   采样率 %.1f Hz" %
             (an["duration_s"], an["frames"], an["sample_rate_hz"]))
    L.append("delta       : min %.4f  max %.4f  mean %.4f  峰峰 %.1f mm"
             % (an["delta_min_m"], an["delta_max_m"], an["delta_mean_m"],
                an["delta_pp_m"] * 1000.0))
    L.append("局部极值    : 极小 %d 个 / 极大 %d 个" % (an["local_minima"], an["local_maxima"]))
    if an["mean_period_s"] is not None:
        L.append("平均周期    : %.4f s  （%d 个极小间距的均值）"
                 % (an["mean_period_s"], max(an["local_minima"] - 1, 0)))
    else:
        L.append("平均周期    : n/a（局部极小不足）")
    if an["cycle_pp_m"] is not None:
        L.append("单周期峰峰  : %.1f mm  （%d 个周期的均值）"
                 % (an["cycle_pp_m"] * 1000.0, an["cycle_pp_n"]))
    else:
        L.append("单周期峰峰  : n/a")
    L.append("")
    L.append("判定        : %s" % res["verdict"])
    L.append("理由        : %s" % res["reason"])
    return "\n".join(L)


def jsonable(res):
    return json.dumps(res, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def build_parser():
    p = argparse.ArgumentParser(
        prog="114_carry_watch.py",
        description="夹爪搬运箱子的跟随质量观测器（SAWTOOTH / CONSTANT_OFFSET / NO_CARRY / INDETERMINATE）。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--poses", metavar="FILE",
                     help="离线：已录好的位姿文件（.jsonl 或 .jsonl.gz）——主要用法")
    src.add_argument("--follow", action="store_true",
                     help="在线：自己起 gz topic 子进程实时读")

    p.add_argument("--world", default=WORLD_DEFAULT,
                   help="Gazebo 世界名（默认 %(default)s，不是 flexcell_world）")
    p.add_argument("--topic", default=None,
                   help="位姿话题（默认由 --world 拼出 %s）" % TOPIC_TMPL)
    p.add_argument("-n", "--frames", type=int, default=N_DEFAULT,
                   help="--follow 时向 gz 要的帧数（默认 %(default)s）")

    p.add_argument("--box", default=BOX_DEFAULT, help="箱子模型名（默认 %(default)s）")
    p.add_argument("--gripper", nargs="+", default=list(GRIPPERS_DEFAULT),
                   help="夹爪模型名，多个取 z 均值（默认 %(default)s）")

    p.add_argument("--rest", type=float, default=None,
                   help="箱子静止高度（默认取全程 box_z 中位数）")

    p.add_argument("--grip-thr", type=float, default=GRIP_THR_DEFAULT,
                   help="夹爪 z 抬升阈值 m（默认 %(default)s）")
    p.add_argument("--lift-margin", type=float, default=LIFT_MARGIN_DEFAULT,
                   help="箱子高出静止多少算被带起来 m（默认 %(default)s）")
    p.add_argument("--gap", type=int, default=GAP_DEFAULT,
                   help="抬升 mask 中断几帧内合并（默认 %(default)s）")
    p.add_argument("--min-frames", type=int, default=MIN_FRAMES_DEFAULT,
                   help="短于此的抬升段丢弃（默认 %(default)s）")
    p.add_argument("--hold-speed", type=float, default=HOLD_SPEED_DEFAULT,
                   help="保持段夹爪速度上限 m/s（默认 %(default)s）")

    p.add_argument("--period", type=float, default=PERIOD_DEFAULT,
                   help="期望 pin 周期 s（默认 %(default)s）")
    p.add_argument("--period-tol", type=float, default=PERIOD_TOL_DEFAULT,
                   help="周期容差 s（默认 %(default)s）")
    p.add_argument("--pp-thr", type=float, default=PP_THR_DEFAULT,
                   help="单周期峰峰阈值 m（默认 %(default)s）")
    p.add_argument("--offset-tol", type=float, default=OFFSET_TOL_DEFAULT,
                   help="稳定跟随的 delta 变化上限 m（默认 %(default)s）")
    p.add_argument("--min-cycles", type=int, default=MIN_CYCLES_DEFAULT,
                   help="谈周期所需的最少局部极小个数（默认 %(default)s）")

    p.add_argument("--json", metavar="PATH", default=None,
                   help="额外把机器可读结果写到 PATH（- 表示 stdout）")
    return p


def main(argv=None):
    cfg = build_parser().parse_args(argv)
    topic = cfg.topic or TOPIC_TMPL.format(world=cfg.world)
    grip_names = list(cfg.gripper)

    # ---- 取数 ------------------------------------------------------------- #
    frames = []
    src = {"mode": "follow" if cfg.follow else "poses", "topic": topic}
    try:
        if cfg.follow:
            src["desc"] = "gz topic -e -t %s -n %d --json-output（在线）" % (topic, cfg.frames)
            print("t,box_z,grip_z,delta", flush=True)

            def on_frame(row):
                if row["box"] is None or row["grip"] is None:
                    return
                if row['t'] is None:
                    return
                t = row['t']
                print("%.4f,%.6f,%.6f,%.6f" % (t, row["box"], row["grip"],
                                               row["grip"] - row["box"]), flush=True)

            frames = follow(topic, cfg.frames, cfg.box, grip_names, on_frame)
        else:
            src["desc"] = cfg.poses
            frames, meta = load_frames_from_file(cfg.poses, cfg.box, grip_names)
            src.update(meta)
    except (IOError, ValueError, TypeError) as exc:
        sys.stderr.write("输入不可用: %s\n" % exc)
        return 2

    # ---- 目标模型在不在 ---------------------------------------------------- #
    have_box = any(fr["box"] is not None for fr in frames)
    have_grip = any(fr["grip"] is not None for fr in frames)
    if not frames:
        sys.stderr.write("输入不可用: 一条位姿都没解析出来\n")
        return 2
    if not have_box:
        sys.stderr.write("没找到箱子模型 %s\n" % cfg.box)
        return 2
    if not have_grip:
        sys.stderr.write("没找到夹爪模型 %s\n" % ", ".join(grip_names))
        return 2

    # ---- 分析 -------------------------------------------------------------- #
    try:
        times = finish_times(frames)
        if any(fr['box'] is None or fr['grip'] is None for fr in frames):
            raise ValueError('target poses missing within source recording')
        if len(times) < 2 or any(b - a > cfg.period / 2 for a, b in zip(times, times[1:])):
            raise ValueError('source sampling gaps are too large for the requested period')
    except ValueError as exc:
        sys.stderr.write('输入不可用: %s\n' % exc)
        return 2
    rest = cfg.rest if cfg.rest is not None else rest_height(frames)
    segs = lift_segments(frames, times, cfg.grip_thr, rest, cfg.lift_margin,
                         cfg.gap, cfg.min_frames)

    seg_out, primary = [], None
    for a, b in segs:
        info = {"start_index": a, "end_index": b, "frames": b - a,
                "t0": times[a], "t1": times[b - 1],
                "duration_s": times[b - 1] - times[a]}
        if primary is None or info["frames"] > primary["frames"]:
            primary = info
        seg_out.append(info)
    if primary is not None:
        primary["primary"] = True

    an = None
    if primary is not None:
        a, b = primary["start_index"], primary["end_index"]
        ha, hb = hold_window(frames, times, a, b, cfg.hold_speed)
        if ha is not None and (hb - ha) >= cfg.min_frames:
            an = analyze_window(frames, times, ha, hb, "hold")
        else:
            an = analyze_window(frames, times, a, b, "lift")

    box_vals = [fr["box"] for fr in frames if fr["box"] is not None]
    grip_vals = [fr["grip"] for fr in frames if fr["grip"] is not None]
    ctx = {"rest": rest,
           "box_max": max(box_vals) if box_vals else 0.0,
           "grip_max": max(grip_vals) if grip_vals else 0.0,
           "box_rise": (max(box_vals) - rest) if box_vals else 0.0}
    verdict, reason = judge(an, cfg, ctx)

    res = {
        "source": src,
        "models": {"box": cfg.box, "grippers": grip_names},
        "frames_total": len(frames),
        "rest_box_z": rest,
        "lift_segments": seg_out,
        "context": ctx,
        "analysis": an,
        "thresholds": {
            "grip_thr_m": cfg.grip_thr, "lift_margin_m": cfg.lift_margin,
            "period_s": cfg.period, "period_tol_s": cfg.period_tol,
            "pp_thr_m": cfg.pp_thr, "offset_tol_m": cfg.offset_tol,
            "min_cycles": cfg.min_cycles, "hold_speed_mps": cfg.hold_speed,
        },
        "verdict": verdict,
        "reason": reason,
    }

    print(human_report(res))

    if cfg.json:
        text = jsonable(res)
        if cfg.json == "-":
            print(text)
        else:
            with open(cfg.json, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
