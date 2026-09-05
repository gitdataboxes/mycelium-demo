# Messaging — Implementation Spec

## Purpose

Messaging is the brokered introduction channel, anchored to participation. When the network surfaces a match — an event to volunteer at, an organization to join — users need a way to follow up with whoever manages that entity. All first contact happens through an event or organization. Individual user profiles are not browsable, searchable, or directly messageable.

This is NOT a chat app. Messages are short, asynchronous, and exist to coordinate. The system should feel more like leaving a note than starting a conversation. The platform mediates the first contact through context (events/orgs), then gets out of the way.

## Core Concepts

### Thread Types

**Context threads** are tied to an event or organization. When a user contacts "Park Cleanup Saturday," the message goes to whoever manages that event. The thread lives in the context of that entity — both parties see it labeled with the event/org name. Context threads persist after the event ends or the org goes dormant — the channel stays open unless someone blocks or reports.

**Direct threads** are person-to-person with no attached context. These are only possible between users who have previously exchanged messages through a context thread. You earn a contact by participating; you can't cold-message someone.

### Contacts

Contacts are emergent. Anyone you've exchanged messages with (through any thread type) becomes a contact. No explicit "add contact" action — just message history. Your contact list = the set of users you've had at least one message exchange with. From your contact list, you can start direct threads.

### Responders

Each event or organization has designated responders — users who receive and reply to incoming messages for that entity. The creator is automatically a responder. Responders can add other responders (delegation). This is just "who answers the inbox for this thing."

## What Exists Today

### Message Model (needs migration)

`backend/app/models/message.py` — migrated, but needs `context_node_id` added:

```python
class Message(Base):
    __tablename__ = "messages"
    id: uuid           # PK
    from_user: uuid    # FK → users.node_id
    to_user: uuid      # FK → users.node_id
    content: text
    created_at: timestamptz
    read_at: timestamptz | None
    # MISSING: context_node_id → FK nodes.id
```

Index on `(to_user, created_at)` exists. The model has `sender` and `recipient` relationships to `User`.

### Node/Edge Model (ready to use)

Nodes represent users, events, and organizations. Edges encode relationships (VOUCH, COOL, BLOCK, MEMBER, PARTICIPANT, HOST). The `EdgeType` enum needs a new `RESPONDER` type.

### Trust System

`backend/app/services/trust.py` has cool edge management. `BLOCK` exists in EdgeType but has no service logic or router endpoints. Block needs to be implemented as part of messaging.

### Frontend Gaps

- No messages page exists
- No unread indicator anywhere
- Event/org detail pages have no "Contact" action
- Match detail page says "Reach out directly if their profile includes contact preferences"

## What Needs to Be Built

### 1. Model Changes

#### Migration: add context_node_id to messages

```python
context_node_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=True
)
context_node: Mapped["Node | None"] = relationship(foreign_keys=[context_node_id])
```

Add index: `(context_node_id, created_at)`.

#### Add RESPONDER to EdgeType

```python
RESPONDER = "responder"  # user → event/org node
```

A `RESPONDER` edge from user A to node X means "A handles messages for X."

#### Auto-create RESPONDER edge on entity creation

When an event or organization is created, automatically create a `RESPONDER` edge from the creator to the new node. Add this to the existing event/org creation service functions.

### 2. Message Schemas (`backend/app/schemas/message.py`)

```python
class MessageSend(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    to_node_id: uuid.UUID | None = None       # for direct threads
    context_node_id: uuid.UUID | None = None   # for context threads

    @model_validator(mode="after")
    def exactly_one_target(self):
        if not self.to_node_id and not self.context_node_id:
            raise ValueError("Provide to_node_id (direct) or context_node_id (context)")
        if self.to_node_id and self.context_node_id:
            raise ValueError("Provide to_node_id or context_node_id, not both")
        return self

class MessageResponse(BaseModel):
    id: uuid.UUID
    from_node_id: uuid.UUID
    from_username: str | None
    to_node_id: uuid.UUID
    to_username: str | None
    context_node_id: uuid.UUID | None
    context_name: str | None        # event title or org name
    content: str
    created_at: datetime
    read_at: datetime | None

class ThreadResponse(BaseModel):
    other_node_id: uuid.UUID
    other_username: str | None
    context_node_id: uuid.UUID | None
    context_name: str | None
    last_message: MessageResponse
    unread_count: int

class ThreadListResponse(BaseModel):
    threads: list[ThreadResponse]

class ContactResponse(BaseModel):
    node_id: uuid.UUID
    username: str | None
```

### 3. Message Service (`backend/app/services/message.py`)

Core functions:

```python
async def send_message(db, from_node_id, content, *, to_node_id=None, context_node_id=None) -> Message
async def get_threads(db, user_node_id) -> list[ThreadResponse]
async def get_thread_messages(db, user_node_id, other_node_id, context_node_id=None, *, limit=50, offset=0) -> tuple[list[Message], int]
async def mark_read(db, user_node_id, other_node_id, context_node_id=None) -> int
async def get_unread_count(db, user_node_id) -> int
async def get_contacts(db, user_node_id) -> list[ContactResponse]
```

#### send_message rules

**Context thread** (context_node_id provided):
1. **Cannot message yourself** — sender must not be the responder.
2. **Context node must exist** and be type EVENT or ORGANIZATION.
3. **Must have a responder** — at least one RESPONDER edge exists for the context node.
4. **Route to responder** — look up RESPONDER edges for the context node. Use the first (oldest edge) as `to_user`. (V1 limitation: routes to one responder. Future: shared inbox.)
5. **Block check** — if the responder has blocked the sender, reject with "Cannot send message to this user." Do NOT reveal block status.
6. **Sender must be active.**

**Direct thread** (to_node_id provided):
1. **Cannot message yourself.**
2. **Must be an existing contact** — sender and recipient must have prior message exchange through any thread. This is the gate — no cold DMs.
3. **Block check** — if recipient has blocked sender, reject with generic error.
4. **Both users must be active.**

#### get_threads (inbox)

Return threads grouped by `(other_user, context_node_id)`, ordered by most recent message. Each thread includes the last message, unread count, and context info.

SQL sketch:
```sql
SELECT DISTINCT ON (other_id, context_node_id)
    CASE WHEN from_user = :me THEN to_user ELSE from_user END AS other_id,
    context_node_id,
    *,
    COUNT(*) FILTER (WHERE to_user = :me AND read_at IS NULL)
        OVER (PARTITION BY other_id, context_node_id) AS unread_count
FROM messages
WHERE from_user = :me OR to_user = :me
ORDER BY other_id, context_node_id, created_at DESC
```

Adapt to SQLAlchemy. Key: one row per thread, most recent message, unread count, ordered by recency.

#### get_thread_messages

Messages in a specific thread, chronologically. Thread identified by `(other_node_id, context_node_id)`.

```sql
SELECT * FROM messages
WHERE ((from_user = :me AND to_user = :other) OR (from_user = :other AND to_user = :me))
  AND context_node_id IS NOT DISTINCT FROM :context  -- handles NULL for direct threads
ORDER BY created_at ASC
LIMIT :limit OFFSET :offset
```

#### mark_read

Mark all unread messages FROM the other user TO the current user in the specified thread. Set `read_at = now()`. Return count marked. Called on thread open.

#### get_contacts

Distinct users this user has exchanged messages with:
```sql
SELECT DISTINCT
    CASE WHEN from_user = :me THEN to_user ELSE from_user END AS contact_id
FROM messages
WHERE from_user = :me OR to_user = :me
```

### 4. Responder Management

Add to event and organization services:

```python
async def add_responder(db, adder_node_id, entity_node_id, responder_node_id) -> Edge
async def remove_responder(db, remover_node_id, entity_node_id, responder_node_id) -> None
async def get_responders(db, entity_node_id) -> list[uuid.UUID]
```

Rules:
- Only existing responders can add/remove other responders
- Cannot remove yourself if you're the last responder
- Creates/removes a `RESPONDER` edge from responder → entity node
- Target user must be active

### 5. Block Service (extend `backend/app/services/trust.py`)

```python
async def add_block(db, blocker_node_id, target_node_id) -> Edge
async def remove_block(db, blocker_node_id, target_node_id) -> None
async def is_blocked(db, from_node_id, to_node_id) -> bool
```

`is_blocked(A, B)` returns True if B has blocked A (B is the blocker). Directional.

### 6. Message Router (`backend/app/routers/message.py`)

```
POST   /api/messages                                       — send a message
GET    /api/messages                                       — list threads (inbox)
GET    /api/messages/contacts                              — list contacts
GET    /api/messages/unread-count                           — total unread count
GET    /api/messages/thread/{other_node_id}                — thread messages (direct)
GET    /api/messages/thread/{other_node_id}?context=X      — thread messages (context)
POST   /api/messages/thread/{other_node_id}/read           — mark thread read
POST   /api/messages/thread/{other_node_id}/read?context=X — mark context thread read
```

Register in `main.py` under prefix `/api/messages`, tag `messages`.

Define `/contacts` and `/unread-count` routes BEFORE `/thread/{other_node_id}` to avoid path ambiguity.

### 7. Responder Router (extend existing routers)

Add to event router (`backend/app/routers/event.py`):
```
GET    /api/events/{node_id}/responders
POST   /api/events/{node_id}/responders                    — body: { node_id: uuid }
DELETE /api/events/{node_id}/responders/{responder_node_id}
```

Same pattern for organization router.

### 8. Block Router (extend `backend/app/routers/trust.py`)

```
POST   /api/trust/block/{target_node_id}   — block a user
DELETE /api/trust/block/{target_node_id}   — unblock a user
```

Same pattern as existing cool endpoints.

### 9. Frontend API (`frontend/src/lib/api.ts`)

Add types:

```typescript
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
```

Add API methods (both mock and real):

```typescript
messages: {
  list: () => Promise<{ threads: ThreadInfo[] }>
  getThread: (otherNodeId: string, contextNodeId?: string, limit?: number, offset?: number)
    => Promise<{ messages: MessageInfo[], total: number }>
  send: (content: string, opts: { toNodeId?: string, contextNodeId?: string })
    => Promise<MessageInfo>
  markRead: (otherNodeId: string, contextNodeId?: string) => Promise<{ marked: number }>
  unreadCount: () => Promise<{ count: number }>
  contacts: () => Promise<{ contacts: ContactInfo[] }>
}

trust: {
  // ... existing ...
  block: (nodeId: string) => Promise<void>
  unblock: (nodeId: string) => Promise<void>
}

events: {
  // ... existing ...
  getResponders: (nodeId: string) => Promise<{ responders: { node_id: string, username: string | null }[] }>
  addResponder: (nodeId: string, responderNodeId: string) => Promise<void>
  removeResponder: (nodeId: string, responderNodeId: string) => Promise<void>
}

organizations: {
  // ... existing ...  (same responder methods as events)
}
```

### 10. Frontend Pages

#### `/messages` — Inbox

All threads, ordered by most recent message. Each row shows:
- Context label (event title or org name) for context threads, or other user's username for direct threads
- Last message preview (truncated ~80 chars)
- Relative timestamp ("2h ago", "Yesterday")
- Unread indicator (dot or badge)

Clicking a thread navigates to `/messages/[other_node_id]` (direct) or `/messages/[other_node_id]?context=[context_node_id]` (context).

"New message" action shows contact list for starting direct threads.

#### `/messages/[id]` — Thread View

Messages chronologically. Header shows:
- Context thread: event/org name (linked to entity page) + other user's name
- Direct thread: other user's name (linked to profile)

Current user's messages align right, other's align left. Text input + send at bottom. On load, call `markRead`.

"Block" button in header (small, subtle). Blocking redirects to inbox.

#### Event/Org Detail Pages — "Contact" Button

On event and organization detail pages, add a "Contact" button:
1. Fetch responders for the entity
2. Navigate to `/messages/[responder_node_id]?context=[entity_node_id]`
3. Thread view loads with compose ready

Don't show the button if current user IS a responder for this entity.

#### Match Detail Page — Update CTA

On `/matches/[id]`, replace "Reach out directly" text:
- If match involves an event/org: "Contact about [name]" → navigates to context thread
- If user-user match: show matched attributes but no messaging CTA

#### Home Page — Messages Nav Card

```tsx
<Link href="/messages" className="group block rounded-xl border ...">
  <p className="text-base font-semibold ...">Messages</p>
  <p className="text-sm text-neutral-400 ...">
    Conversations about events and organizations.
  </p>
  {unreadCount > 0 && (
    <span className="... text-emerald-500 ...">{unreadCount} new</span>
  )}
</Link>
```

Fetch unread count on home page load.

## What NOT to Build

- **Real-time / WebSockets.** Polling on page load is fine.
- **Group messaging.** Threads are 1:1 (through a context or direct).
- **Media / attachments.** Text only.
- **Message editing or deletion.** Once sent, it's sent.
- **Read receipts visible to sender.** `read_at` is for unread badges only.
- **Notification emails.** Future enhancement.
- **User-to-user search or browse.** Not part of the platform model.
- **Shared inbox UI for multiple responders.** V1 routes to one responder. Multiple RESPONDER edges can exist, but the inbox is per-user.
- **Chatbot auto-response.** The model supports it (a bot user could be a responder) but don't build it now.
- **Report from message context.** Separate feature.

## Files to Create

- `backend/app/schemas/message.py`
- `backend/app/services/message.py`
- `backend/app/routers/message.py`
- `frontend/src/app/messages/page.tsx`
- `frontend/src/app/messages/[id]/page.tsx`
- Alembic migration for `context_node_id` column and `RESPONDER` edge type

## Files to Modify

- `backend/app/models/message.py` — add `context_node_id` column and relationship
- `backend/app/models/edge.py` — add `RESPONDER` to EdgeType enum
- `backend/app/services/trust.py` — add `add_block`, `remove_block`, `is_blocked`
- `backend/app/services/event.py` — add responder management, auto-create RESPONDER on creation
- `backend/app/services/organization.py` — same responder pattern
- `backend/app/routers/trust.py` — add block/unblock endpoints
- `backend/app/routers/event.py` — add responder endpoints
- `backend/app/routers/organization.py` — add responder endpoints
- `backend/app/main.py` — register message router
- `frontend/src/lib/api.ts` — add message types, mock data, API methods; add block/unblock; add responder methods
- `frontend/src/app/matches/[id]/page.tsx` — update CTA for context messaging
- `frontend/src/app/page.tsx` — add Messages nav card with unread badge
- Event and org detail pages — add "Contact" button

## Testing

### Test Fixture

```python
# alice — active user
# bob — active user, responder for event_cleanup
# carol — active user, responder for org_gardening
# dave — inactive user
# event_cleanup — event node (bob is responder)
# org_gardening — organization node (carol is responder)
```

### Test Cases

**Sending (context thread):**
1. Alice messages event_cleanup → succeeds, to_user=bob, context=event_cleanup
2. Alice messages event_cleanup again → new message in same thread
3. Alice messages org_gardening → succeeds, to_user=carol, context=org_gardening
4. Bob blocks Alice → Alice messages event_cleanup → rejected ("Cannot send message to this user")
5. Alice messages entity with no responders → rejected
6. Empty content → rejected (min_length=1)
7. Content over 2000 chars → rejected (max_length=2000)

**Sending (direct thread):**
8. Alice messages Bob directly after context exchange → succeeds, context_node_id=NULL
9. Alice messages Carol directly without prior exchange → rejected ("Must have prior contact")
10. Alice messages Dave (inactive) → rejected

**Threads/Inbox:**
11. Alice's inbox shows context threads, ordered by most recent message
12. After context + direct exchange with Bob: inbox shows 2 separate threads
13. Unread counts accurate per thread

**Contacts:**
14. After exchange with Bob through event_cleanup: Bob in Alice's contacts
15. Carol (no exchange) not in Alice's contacts
16. After exchange with Carol through org_gardening: Carol now appears

**Reading:**
17. Bob marks read in event_cleanup thread → read_at set, returns count
18. Unread count decreases
19. mark_read again → returns 0 (idempotent)

**Blocking:**
20. Bob blocks Alice → block edge created
21. Bob blocks Alice again → rejected ("Already blocked")
22. Bob unblocks Alice → edge removed, Alice can message again
23. Blocking does NOT delete existing messages
24. `is_blocked(alice, bob)` = True, `is_blocked(bob, alice)` = False

**Responders:**
25. On event creation, creator gets RESPONDER edge automatically
26. Bob adds Eve as responder → RESPONDER edge created
27. Non-responder cannot add responders → rejected
28. Cannot remove last responder → rejected

**Pagination:**
29. 25 messages in thread, limit=10 offset=0 → first 10 chronologically, total=25
