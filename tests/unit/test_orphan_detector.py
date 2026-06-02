from ai_ha.topology.orphan_detector import find_orphans
from ai_ha.topology.snapshot_store import TopologyPayload


def test_no_orphans_when_all_have_area():
    p = TopologyPayload(
        areas=[{"area_id": "a1"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[
            {"entity_id": "e1", "device_id": "d1", "area_id": None},
            {"entity_id": "e2", "device_id": None, "area_id": "a1"},
        ],
    )
    assert find_orphans(p) == []


def test_orphan_no_device_no_area():
    p = TopologyPayload(
        areas=[{"area_id": "a1"}],
        devices=[],
        entities=[{"entity_id": "orphan.x", "device_id": None, "area_id": None}],
    )
    assert find_orphans(p) == ["orphan.x"]


def test_orphan_device_without_area():
    p = TopologyPayload(
        areas=[{"area_id": "a1"}],
        devices=[{"device_id": "d_orphan", "area_id": None}],
        entities=[{"entity_id": "x", "device_id": "d_orphan", "area_id": None}],
    )
    assert find_orphans(p) == ["x"]


def test_disabled_entities_skipped():
    p = TopologyPayload(
        areas=[],
        devices=[],
        entities=[
            {"entity_id": "x", "device_id": None, "area_id": None, "disabled_by": "user"},
            {"entity_id": "y", "device_id": None, "area_id": None},
        ],
    )
    assert find_orphans(p) == ["y"]
