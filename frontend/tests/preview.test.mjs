import assert from "node:assert/strict";
import test from "node:test";

// These interactions must work without a backend or network requests.
process.env.NEXT_PUBLIC_DEV_MOCK = "true";
globalThis.fetch = () => { throw new Error("Preview attempted a network request"); };
const { api } = await import("../src/lib/api.ts");

test("sample profile accepts an offer and returns it on the next read", async () => {
  const offer = await api.profile.createAttribute("output", "Bicycle repair for community events");
  const profile = await api.profile.get();
  assert.ok(profile.outputs.some(item => item.id === offer.id && item.content === offer.content));
});

test("organization and event searches narrow the visible community", async () => {
  const groups = await api.organizations.list("repair");
  assert.deepEqual(groups.organizations.map(item => item.name), ["Repair Cafe"]);
  assert.equal(groups.total, 1);
  const events = await api.events.list("cleanup", true);
  assert.deepEqual(events.events.map(item => item.title), ["Park Cleanup Day"]);
});

test("each connection detail corresponds to its list entry", async () => {
  for (const match of await api.matches.list()) {
    const detail = await api.matches.getDetail(match.match_id);
    assert.equal(detail.node_b.username, match.other_username);
    assert.equal(detail.node_b.attribute_content, match.other_content);
    assert.equal(detail.node_a.attribute_content, match.own_content);
    assert.equal(detail.similarity, match.similarity);
  }
});

test("unknown detail IDs fail rather than displaying another entity", async () => {
  await assert.rejects(api.organizations.get("missing"), /not found/);
  await assert.rejects(api.events.get("missing"), /not found/);
  await assert.rejects(api.matches.getDetail("missing"), /not found/);
});
