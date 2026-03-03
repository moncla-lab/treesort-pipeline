#!/usr/bin/env python3
"""Verify reassortment diagnostic outputs. Exit 0 if all checks pass, 1 if any fail."""

import json
import sys


def main():
    unmapped = json.load(open("results/diagnostics/unmapped_targets.json"))
    unannotated = json.load(open("results/diagnostics/unannotated_nodes.json"))
    auspice = json.load(open("results/diagnostics/auspice_validation.json"))

    passed = 0
    failed = 0

    # 1. Counts add up
    for name, d in [("unmapped_targets", unmapped), ("unannotated_nodes", unannotated)]:
        total = d["total_target_internal"]
        summed = d["annotated_count"] + d["unannotated_count"]
        if summed == total:
            print(f"PASS  {name}: annotated + unannotated = total ({total})")
            passed += 1
        else:
            print(f"FAIL  {name}: {summed} != {total}")
            failed += 1

    # 2. No Auspice inconsistencies
    n = auspice["in_auspice_with_reassorted"]
    if n == 0:
        print(f"PASS  auspice_validation: no inconsistencies")
        passed += 1
    else:
        print(f"FAIL  auspice_validation: {n} nodes marked unannotated but have reassorted in Auspice")
        failed += 1

    # 3. Actual unannotated >= simulated unmapped (mapper also filters by confidence)
    sim = unmapped["unannotated_count"]
    actual = unannotated["unannotated_count"]
    if actual >= sim:
        print(f"PASS  cross-check: unannotated ({actual}) >= unmapped ({sim})")
        passed += 1
    else:
        print(f"FAIL  cross-check: unannotated ({actual}) < unmapped ({sim})")
        failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
