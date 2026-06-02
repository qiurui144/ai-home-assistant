from ai_ha.topology.entity_index import EntityIndex, EntityRef
from ai_ha.topology.snapshot_store import TopologyPayload


def test_empty_index_lookup_returns_none():
    idx = EntityIndex.build_from_payload(TopologyPayload(), snapshot_id=0)
    assert idx.lookup("light.x") is None


def test_lookup_resolves_full_chain():
    payload = TopologyPayload(
        areas=[{"area_id": "a1", "name": "Living"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{
            "entity_id": "light.living_room", "device_id": "d1",
            "area_id": None,  # inherited from device
            "device_class": "light",
        }],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=7)
    ref = idx.lookup("light.living_room")
    assert ref == EntityRef(
        device_id="d1", area_id="a1", device_class="light", snapshot_id=7,
    )


def test_lookup_uses_entity_area_when_set():
    payload = TopologyPayload(
        areas=[{"area_id": "a1"}, {"area_id": "a2"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{
            "entity_id": "light.x", "device_id": "d1",
            "area_id": "a2",  # overrides device's a1
            "device_class": "light",
        }],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=1)
    ref = idx.lookup("light.x")
    assert ref is not None and ref.area_id == "a2"


def test_rebuild_swaps_atomically():
    p1 = TopologyPayload(
        areas=[{"area_id": "a1"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{"entity_id": "e1", "device_id": "d1", "area_id": None}],
    )
    idx = EntityIndex.build_from_payload(p1, snapshot_id=1)
    p2 = TopologyPayload(
        areas=[{"area_id": "a2"}],
        devices=[{"device_id": "d1", "area_id": "a2"}],
        entities=[{"entity_id": "e1", "device_id": "d1", "area_id": None}],
    )
    idx.rebuild_from_payload(p2, snapshot_id=2)
    ref = idx.lookup("e1")
    assert ref is not None and ref.area_id == "a2" and ref.snapshot_id == 2
