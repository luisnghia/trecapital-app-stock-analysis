"""Measure the real card-key hot path against the previous implementation.

The former device-table benchmark depended on filesystem/SQLite DDL timing and
reported hypothetical typing calls. This measures identical work and checks
call-site identity; protocol and actual role-page saves have separate QA.
"""
from __future__ import annotations

import inspect
import importlib.util
import os
from pathlib import Path
import re
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if importlib.util.find_spec('khdn_apps.customer_work_note_card_patch'):
    from khdn_apps.customer_work_note_card_patch import _stable_render_context
else:
    from khdn_apps.planning_final_ux_patch import _render_context as _stable_render_context


def _reference_context():
    skip = {'customer_work_note_card_patch.py','planning_final_ux_patch.py',
            'planning_usability_v3_patch.py','planning_ui_v4_patch.py'}
    for frame in inspect.stack()[2:]:
        name = os.path.basename(frame.filename)
        if name not in skip:
            return re.sub(r'[^A-Za-z0-9_]+','_',f'{name}_{frame.function}_{frame.lineno}')
    return 'default'


def _invoke(resolver):
    return resolver()


def _same_callsite():
    results = []
    for resolver in (_reference_context, _stable_render_context):
        results.append(_invoke(resolver))
    return results


def _median_ms(resolver, count=160, rounds=5):
    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(count):
            _invoke(resolver)
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def main():
    reference_key, current_key = _same_callsite()
    assert reference_key == current_key, (reference_key, current_key)
    assert reference_key != 'default'
    reference = _median_ms(_reference_context)
    current = _median_ms(_stable_render_context)
    speedup = reference / max(current, 0.000001)
    print(f'KHDN_INTERACTION_BENCH cards=160 rounds=5 context_reference_ms={reference:.3f} '
          f'context_current_ms={current:.3f} context_speedup={speedup:.1f}x identical_callsite=1', flush=True)
    if speedup < 3:
        raise RuntimeError(f'Card-key optimization below 3x: {speedup:.2f}x')


if __name__ == '__main__':main()
