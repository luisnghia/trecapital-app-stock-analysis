from __future__ import annotations

from pathlib import Path

import khdn_apps.planning_priority_patch as base
import khdn_apps.priority_workflow_patch as bridge


def main():
    base_src=Path(base.__file__).read_text(encoding="utf-8")
    bridge_src=Path(bridge.__file__).read_text(encoding="utf-8")
    assert '"#D92D20"' in base_src and '"#F79009"' in base_src and '"#FEC84B"' in base_src and '"#12B76A"' in base_src
    assert 'st.subheader("🔥 Góc phần tư ưu tiên")' in base_src
    assert 'Mức ưu tiên khi duyệt' in base_src
    assert "priority_quadrant" in base_src
    assert 'urgent_override = 0' in base_src
    assert 'Ưu tiên mặc định cho công việc mới' in bridge_src
    assert 'Q1/Q2/Q3/Q4' in bridge_src
    assert 'mặc định xếp **Q2' in bridge_src
    assert '_PRIORITY_WORKFLOW_BRIDGE_INSTALLED' in bridge_src
    print("PRIORITY_WORKFLOW_QA_PASS")


if __name__=="__main__":
    main()
