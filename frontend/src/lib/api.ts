const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const DEV_MOCK = process.env.NEXT_PUBLIC_DEV_MOCK === "true";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || "Request failed");
  }

  return res.json();
}

export type Attribute = {
  id: string;
  direction: "input" | "output";
  content: string;
  created_at: string;
};

export type Profile = {
  node_id: string;
  username: string | null;
  email: string;
  inputs: Attribute[];
  outputs: Attribute[];
};

export type VouchInfo = {
  id: string;
  voucher_node_id: string;
  voucher_username: string | null;
  vouchee_node_id: string;
  vouchee_username: string | null;
  vouchee_email: string;
  created_at: string;
};

export type SignalInfo = {
  id: string;
  direction: "input" | "output";
  content: string;
  expires_at: string;
  created_at: string;
};

export type TrustGraph = {
  vouches_given: VouchInfo[];
  vouches_received: VouchInfo[];
  can_vouch: boolean;
};

export type MatchListItem = {
  match_id: string;
  other_username: string | null;
  own_content: string;
  own_direction: string;
  other_content: string;
  other_direction: string;
  similarity: number;
  matched_at: string;
};

export type OrgInfo = {
  node_id: string;
  name: string;
  description: string | null;
  created_at: string;
  member_count: number;
  is_member: boolean;
  graph_distance: number | null;
  inputs: Attribute[];
  outputs: Attribute[];
};

export type OrgListResponse = {
  organizations: OrgInfo[];
  total: number;
};

export type OrgMember = {
  node_id: string;
  username: string | null;
  name: string | null;
  joined_at: string;
};

export type EventInfo = {
  node_id: string;
  title: string;
  description: string | null;
  location: string | null;
  starts_at: string | null;
  ends_at: string | null;
  urgency: "standard" | "spontaneous";
  created_at: string;
  participant_count: number;
  is_participant: boolean;
  graph_distance: number | null;
  inputs: Attribute[];
  outputs: Attribute[];
};

export type EventListResponse = {
  events: EventInfo[];
  total: number;
};

export type EventParticipant = {
  node_id: string;
  username: string | null;
  name: string | null;
  joined_at: string;
};

export type MessageInfo = {
  id: string;
  from_node_id: string;
  from_username: string | null;
  to_node_id: string;
  to_username: string | null;
  context_node_id: string | null;
  context_name: string | null;
  content: string;
  created_at: string;
  read_at: string | null;
};

export type ThreadInfo = {
  other_node_id: string;
  other_username: string | null;
  context_node_id: string | null;
  context_name: string | null;
  last_message: MessageInfo;
  unread_count: number;
};

export type ContactInfo = {
  node_id: string;
  username: string | null;
};

export type ResponderInfo = {
  node_id: string;
  username: string | null;
};

export type MatchNodeInfo = {
  node_id: string;
  username: string | null;
  attribute_content: string;
  attribute_direction: string;
  attribute_type: string;
};

export type MatchDetail = {
  match_id: string;
  similarity: number;
  matched_at: string;
  node_a: MatchNodeInfo;
  node_b: MatchNodeInfo;
};

// --- Mock data for dev mode ---
let mockOutputs: Attribute[] = [
  { id: "o1", direction: "output", content: "Python mentoring", created_at: new Date().toISOString() },
  { id: "o2", direction: "output", content: "Sourdough starter", created_at: new Date().toISOString() },
  { id: "o3", direction: "output", content: "Graphic design feedback", created_at: new Date().toISOString() },
];
let mockInputs: Attribute[] = [
  { id: "i1", direction: "input", content: "Rust learning buddy", created_at: new Date().toISOString() },
  { id: "i2", direction: "input", content: "Garden plot sharing", created_at: new Date().toISOString() },
];
let mockSignals: SignalInfo[] = [
  { id: "s1", direction: "output", content: "Hosting a potluck this Saturday", expires_at: new Date(Date.now() + 7 * 86400000).toISOString(), created_at: new Date().toISOString() },
  { id: "s2", direction: "input", content: "Need a PA system for an event next month", expires_at: new Date(Date.now() + 30 * 86400000).toISOString(), created_at: new Date().toISOString() },
];
let mockUsername: string | null = "alice";
let mockOrgs: OrgInfo[] = [
  { node_id: "org-001", name: "Community Garden Co-op", description: "Shared garden plots and knowledge exchange", created_at: new Date().toISOString(), member_count: 5, is_member: true, graph_distance: 0, inputs: [{ id: "oi1", direction: "input", content: "Volunteers for spring planting", created_at: new Date().toISOString() }], outputs: [{ id: "oo1", direction: "output", content: "Fresh produce shares", created_at: new Date().toISOString() }] },
  { node_id: "org-002", name: "Repair Cafe", description: "Fix things together instead of throwing them away", created_at: new Date().toISOString(), member_count: 12, is_member: false, graph_distance: 2, inputs: [], outputs: [] },
];
let mockEvents: EventInfo[] = [
  { node_id: "evt-001", title: "Park Cleanup Day", description: "Help us clean up Riverside Park", location: "Riverside Park", starts_at: new Date(Date.now() + 3 * 86400000).toISOString(), ends_at: new Date(Date.now() + 3 * 86400000 + 3 * 3600000).toISOString(), urgency: "standard", created_at: new Date().toISOString(), participant_count: 8, is_participant: true, graph_distance: 1, inputs: [{ id: "ei1", direction: "input", content: "Trash bags and gloves", created_at: new Date().toISOString() }], outputs: [{ id: "eo1", direction: "output", content: "Pizza lunch provided", created_at: new Date().toISOString() }] },
  { node_id: "evt-002", title: "Spontaneous Jam Session", description: "Bring an instrument or just listen", location: "Community Center", starts_at: new Date(Date.now() + 86400000).toISOString(), ends_at: null, urgency: "spontaneous", created_at: new Date().toISOString(), participant_count: 3, is_participant: false, graph_distance: null, inputs: [], outputs: [] },
];
let mockMessages: MessageInfo[] = [
  { id: "msg-1", from_node_id: "dev-node-001", from_username: "alice", to_node_id: "dev-node-002", to_username: "bob", context_node_id: "evt-001", context_name: "Park Cleanup Day", content: "Hey, I'd love to help out with the cleanup!", created_at: new Date(Date.now() - 3600000).toISOString(), read_at: null },
  { id: "msg-2", from_node_id: "dev-node-002", from_username: "bob", to_node_id: "dev-node-001", to_username: "alice", context_node_id: "evt-001", context_name: "Park Cleanup Day", content: "Great! We could use help with the south trail area.", created_at: new Date(Date.now() - 1800000).toISOString(), read_at: null },
];
const mockMatches: MatchListItem[] = [
  { match_id: "m1", other_username: "bob", own_content: "Python mentoring", own_direction: "output", other_content: "Learn Python for data science", other_direction: "input", similarity: 0.87, matched_at: new Date().toISOString() },
  { match_id: "m2", other_username: "carol", own_content: "Garden plot sharing", own_direction: "input", other_content: "Have extra garden space this summer", other_direction: "output", similarity: 0.82, matched_at: new Date().toISOString() },
];
let mockIdCounter = 10;

function getMockProfile(): Profile {
  return {
    node_id: "dev-node-001",
    username: mockUsername,
    email: "alice@example.com",
    inputs: [...mockInputs],
    outputs: [...mockOutputs],
  };
}

export const api = DEV_MOCK
  ? {
      auth: {
        requestMagicLink: async (_email: string) => ({ message: "ok" }),
        verify: async (_token: string) => ({ status: "ok", node_id: "dev-node-001" }),
        me: async () => ({
          node_id: "dev-node-001",
          username: mockUsername,
          email: "alice@example.com",
          is_active: true,
        }),
        logout: async () => ({ status: "ok" }),
      },
      profile: {
        get: async () => getMockProfile(),
        getUser: async (_userId: string) => getMockProfile(),
        updateUsername: async (username: string) => {
          mockUsername = username;
          return getMockProfile();
        },
        createAttribute: async (direction: "input" | "output", content: string) => {
          const attr: Attribute = { id: `mock-${++mockIdCounter}`, direction, content, created_at: new Date().toISOString() };
          if (direction === "output") mockOutputs.push(attr);
          else mockInputs.push(attr);
          return attr;
        },
        updateAttribute: async (id: string, content: string) => {
          const list = [...mockOutputs, ...mockInputs];
          const item = list.find((a) => a.id === id);
          if (item) item.content = content;
          return item as Attribute;
        },
        deleteAttribute: async (id: string) => {
          mockOutputs = mockOutputs.filter((a) => a.id !== id);
          mockInputs = mockInputs.filter((a) => a.id !== id);
        },
      },
      trust: {
        getGraph: async (): Promise<TrustGraph> => ({
          vouches_given: [
            { id: "v1", voucher_node_id: "dev-node-001", voucher_username: "alice", vouchee_node_id: "dev-node-002", vouchee_username: "bob", vouchee_email: "bob@example.com", created_at: new Date().toISOString() },
          ],
          vouches_received: [
            { id: "v2", voucher_node_id: "dev-node-003", voucher_username: "carol", vouchee_node_id: "dev-node-001", vouchee_username: "alice", vouchee_email: "alice@example.com", created_at: new Date().toISOString() },
          ],
          can_vouch: true,
        }),
        vouch: async (_email: string) => ({ vouch: {} as VouchInfo, invite_sent: true }),
        withdrawVouch: async (_id: string) => {},
        cool: async (_userId: string) => {},
        uncool: async (_userId: string) => {},
        block: async (_nodeId: string) => {},
        unblock: async (_nodeId: string) => {},
      },
      signals: {
        list: async () => [...mockSignals],
        create: async (direction: "input" | "output", content: string, expiresInDays: number = 30) => {
          const sig: SignalInfo = { id: `mock-s-${++mockIdCounter}`, direction, content, expires_at: new Date(Date.now() + expiresInDays * 86400000).toISOString(), created_at: new Date().toISOString() };
          mockSignals.push(sig);
          return sig;
        },
        remove: async (id: string) => { mockSignals = mockSignals.filter((s) => s.id !== id); },
      },
      matches: {
        list: async (): Promise<MatchListItem[]> => [...mockMatches],
        getDetail: async (matchId: string): Promise<MatchDetail> => {
          const match = mockMatches.find(item => item.match_id === matchId);
          if (!match) throw new Error("Connection not found");
          return {
            match_id: match.match_id, similarity: match.similarity, matched_at: match.matched_at,
            node_a: { node_id: "dev-node-001", username: "alice", attribute_content: match.own_content, attribute_direction: match.own_direction, attribute_type: "membrane" },
            node_b: { node_id: match.other_username === "bob" ? "dev-node-002" : "dev-node-003", username: match.other_username, attribute_content: match.other_content, attribute_direction: match.other_direction, attribute_type: "membrane" },
          };
        },
      },
      organizations: {
        list: async (search?: string): Promise<OrgListResponse> => {
          const query = search?.trim().toLowerCase() || "";
          const organizations = mockOrgs.filter(org => `${org.name} ${org.description || ""}`.toLowerCase().includes(query));
          return { organizations, total: organizations.length };
        },
        get: async (nodeId: string): Promise<OrgInfo> => {
          const org = mockOrgs.find(item => item.node_id === nodeId);
          if (!org) throw new Error("Organization not found");
          return org;
        },
        create: async (name: string, description?: string): Promise<OrgInfo> => {
          const org: OrgInfo = { node_id: `org-${++mockIdCounter}`, name, description: description || null, created_at: new Date().toISOString(), member_count: 1, is_member: true, graph_distance: 0, inputs: [], outputs: [] };
          mockOrgs.push(org);
          return org;
        },
        update: async (nodeId: string, data: { name?: string; description?: string }): Promise<OrgInfo> => {
          const org = mockOrgs.find(o => o.node_id === nodeId);
          if (org) { if (data.name) org.name = data.name; if (data.description !== undefined) org.description = data.description; }
          return org || mockOrgs[0];
        },
        delete: async (nodeId: string) => { mockOrgs = mockOrgs.filter(o => o.node_id !== nodeId); },
        getMembers: async (_nodeId: string): Promise<OrgMember[]> => [
          { node_id: "dev-node-001", username: "alice", name: "Alice", joined_at: new Date().toISOString() },
          { node_id: "dev-node-002", username: "bob", name: "Bob", joined_at: new Date().toISOString() },
        ],
        vouchMember: async (_nodeId: string, _voucheeNodeId: string): Promise<OrgMember> => ({ node_id: "dev-node-003", username: "carol", name: "Carol", joined_at: new Date().toISOString() }),
        leave: async (_nodeId: string) => {},
        createAttribute: async (nodeId: string, direction: "input" | "output", content: string) => {
          const attr: Attribute = { id: `mock-${++mockIdCounter}`, direction, content, created_at: new Date().toISOString() };
          const org = mockOrgs.find(o => o.node_id === nodeId);
          if (org) { if (direction === "output") org.outputs.push(attr); else org.inputs.push(attr); }
          return attr;
        },
        updateAttribute: async (_nodeId: string, attrId: string, content: string) => {
          for (const org of mockOrgs) { for (const a of [...org.inputs, ...org.outputs]) { if (a.id === attrId) { a.content = content; return a; } } }
          return { id: attrId, direction: "output" as const, content, created_at: new Date().toISOString() };
        },
        deleteAttribute: async (nodeId: string, attrId: string) => {
          const org = mockOrgs.find(o => o.node_id === nodeId);
          if (org) { org.inputs = org.inputs.filter(a => a.id !== attrId); org.outputs = org.outputs.filter(a => a.id !== attrId); }
        },
        getResponders: async (_nodeId: string): Promise<ResponderInfo[]> => [
          { node_id: "dev-node-001", username: "alice" },
        ],
        addResponder: async (_nodeId: string, _responderNodeId: string) => {},
        removeResponder: async (_nodeId: string, _responderNodeId: string) => {},
      },
      events: {
        list: async (search?: string, upcoming?: boolean): Promise<EventListResponse> => {
          const query = search?.trim().toLowerCase() || "";
          const events = mockEvents.filter(event =>
            `${event.title} ${event.description || ""}`.toLowerCase().includes(query) &&
            (!upcoming || !event.ends_at || new Date(event.ends_at).getTime() > Date.now()));
          return { events, total: events.length };
        },
        get: async (nodeId: string): Promise<EventInfo> => {
          const event = mockEvents.find(item => item.node_id === nodeId);
          if (!event) throw new Error("Event not found");
          return event;
        },
        create: async (data: { title: string; description?: string; location?: string; starts_at?: string; ends_at?: string; urgency?: string }): Promise<EventInfo> => {
          const evt: EventInfo = { node_id: `evt-${++mockIdCounter}`, title: data.title, description: data.description || null, location: data.location || null, starts_at: data.starts_at || null, ends_at: data.ends_at || null, urgency: (data.urgency as "standard" | "spontaneous") || "standard", created_at: new Date().toISOString(), participant_count: 1, is_participant: true, graph_distance: 0, inputs: [], outputs: [] };
          mockEvents.push(evt);
          return evt;
        },
        update: async (nodeId: string, data: Record<string, unknown>): Promise<EventInfo> => {
          const evt = mockEvents.find(e => e.node_id === nodeId);
          if (evt) Object.assign(evt, data);
          return evt || mockEvents[0];
        },
        delete: async (nodeId: string) => { mockEvents = mockEvents.filter(e => e.node_id !== nodeId); },
        getParticipants: async (_nodeId: string): Promise<EventParticipant[]> => [
          { node_id: "dev-node-001", username: "alice", name: "Alice", joined_at: new Date().toISOString() },
        ],
        vouchParticipant: async (_nodeId: string, _voucheeNodeId: string): Promise<EventParticipant> => ({ node_id: "dev-node-003", username: "carol", name: "Carol", joined_at: new Date().toISOString() }),
        leave: async (_nodeId: string) => {},
        createAttribute: async (nodeId: string, direction: "input" | "output", content: string) => {
          const attr: Attribute = { id: `mock-${++mockIdCounter}`, direction, content, created_at: new Date().toISOString() };
          const evt = mockEvents.find(e => e.node_id === nodeId);
          if (evt) { if (direction === "output") evt.outputs.push(attr); else evt.inputs.push(attr); }
          return attr;
        },
        updateAttribute: async (_nodeId: string, attrId: string, content: string) => {
          for (const evt of mockEvents) { for (const a of [...evt.inputs, ...evt.outputs]) { if (a.id === attrId) { a.content = content; return a; } } }
          return { id: attrId, direction: "output" as const, content, created_at: new Date().toISOString() };
        },
        deleteAttribute: async (nodeId: string, attrId: string) => {
          const evt = mockEvents.find(e => e.node_id === nodeId);
          if (evt) { evt.inputs = evt.inputs.filter(a => a.id !== attrId); evt.outputs = evt.outputs.filter(a => a.id !== attrId); }
        },
        getResponders: async (_nodeId: string): Promise<ResponderInfo[]> => [
          { node_id: "dev-node-001", username: "alice" },
        ],
        addResponder: async (_nodeId: string, _responderNodeId: string) => {},
        removeResponder: async (_nodeId: string, _responderNodeId: string) => {},
      },
      messages: {
        list: async (): Promise<{ threads: ThreadInfo[] }> => {
          const threadMap = new Map<string, ThreadInfo>();
          for (const msg of mockMessages) {
            const otherId = msg.from_node_id === "dev-node-001" ? msg.to_node_id : msg.from_node_id;
            const key = `${otherId}:${msg.context_node_id || "direct"}`;
            const existing = threadMap.get(key);
            if (!existing || new Date(msg.created_at) > new Date(existing.last_message.created_at)) {
              threadMap.set(key, {
                other_node_id: otherId,
                other_username: otherId === "dev-node-002" ? "bob" : "carol",
                context_node_id: msg.context_node_id,
                context_name: msg.context_name,
                last_message: msg,
                unread_count: mockMessages.filter(m => m.to_node_id === "dev-node-001" && m.from_node_id === otherId && m.context_node_id === msg.context_node_id && !m.read_at).length,
              });
            }
          }
          return { threads: [...threadMap.values()].sort((a, b) => new Date(b.last_message.created_at).getTime() - new Date(a.last_message.created_at).getTime()) };
        },
        getThread: async (otherNodeId: string, contextNodeId?: string, _limit?: number, _offset?: number): Promise<{ messages: MessageInfo[], total: number }> => {
          const filtered = mockMessages.filter(m => {
            const match = (m.from_node_id === "dev-node-001" && m.to_node_id === otherNodeId) || (m.from_node_id === otherNodeId && m.to_node_id === "dev-node-001");
            const ctxMatch = contextNodeId ? m.context_node_id === contextNodeId : !m.context_node_id;
            return match && ctxMatch;
          });
          return { messages: filtered, total: filtered.length };
        },
        send: async (content: string, opts: { toNodeId?: string; contextNodeId?: string }): Promise<MessageInfo> => {
          const msg: MessageInfo = {
            id: `msg-${++mockIdCounter}`, from_node_id: "dev-node-001", from_username: "alice",
            to_node_id: opts.toNodeId || "dev-node-002", to_username: "bob",
            context_node_id: opts.contextNodeId || null, context_name: opts.contextNodeId ? "Park Cleanup Day" : null,
            content, created_at: new Date().toISOString(), read_at: null,
          };
          mockMessages.push(msg);
          return msg;
        },
        markRead: async (_otherNodeId: string, _contextNodeId?: string): Promise<{ marked: number }> => {
          let count = 0;
          for (const m of mockMessages) {
            if (m.to_node_id === "dev-node-001" && !m.read_at) { m.read_at = new Date().toISOString(); count++; }
          }
          return { marked: count };
        },
        unreadCount: async (): Promise<{ count: number }> => ({
          count: mockMessages.filter(m => m.to_node_id === "dev-node-001" && !m.read_at).length,
        }),
        contacts: async (): Promise<ContactInfo[]> => [
          { node_id: "dev-node-002", username: "bob" },
        ],
      },
    }
  : {
      auth: {
        requestMagicLink: (email: string) =>
          apiFetch<{ message: string }>("/api/auth/request", {
            method: "POST",
            body: JSON.stringify({ email }),
          }),

        verify: (token: string) =>
          apiFetch<{ status: string; node_id: string }>(`/api/auth/verify?token=${token}`),

        me: () =>
          apiFetch<{
            node_id: string;
            username: string | null;
            email: string;
            is_active: boolean;
          }>("/api/auth/me"),

        logout: () =>
          apiFetch<{ status: string }>("/api/auth/logout", { method: "POST" }),
      },

      profile: {
        get: () => apiFetch<Profile>("/api/profile"),

        getUser: (userId: string) => apiFetch<Profile>(`/api/profile/${userId}`),

        updateUsername: (username: string) =>
          apiFetch<Profile>("/api/profile/username", {
            method: "PUT",
            body: JSON.stringify({ username }),
          }),

        createAttribute: (direction: "input" | "output", content: string) =>
          apiFetch<Attribute>("/api/profile/attributes", {
            method: "POST",
            body: JSON.stringify({ direction, content }),
          }),

        updateAttribute: (id: string, content: string) =>
          apiFetch<Attribute>(`/api/profile/attributes/${id}`, {
            method: "PUT",
            body: JSON.stringify({ content }),
          }),

        deleteAttribute: (id: string) =>
          apiFetch<void>(`/api/profile/attributes/${id}`, { method: "DELETE" }),
      },

      trust: {
        getGraph: () => apiFetch<TrustGraph>("/api/trust/graph"),

        vouch: (email: string) =>
          apiFetch<{ vouch: VouchInfo; invite_sent: boolean }>("/api/trust/vouch", {
            method: "POST",
            body: JSON.stringify({ email }),
          }),

        withdrawVouch: (vouchId: string) =>
          apiFetch<void>(`/api/trust/vouch/${vouchId}`, { method: "DELETE" }),

        cool: (userId: string) =>
          apiFetch<void>(`/api/trust/cool/${userId}`, { method: "POST" }),

        uncool: (userId: string) =>
          apiFetch<void>(`/api/trust/cool/${userId}`, { method: "DELETE" }),

        block: (nodeId: string) =>
          apiFetch<void>(`/api/trust/block/${nodeId}`, { method: "POST" }),

        unblock: (nodeId: string) =>
          apiFetch<void>(`/api/trust/block/${nodeId}`, { method: "DELETE" }),
      },

      signals: {
        list: () => apiFetch<SignalInfo[]>("/api/signals"),

        create: (direction: "input" | "output", content: string, expiresInDays: number = 30) =>
          apiFetch<SignalInfo>("/api/signals", {
            method: "POST",
            body: JSON.stringify({ direction, content, expires_in_days: expiresInDays }),
          }),

        remove: (id: string) =>
          apiFetch<void>(`/api/signals/${id}`, { method: "DELETE" }),
      },

      matches: {
        list: () => apiFetch<MatchListItem[]>("/api/matches"),

        getDetail: (matchId: string) =>
          apiFetch<MatchDetail>(`/api/matches/${matchId}`),
      },

      organizations: {
        list: (search?: string) => {
          const params = search ? `?search=${encodeURIComponent(search)}` : "";
          return apiFetch<OrgListResponse>(`/api/organizations${params}`);
        },

        get: (nodeId: string) =>
          apiFetch<OrgInfo>(`/api/organizations/${nodeId}`),

        create: (name: string, description?: string) =>
          apiFetch<OrgInfo>("/api/organizations", {
            method: "POST",
            body: JSON.stringify({ name, description }),
          }),

        update: (nodeId: string, data: { name?: string; description?: string }) =>
          apiFetch<OrgInfo>(`/api/organizations/${nodeId}`, {
            method: "PUT",
            body: JSON.stringify(data),
          }),

        delete: (nodeId: string) =>
          apiFetch<void>(`/api/organizations/${nodeId}`, { method: "DELETE" }),

        getMembers: (nodeId: string) =>
          apiFetch<OrgMember[]>(`/api/organizations/${nodeId}/members`),

        vouchMember: (nodeId: string, voucheeNodeId: string) =>
          apiFetch<OrgMember>(`/api/organizations/${nodeId}/vouch?vouchee_node_id=${voucheeNodeId}`, {
            method: "POST",
          }),

        leave: (nodeId: string) =>
          apiFetch<void>(`/api/organizations/${nodeId}/leave`, { method: "DELETE" }),

        createAttribute: (nodeId: string, direction: "input" | "output", content: string) =>
          apiFetch<Attribute>(`/api/organizations/${nodeId}/attributes`, {
            method: "POST",
            body: JSON.stringify({ direction, content }),
          }),

        updateAttribute: (nodeId: string, attrId: string, content: string) =>
          apiFetch<Attribute>(`/api/organizations/${nodeId}/attributes/${attrId}`, {
            method: "PUT",
            body: JSON.stringify({ content }),
          }),

        deleteAttribute: (nodeId: string, attrId: string) =>
          apiFetch<void>(`/api/organizations/${nodeId}/attributes/${attrId}`, { method: "DELETE" }),

        getResponders: (nodeId: string) =>
          apiFetch<ResponderInfo[]>(`/api/organizations/${nodeId}/responders`),

        addResponder: (nodeId: string, responderNodeId: string) =>
          apiFetch<void>(`/api/organizations/${nodeId}/responders`, {
            method: "POST",
            body: JSON.stringify({ node_id: responderNodeId }),
          }),

        removeResponder: (nodeId: string, responderNodeId: string) =>
          apiFetch<void>(`/api/organizations/${nodeId}/responders/${responderNodeId}`, { method: "DELETE" }),
      },

      events: {
        list: (search?: string, upcoming?: boolean) => {
          const params = new URLSearchParams();
          if (search) params.set("search", search);
          if (upcoming) params.set("upcoming", "true");
          const qs = params.toString();
          return apiFetch<EventListResponse>(`/api/events${qs ? `?${qs}` : ""}`);
        },

        get: (nodeId: string) =>
          apiFetch<EventInfo>(`/api/events/${nodeId}`),

        create: (data: { title: string; description?: string; location?: string; starts_at?: string; ends_at?: string; urgency?: string }) =>
          apiFetch<EventInfo>("/api/events", {
            method: "POST",
            body: JSON.stringify(data),
          }),

        update: (nodeId: string, data: Record<string, unknown>) =>
          apiFetch<EventInfo>(`/api/events/${nodeId}`, {
            method: "PUT",
            body: JSON.stringify(data),
          }),

        delete: (nodeId: string) =>
          apiFetch<void>(`/api/events/${nodeId}`, { method: "DELETE" }),

        getParticipants: (nodeId: string) =>
          apiFetch<EventParticipant[]>(`/api/events/${nodeId}/participants`),

        vouchParticipant: (nodeId: string, voucheeNodeId: string) =>
          apiFetch<EventParticipant>(`/api/events/${nodeId}/vouch?vouchee_node_id=${voucheeNodeId}`, {
            method: "POST",
          }),

        leave: (nodeId: string) =>
          apiFetch<void>(`/api/events/${nodeId}/leave`, { method: "DELETE" }),

        createAttribute: (nodeId: string, direction: "input" | "output", content: string) =>
          apiFetch<Attribute>(`/api/events/${nodeId}/attributes`, {
            method: "POST",
            body: JSON.stringify({ direction, content }),
          }),

        updateAttribute: (nodeId: string, attrId: string, content: string) =>
          apiFetch<Attribute>(`/api/events/${nodeId}/attributes/${attrId}`, {
            method: "PUT",
            body: JSON.stringify({ content }),
          }),

        deleteAttribute: (nodeId: string, attrId: string) =>
          apiFetch<void>(`/api/events/${nodeId}/attributes/${attrId}`, { method: "DELETE" }),

        getResponders: (nodeId: string) =>
          apiFetch<ResponderInfo[]>(`/api/events/${nodeId}/responders`),

        addResponder: (nodeId: string, responderNodeId: string) =>
          apiFetch<void>(`/api/events/${nodeId}/responders`, {
            method: "POST",
            body: JSON.stringify({ node_id: responderNodeId }),
          }),

        removeResponder: (nodeId: string, responderNodeId: string) =>
          apiFetch<void>(`/api/events/${nodeId}/responders/${responderNodeId}`, { method: "DELETE" }),
      },

      messages: {
        list: () =>
          apiFetch<{ threads: ThreadInfo[] }>("/api/messages"),

        getThread: (otherNodeId: string, contextNodeId?: string, limit?: number, offset?: number) => {
          const params = new URLSearchParams();
          if (contextNodeId) params.set("context", contextNodeId);
          if (limit) params.set("limit", String(limit));
          if (offset) params.set("offset", String(offset));
          const qs = params.toString();
          return apiFetch<{ messages: MessageInfo[]; total: number }>(`/api/messages/thread/${otherNodeId}${qs ? `?${qs}` : ""}`);
        },

        send: (content: string, opts: { toNodeId?: string; contextNodeId?: string }) =>
          apiFetch<MessageInfo>("/api/messages", {
            method: "POST",
            body: JSON.stringify({
              content,
              to_node_id: opts.toNodeId || null,
              context_node_id: opts.contextNodeId || null,
            }),
          }),

        markRead: (otherNodeId: string, contextNodeId?: string) => {
          const params = contextNodeId ? `?context=${contextNodeId}` : "";
          return apiFetch<{ marked: number }>(`/api/messages/thread/${otherNodeId}/read${params}`, { method: "POST" });
        },

        unreadCount: () =>
          apiFetch<{ count: number }>("/api/messages/unread-count"),

        contacts: () =>
          apiFetch<ContactInfo[]>("/api/messages/contacts"),
      },
    };
