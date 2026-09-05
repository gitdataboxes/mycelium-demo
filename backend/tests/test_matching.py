"""Exercise ORM-written directions through the real pgvector matching query."""
import pytest
from app.models.community import Community
from app.models.node import Node, NodeType
from app.models.profile import AttributeDirection, MembraneEntry
from app.services.matching import _find_attribute_matches


@pytest.mark.asyncio
async def test_matching_reads_orm_offer_and_need(db):
    community = Community(name="Matching fixture")
    db.add(community)
    await db.flush()
    giver = Node(community_id=community.id, type=NodeType.USER)
    receiver = Node(community_id=community.id, type=NodeType.USER)
    db.add_all([giver, receiver])
    await db.flush()
    vector = [1.0] + [0.0] * 1023
    db.add_all([
        MembraneEntry(node_id=giver.id, direction=AttributeDirection.OUTPUT,
                      content="Bicycle repairs", embedding=vector),
        MembraneEntry(node_id=receiver.id, direction=AttributeDirection.INPUT,
                      content="Need a bike repaired", embedding=vector),
    ])
    await db.commit()
    matches = await _find_attribute_matches(db)
    assert len(matches) == 1
    assert matches[0].node_a_id == giver.id
    assert matches[0].node_b_id == receiver.id
    assert matches[0].similarity == pytest.approx(1.0)
