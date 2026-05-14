"""Demo: QTApplier on real Vietphrase + Names + PhienAm + LuatNhan.

First run: builds + caches automatons (slow). Subsequent runs: warm cache.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from trilex.qt_dict.applier import QTApplier

ROOT = Path(__file__).resolve().parents[1]
DICT_DIR = ROOT / "data" / "dictionaries"
CACHE_DIR = ROOT / "data" / "cache"

SAMPLE_500 = (
    "林天望着面前的金丹大圆满老者，心中涌起一股难以言喻的敬畏。这位前辈乃是青云"
    "宗的太上长老，曾经在三百年前一战成名，斩杀过元婴期的妖兽。他盘膝而坐，开始"
    "运转九转玄功，体内灵气如同江河奔涌，丹田中的金丹散发出耀眼的光芒。突然，一"
    "道天雷从九天之上劈下，林天的瞳孔骤然收缩，他知道，劫难来了。这是渡劫期修士"
    "才会遇到的天劫。"
)

SAMPLE_1000 = SAMPLE_500 + (
    "雷霆轰鸣，紫色的雷电在虚空中盘旋，仿佛要将整片天地撕裂。林天怒吼一声，体内"
    "九条真龙虚影盘旋而起，护住他的周身。他要在这一劫中蜕变，从金丹期一跃而入元"
    "婴境界！前辈站在远处冷眼旁观，眉头微皱，心中暗自感叹这小子的天赋果然不凡。"
    "三百年来，从未见过如此惊艳的修炼者。雷电劈下，林天浑身鲜血直流，但他眼神依"
    "旧坚毅。这一刻，他想起师父临终前的嘱托，想起青云宗千百年来无数同门的期盼。"
    "他绝不能倒下，绝不能让这一脉就此断绝。轰隆一声巨响，最后一道天雷劈下。"
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("Building QTApplier (uses cache if available) ...")
    t0 = time.perf_counter()
    applier = QTApplier(DICT_DIR, cache_dir=CACHE_DIR)
    print(f"Loaded tiers: {applier.tier_names}")
    print(f"Init took {time.perf_counter() - t0:.2f}s")
    print()

    print(f"=== Side-by-side ({len(SAMPLE_500)} chars) ===")
    t0 = time.perf_counter()
    converted = applier.convert(SAMPLE_500)
    elapsed = time.perf_counter() - t0
    print(f"-- Source ({len(SAMPLE_500)} chars) --")
    print(SAMPLE_500)
    print()
    print(f"-- Converted ({len(converted)} chars, took {elapsed * 1000:.1f} ms) --")
    print(converted)
    print()

    # Stress test: replicate sample to reach 1000+ chars for the perf target
    stress_text = SAMPLE_1000
    while len(stress_text) < 1000:
        stress_text += SAMPLE_1000
    stress_text = stress_text[:1024]

    print("=== Performance: 1024-char sample ===")
    t0 = time.perf_counter()
    out_stress = applier.convert(stress_text)
    elapsed_stress = time.perf_counter() - t0
    print(f"  source_chars={len(stress_text)}")
    print(f"  output_chars={len(out_stress)}")
    print(f"  convert_time={elapsed_stress * 1000:.1f} ms")
    target = 500.0
    status = "PASS" if elapsed_stress * 1000 < target else "FAIL"
    print(f"  target=<{target:.0f}ms  status={status}")
    print()
    # Custom-glossary demo
    out_glossary = applier.convert(
        "林天走入青云宗",
        custom_glossary={"林天": "Lin Tian", "青云宗": "Cloud Sect"},
    )
    print("=== Custom glossary override ===")
    print("  in : 林天走入青云宗")
    print(f"  out: {out_glossary}")


if __name__ == "__main__":
    main()
