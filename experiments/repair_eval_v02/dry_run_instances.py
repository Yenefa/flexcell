"""Dry run for the pre-registered instances: injected must fail, repaired must pass.

WHY
    A gate that passes everything and a gate that fails everything look the same
    from a distance: both produce a column of one value. The only way to know the
    gate discriminates is to hand it both a broken and a repaired workspace and
    watch the answer change.

    This costs no model tokens, so it runs before any slot is dispatched.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import instances as I  # noqa: E402


def main():
    report = {}
    ok = True
    for family in I.FAMILIES:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "candidate"
            I.materialize(family, root)
            broken_ok, broken = I.check(family, root)
            I.apply_reference_fix(family, root)
            fixed_ok, fixed = I.check(family, root)
            entry = {
                "injected": {"ok": broken_ok, "code": broken.get("code")},
                "repaired": {"ok": fixed_ok, "code": fixed.get("code")},
                "discriminates": (not broken_ok) and fixed_ok,
            }
            report[family] = entry
            if not entry["discriminates"]:
                ok = False
            print("%-12s injected=%-9s repaired=%-6s discriminates=%s"
                  % (family, broken.get("code"), fixed.get("code"), entry["discriminates"]))
    print(json.dumps({"ok": ok, "instances": report}, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
