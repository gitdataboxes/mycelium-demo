#!/usr/bin/env python3
"""Seed a Mycelium network with rich synthetic data.

Usage (from repo root):
    python3 seed_synthetic.py

Creates a realistic community with ~15 users, organizations, events,
trust relationships, messages, membrane entries, signals, and match history.

Uses fictional people and example.com addresses. Refuses to seed a populated database.
Run migrations first; embeddings are not generated and match scores are illustrative.
"""
import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from sqlalchemy import select

from app.database import Base, async_session, engine
from app.models.community import Community
from app.models.edge import Edge, EdgeType
from app.models.event import Event, EventUrgency
from app.models.match import MatchHistory
from app.models.message import Message
from app.models.node import Node, NodeType
from app.models.organization import Organization
from app.models.profile import AttributeDirection, MembraneEntry
from app.models.signal import Signal
from app.models.user import User

random.seed(42)  # reproducible

NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Persona definitions — a neighborhood creative/mutual-aid community
# ---------------------------------------------------------------------------

USERS = [
    {
        "email": "maya@example.com",
        "username": "maya",
        "name": "Maya Chen",
        "inputs": [
            "Looking for collaborators on community mural projects",
            "Need help learning screen printing techniques",
        ],
        "outputs": [
            "I teach watercolor and acrylic painting workshops",
            "Graphic design for community flyers and posters",
        ],
    },
    {
        "email": "dex@example.com",
        "username": "dex",
        "name": "Dex Okafor",
        "inputs": [
            "Seeking a shared workshop space for woodworking",
            "Want to learn about mycology and mushroom cultivation",
        ],
        "outputs": [
            "Custom furniture building and repair",
            "I can teach basic carpentry and joinery skills",
        ],
    },
    {
        "email": "river@example.com",
        "username": "river",
        "name": "River Vasquez",
        "inputs": [
            "Looking for musicians to jam with — folk, jazz, experimental",
            "Need a quiet space for music recording sessions",
        ],
        "outputs": [
            "Guitar and ukulele lessons for beginners",
            "I organize neighborhood open-mic nights",
            "Sound engineering for small events",
        ],
    },
    {
        "email": "lia@example.com",
        "username": "lia",
        "name": "Lia Johansson",
        "inputs": [
            "Seeking volunteers for weekend park cleanups",
            "Need someone to help maintain the community garden irrigation",
        ],
        "outputs": [
            "Organic gardening mentorship — soil prep, composting, seasonal planting",
            "Free seedlings and plant starts every spring",
        ],
    },
    {
        "email": "sam@example.com",
        "username": "sam",
        "name": "Sam Reyes",
        "inputs": [
            "Looking for a study group for data science and ML",
            "Need advice on setting up a home server",
        ],
        "outputs": [
            "Python and web development tutoring",
            "I help neighbors troubleshoot tech issues for free",
            "Can set up simple websites for community projects",
        ],
    },
    {
        "email": "juno@example.com",
        "username": "juno",
        "name": "Juno Park",
        "inputs": [
            "Want to learn pottery and ceramics",
            "Seeking people interested in zine-making",
        ],
        "outputs": [
            "Letterpress printing — I have a small press at home",
            "Book binding workshops",
        ],
    },
    {
        "email": "kai@example.com",
        "username": "kai",
        "name": "Kai Nakamura",
        "inputs": [
            "Looking for partners for a neighborhood tool library",
            "Need help organizing a repair cafe",
        ],
        "outputs": [
            "Bicycle repair and maintenance — I'll fix your bike for free",
            "Small electronics repair (phones, laptops, appliances)",
        ],
    },
    {
        "email": "sol@example.com",
        "username": "sol",
        "name": "Sol Abramov",
        "inputs": [
            "Searching for a community darkroom for film photography",
            "Looking for people to start a neighborhood podcast",
        ],
        "outputs": [
            "Portrait and event photography",
            "Video editing for community projects",
        ],
    },
    {
        "email": "wren@example.com",
        "username": "wren",
        "name": "Wren Oduya",
        "inputs": [
            "Need fresh herbs and vegetables — happy to trade",
            "Looking for someone to teach fermentation (kimchi, kombucha)",
        ],
        "outputs": [
            "Sourdough bread — I bake weekly and share with neighbors",
            "I teach cooking classes focused on West African cuisine",
        ],
    },
    {
        "email": "arden@example.com",
        "username": "arden",
        "name": "Arden Kowalski",
        "inputs": [
            "Seeking collaborators for a community land trust proposal",
            "Need legal advice on cooperative incorporation",
        ],
        "outputs": [
            "Grant writing for neighborhood organizations",
            "Community organizing and meeting facilitation",
            "Conflict mediation and restorative justice circles",
        ],
    },
    {
        "email": "iris@example.com",
        "username": "iris",
        "name": "Iris Delgado",
        "inputs": [
            "Looking for a dance partner — salsa, swing, or tango",
            "Need a ride-share buddy for weekend farmers markets",
        ],
        "outputs": [
            "Yoga and movement classes in the park",
            "Bilingual (EN/ES) translation for community events",
        ],
    },
    {
        "email": "finn@example.com",
        "username": "finn",
        "name": "Finn Larsen",
        "inputs": [
            "Want to learn about permaculture design",
            "Looking for people to share a CSA box with",
        ],
        "outputs": [
            "Beekeeping mentorship — I maintain three hives",
            "Honey and beeswax products to share/trade",
        ],
    },
    {
        "email": "cleo@example.com",
        "username": "cleo",
        "name": "Cleo Mwangi",
        "inputs": [
            "Seeking a co-working buddy — accountability partnership",
            "Need someone to practice conversational French with",
        ],
        "outputs": [
            "Resume and cover letter review",
            "Career coaching and interview prep",
            "I host monthly skill-swap potlucks",
        ],
    },
    {
        "email": "tash@example.com",
        "username": "tash",
        "name": "Tash Khoury",
        "inputs": [
            "Looking for someone to help with home weatherization",
            "Need childcare co-op partners for weekend activities",
        ],
        "outputs": [
            "Sewing and clothing repair — I mend for free",
            "Kids' art and craft workshops",
        ],
    },
    {
        "email": "ozzy@example.com",
        "username": "ozzy",
        "name": "Ozzy Brennan",
        "inputs": [
            "Seeking advice on backyard composting systems",
            "Want to learn basic plumbing and home repair",
        ],
        "outputs": [
            "I do free tax prep for neighbors during tax season",
            "Financial literacy workshops for young adults",
        ],
    },
]

ORGANIZATIONS = [
    {
        "name": "Rootstock Community Garden",
        "description": "A shared urban garden space where neighbors grow food together. "
        "We maintain 40 raised beds, a tool shed, a composting station, and a "
        "small greenhouse. Open to all skill levels.",
        "inputs": [
            "Volunteers for weekly weeding and watering shifts",
            "Donations of seeds, soil amendments, and garden tools",
        ],
        "outputs": [
            "Free plot assignments for community members",
            "Monthly gardening workshops and harvest shares",
        ],
    },
    {
        "name": "Spark Maker Space",
        "description": "A collectively-run workshop with woodworking tools, 3D printers, "
        "a sewing station, electronics bench, and a small darkroom. "
        "Membership is by vouch.",
        "inputs": [
            "Tool donations and maintenance volunteers",
            "Members willing to lead intro safety workshops",
        ],
        "outputs": [
            "Access to shared tools and equipment",
            "Weekly open-shop hours for the community",
            "Project mentorship from experienced makers",
        ],
    },
    {
        "name": "Neighborhood Mutual Aid Network",
        "description": "Coordinating resource sharing, rides, meals, and support for "
        "neighbors in need. No means-testing, no strings attached.",
        "inputs": [
            "Drivers for grocery and pharmacy runs",
            "Meal train volunteers for families in transition",
            "People willing to be on-call for emergency support",
        ],
        "outputs": [
            "Emergency grocery and supply deliveries",
            "Coordination hub for community needs",
            "Warm referrals to social services",
        ],
    },
    {
        "name": "Mycelium Arts Collective",
        "description": "A group of neighborhood artists collaborating on public art, "
        "gallery shows, and community workshops. All mediums welcome.",
        "inputs": [
            "Studio space or walls available for murals",
            "Funding and sponsorship for public art installations",
        ],
        "outputs": [
            "Free community art workshops monthly",
            "Curated neighborhood gallery walks",
            "Artist-in-residence mentorship program",
        ],
    },
    {
        "name": "Fix-It Collective",
        "description": "Monthly repair cafe and permanent tool library. Bring your broken "
        "stuff — bikes, clothes, electronics, small appliances — and we'll "
        "fix it together.",
        "inputs": [
            "Repair volunteers with any skill level",
            "Spare parts, sewing supplies, and electronic components",
        ],
        "outputs": [
            "Free repairs at monthly repair cafes",
            "Tool library lending — borrow what you need",
            "Repair skill workshops (sewing, soldering, bike tune-ups)",
        ],
    },
]

EVENTS = [
    {
        "title": "Spring Seedling Swap",
        "description": "Bring your extra seedlings, seeds, and plant starts to swap "
        "with neighbors. Master gardeners on hand to answer questions. "
        "Light refreshments provided.",
        "location": "Rootstock Community Garden",
        "starts_at": NOW + timedelta(days=5, hours=10),
        "ends_at": NOW + timedelta(days=5, hours=13),
        "urgency": EventUrgency.STANDARD,
    },
    {
        "title": "Open Mic Night at the Gazebo",
        "description": "Acoustic music, poetry, comedy, storytelling — all welcome. "
        "Bring a chair and something to share. PA system provided.",
        "location": "Westfield Park Gazebo",
        "starts_at": NOW + timedelta(days=12, hours=19),
        "ends_at": NOW + timedelta(days=12, hours=22),
        "urgency": EventUrgency.STANDARD,
    },
    {
        "title": "Repair Cafe #17",
        "description": "Bring your broken items! We have stations for bikes, electronics, "
        "clothing, and small appliances. Learn to fix it yourself or let our "
        "volunteers help.",
        "location": "Spark Maker Space",
        "starts_at": NOW + timedelta(days=8, hours=11),
        "ends_at": NOW + timedelta(days=8, hours=16),
        "urgency": EventUrgency.STANDARD,
    },
    {
        "title": "Sourdough & Fermentation Workshop",
        "description": "Learn to make sourdough starter, kimchi, and kombucha from scratch. "
        "Take home your own starter culture. All supplies provided.",
        "location": "Neighborhood Community Center, Kitchen",
        "starts_at": NOW + timedelta(days=18, hours=14),
        "ends_at": NOW + timedelta(days=18, hours=17),
        "urgency": EventUrgency.STANDARD,
    },
    {
        "title": "Emergency Sidewalk Chalk Rally",
        "description": "Come chalk up the neighborhood with positive messages! "
        "All ages welcome. Chalk provided, rain date TBD.",
        "location": "Corner of Oak & 5th",
        "starts_at": NOW + timedelta(days=1, hours=16),
        "ends_at": NOW + timedelta(days=1, hours=18),
        "urgency": EventUrgency.SPONTANEOUS,
    },
    {
        "title": "Community Land Trust Info Session",
        "description": "Learn about cooperative land ownership and how our neighborhood "
        "can take control of housing. Panel with speakers from successful CLTs.",
        "location": "Public Library, Room B",
        "starts_at": NOW + timedelta(days=22, hours=18, minutes=30),
        "ends_at": NOW + timedelta(days=22, hours=20, minutes=30),
        "urgency": EventUrgency.STANDARD,
    },
    {
        "title": "Skill-Swap Potluck",
        "description": "Bring a dish to share and a skill to teach! 15-minute micro-workshops "
        "run all evening. Past topics: origami, lockpicking, hand massage, "
        "composting, bread braiding.",
        "location": "Cleo's backyard (address in DM)",
        "starts_at": NOW + timedelta(days=15, hours=17),
        "ends_at": NOW + timedelta(days=15, hours=21),
        "urgency": EventUrgency.STANDARD,
    },
    {
        "title": "Bike Tune-Up Pop-Up",
        "description": "Free basic bike tune-ups — brakes, gears, tires, chain lube. "
        "Bring your bike and learn to maintain it yourself.",
        "location": "Parking lot behind Fix-It Collective",
        "starts_at": NOW + timedelta(days=3, hours=9),
        "ends_at": NOW + timedelta(days=3, hours=13),
        "urgency": EventUrgency.SPONTANEOUS,
    },
]

# ---------------------------------------------------------------------------
# Vouch topology — defines who vouched whom (by index into USERS list).
# This creates a realistic trust web: maya is the root, she vouches a few
# people, who vouch others, creating depth.
# ---------------------------------------------------------------------------

VOUCHES = [
    # Maya (0) is the root, vouches early members
    (0, 1),   # maya -> dex
    (0, 2),   # maya -> river
    (0, 3),   # maya -> lia
    (0, 9),   # maya -> arden
    # Dex (1) vouches makers
    (1, 6),   # dex -> kai
    (1, 5),   # dex -> juno
    # River (2) vouches creative people
    (2, 7),   # river -> sol
    (2, 10),  # river -> iris
    # Lia (3) vouches gardeners
    (3, 11),  # lia -> finn
    (3, 8),   # lia -> wren
    # Arden (9) vouches community organizers
    (9, 12),  # arden -> cleo
    (9, 4),   # arden -> sam
    # Second-degree vouches (cross-linking the network)
    (4, 14),  # sam -> ozzy
    (12, 13), # cleo -> tash
    (6, 1),   # kai -> dex (reciprocal)
    (5, 0),   # juno -> maya (reciprocal)
    (8, 3),   # wren -> lia (reciprocal)
    (7, 2),   # sol -> river (reciprocal)
    (11, 8),  # finn -> wren
    (10, 12), # iris -> cleo
    (13, 9),  # tash -> arden (reciprocal)
    (14, 4),  # ozzy -> sam (reciprocal)
]

# Org memberships: (user_index, org_index)
ORG_MEMBERS = [
    # Rootstock Community Garden
    (3, 0), (11, 0), (8, 0), (0, 0), (14, 0),
    # Spark Maker Space
    (1, 1), (6, 1), (5, 1), (7, 1), (4, 1),
    # Mutual Aid Network
    (9, 2), (12, 2), (13, 2), (10, 2), (3, 2), (8, 2),
    # Arts Collective
    (0, 3), (5, 3), (7, 3), (2, 3), (10, 3),
    # Fix-It Collective
    (6, 4), (1, 4), (13, 4), (4, 4),
]

# Org hosts events: (org_index, event_index)
ORG_HOSTS = [
    (0, 0),  # Garden hosts Seedling Swap
    (4, 2),  # Fix-It hosts Repair Cafe
    (3, 4),  # Arts Collective hosts Chalk Rally
    (4, 7),  # Fix-It hosts Bike Tune-Up
]

# Event participants: (user_index, event_index)
EVENT_PARTICIPANTS = [
    # Seedling Swap
    (3, 0), (11, 0), (8, 0), (0, 0), (14, 0), (1, 0),
    # Open Mic Night
    (2, 1), (10, 1), (0, 1), (7, 1), (12, 1), (5, 1), (9, 1),
    # Repair Cafe
    (6, 2), (1, 2), (4, 2), (13, 2), (14, 2),
    # Sourdough Workshop
    (8, 3), (3, 3), (11, 3), (12, 3), (10, 3),
    # Chalk Rally
    (0, 4), (5, 4), (13, 4), (2, 4), (10, 4), (7, 4),
    # CLT Info Session
    (9, 5), (12, 5), (4, 5), (14, 5), (3, 5),
    # Skill-Swap Potluck
    (12, 6), (0, 6), (1, 6), (8, 6), (6, 6), (10, 6), (13, 6), (2, 6),
    # Bike Tune-Up
    (6, 7), (1, 7), (14, 7), (11, 7),
]

# Coolings: (source_index, target_index) — personal distance
COOLINGS = [
    (7, 14),   # sol cooled on ozzy
    (11, 4),   # finn cooled on sam
]

# Blocks: (source_index, target_index)
BLOCKS = [
    (13, 7),   # tash blocked sol
]

# Responders: (user_index, context_node — 'org' or 'event', context_index)
RESPONDERS = [
    (4, "org", 1),    # sam responds for Spark Maker Space
    (9, "org", 2),    # arden responds for Mutual Aid
    (6, "org", 4),    # kai responds for Fix-It
    (3, "org", 0),    # lia responds for Garden
    (0, "org", 3),    # maya responds for Arts Collective
    (2, "event", 1),  # river responds for Open Mic
    (8, "event", 3),  # wren responds for Sourdough Workshop
    (12, "event", 6), # cleo responds for Skill-Swap Potluck
]

# Message threads
MESSAGES = [
    # Maya and Juno discussing zine-making
    {
        "from": 0, "to": 5, "context": None,
        "messages": [
            ("Hey Juno! I saw your letterpress work at the last gallery walk — stunning. Would you want to collaborate on a zine about the neighborhood?", -3),
            ("Maya! I'd love that. I've been wanting to do a zine project. What are you thinking — interviews, art, stories?", -2.8),
            ("All of the above! Maybe we could feature different community members and the skills they share. Kind of a directory but beautiful.", -2.5),
            ("I'm in. Let's sketch it out at the next potluck?", -2.3),
        ],
    },
    # Kai and Dex about the tool library
    {
        "from": 6, "to": 1, "context": ("org", 4),
        "messages": [
            ("Dex, I've been thinking about expanding the tool library. We have great woodworking stuff but almost no plumbing tools.", -5),
            ("Good call. I actually have some extras I've been meaning to donate. A pipe wrench set and a basin wrench at least.", -4.5),
            ("Perfect. I'll make labels and add them to the inventory spreadsheet. Can you drop them off Saturday?", -4),
            ("Will do. Also — have you thought about doing a plumbing basics workshop? I keep getting asked.", -3.5),
            ("That's a great idea. Let me put it on the agenda for the next Fix-It meeting.", -3),
        ],
    },
    # Arden and Cleo about the CLT
    {
        "from": 9, "to": 12, "context": None,
        "messages": [
            ("Cleo, I got confirmation from the Dudley Street CLT folks — they'll send a speaker for our info session!", -7),
            ("Amazing! That's going to be so valuable. How many people do we have signed up?", -6.5),
            ("About 20 so far. Sam said he'd help set up a simple website for the initiative too.", -6),
            ("Let's make sure to record it for people who can't make it.", -5.8),
        ],
    },
    # Wren and Lia trading
    {
        "from": 8, "to": 3, "context": ("org", 0),
        "messages": [
            ("Lia, my sourdough loaves came out great this week. Want to trade for some of your lettuce?", -1.5),
            ("Always! I just harvested a bunch of arugula too. Meet me at the garden shed tomorrow morning?", -1),
            ("Perfect, I'll bring two loaves. See you at 9?", -0.8),
        ],
    },
    # Sam and Ozzy about tax prep
    {
        "from": 4, "to": 14, "context": None,
        "messages": [
            ("Hey Ozzy, a few folks have asked me if you're doing free tax prep again this year.", -10),
            ("Yep! Starting in February. I can handle basic returns, W-2s, standard deductions. I'll post about it.", -9),
            ("Cool. I'll add a page for it on the mutual aid site.", -8.5),
        ],
    },
    # River and Sol about the open mic
    {
        "from": 2, "to": 7, "context": ("event", 1),
        "messages": [
            ("Sol, can you do photos at the next open mic? Last time your shots were incredible.", -2),
            ("Thanks! Yeah I'm down. Want me to set up a little portrait station too?", -1.5),
            ("That would be awesome. People loved that at the summer fest.", -1),
        ],
    },
    # Iris and Cleo — French practice
    {
        "from": 10, "to": 12, "context": None,
        "messages": [
            ("Cleo! I saw you're looking for a French conversation partner. I'm not fluent but I'm B2 and would love to practice.", -4),
            ("Oh perfect! Want to do coffee and French once a week? Maybe Thursdays?", -3.5),
            ("Thursdays work great. There's a cafe on Elm that's usually quiet in the afternoon.", -3),
        ],
    },
]

# Active signals
SIGNALS = [
    {"user": 6, "direction": "output", "content": "Free bike tune-ups this Saturday 9am-1pm behind the Fix-It space!", "expires_days": 4},
    {"user": 8, "direction": "output", "content": "Extra sourdough loaves this week — first come first served, DM me", "expires_days": 2},
    {"user": 0, "direction": "input", "content": "Urgently need a projector for the CLT info session on the 25th", "expires_days": 20},
    {"user": 12, "direction": "output", "content": "Hosting skill-swap potluck in two weeks — DM for address", "expires_days": 14},
    {"user": 3, "direction": "output", "content": "Tomato and pepper seedlings ready for pickup at the garden shed", "expires_days": 7},
    {"user": 1, "direction": "input", "content": "Anyone have a belt sander I can borrow this weekend?", "expires_days": 3},
    {"user": 9, "direction": "input", "content": "Looking for a lawyer willing to do pro-bono review of our co-op bylaws", "expires_days": 30},
]


async def seed_synthetic():

    async with async_session() as db:
        # ── Check for existing data ──────────────────────────────────
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("Database already has users. To re-seed, drop and recreate the DB first.")
            print("Use a fresh demo database; existing data has not been changed.")
            return

        # ── Community ────────────────────────────────────────────────
        community = Community(
            name="Westfield Neighborhood Network",
            description="A mutual aid and skill-sharing network for the Westfield neighborhood. "
            "We connect neighbors who have something to offer with neighbors who need something.",
            code_of_conduct="Be kind. Assume good intent. Show up when you say you will. "
            "Respect boundaries. Take accountability. Care for the commons.",
        )
        db.add(community)
        await db.flush()
        print(f"Created community: {community.name}")

        # ── Users ────────────────────────────────────────────────────
        user_nodes: list[Node] = []
        user_records: list[User] = []

        for u in USERS:
            node = Node(community_id=community.id, type=NodeType.USER)
            db.add(node)
            await db.flush()

            user = User(
                node_id=node.id,
                email=u["email"],
                username=u["username"],
                name=u["name"],
                is_active=True,
            )
            db.add(user)
            user_nodes.append(node)
            user_records.append(user)

        await db.flush()
        print(f"Created {len(user_records)} users")

        # ── User membrane entries ────────────────────────────────────
        entry_count = 0
        # We'll collect all membrane entries for match generation later
        user_membrane_ids: dict[int, list[tuple[uuid.UUID, str, str]]] = {}  # user_idx -> [(id, direction, content)]

        for i, u in enumerate(USERS):
            user_membrane_ids[i] = []
            for text in u.get("inputs", []):
                entry = MembraneEntry(
                    node_id=user_nodes[i].id,
                    direction=AttributeDirection.INPUT,
                    content=text,
                )
                db.add(entry)
                await db.flush()
                user_membrane_ids[i].append((entry.id, "input", text))
                entry_count += 1
            for text in u.get("outputs", []):
                entry = MembraneEntry(
                    node_id=user_nodes[i].id,
                    direction=AttributeDirection.OUTPUT,
                    content=text,
                )
                db.add(entry)
                await db.flush()
                user_membrane_ids[i].append((entry.id, "output", text))
                entry_count += 1

        print(f"Created {entry_count} user membrane entries")

        # ── Organizations ────────────────────────────────────────────
        org_nodes: list[Node] = []
        org_records: list[Organization] = []

        for o in ORGANIZATIONS:
            node = Node(community_id=community.id, type=NodeType.ORGANIZATION)
            db.add(node)
            await db.flush()

            org = Organization(
                node_id=node.id,
                name=o["name"],
                description=o["description"],
            )
            db.add(org)
            org_nodes.append(node)
            org_records.append(org)

            # Org membrane entries
            for text in o.get("inputs", []):
                db.add(MembraneEntry(
                    node_id=node.id,
                    direction=AttributeDirection.INPUT,
                    content=text,
                ))
            for text in o.get("outputs", []):
                db.add(MembraneEntry(
                    node_id=node.id,
                    direction=AttributeDirection.OUTPUT,
                    content=text,
                ))

        await db.flush()
        print(f"Created {len(org_records)} organizations with membrane entries")

        # ── Events ───────────────────────────────────────────────────
        event_nodes: list[Node] = []
        event_records: list[Event] = []

        for e in EVENTS:
            node = Node(community_id=community.id, type=NodeType.EVENT)
            db.add(node)
            await db.flush()

            event = Event(
                node_id=node.id,
                title=e["title"],
                description=e["description"],
                location=e["location"],
                starts_at=e["starts_at"],
                ends_at=e["ends_at"],
                urgency=e["urgency"],
            )
            db.add(event)
            event_nodes.append(node)
            event_records.append(event)

        await db.flush()
        print(f"Created {len(event_records)} events")

        # ── Edges: vouches ───────────────────────────────────────────
        vouch_dates_start = NOW - timedelta(days=60)
        for idx, (src, tgt) in enumerate(VOUCHES):
            # Stagger vouch creation times to look natural
            created = vouch_dates_start + timedelta(days=idx * 2.5, hours=random.randint(0, 12))
            edge = Edge(
                source_node_id=user_nodes[src].id,
                target_node_id=user_nodes[tgt].id,
                type=EdgeType.VOUCH,
            )
            db.add(edge)

        await db.flush()
        print(f"Created {len(VOUCHES)} vouch edges")

        # ── Edges: org memberships ───────────────────────────────────
        for user_idx, org_idx in ORG_MEMBERS:
            db.add(Edge(
                source_node_id=user_nodes[user_idx].id,
                target_node_id=org_nodes[org_idx].id,
                type=EdgeType.MEMBER,
            ))
        await db.flush()
        print(f"Created {len(ORG_MEMBERS)} org membership edges")

        # ── Edges: org hosts event ───────────────────────────────────
        for org_idx, event_idx in ORG_HOSTS:
            db.add(Edge(
                source_node_id=org_nodes[org_idx].id,
                target_node_id=event_nodes[event_idx].id,
                type=EdgeType.HOST,
            ))
        await db.flush()
        print(f"Created {len(ORG_HOSTS)} host edges")

        # ── Edges: event participants ────────────────────────────────
        for user_idx, event_idx in EVENT_PARTICIPANTS:
            db.add(Edge(
                source_node_id=user_nodes[user_idx].id,
                target_node_id=event_nodes[event_idx].id,
                type=EdgeType.PARTICIPANT,
            ))
        await db.flush()
        print(f"Created {len(EVENT_PARTICIPANTS)} participant edges")

        # ── Edges: coolings ──────────────────────────────────────────
        for src, tgt in COOLINGS:
            db.add(Edge(
                source_node_id=user_nodes[src].id,
                target_node_id=user_nodes[tgt].id,
                type=EdgeType.COOL,
            ))
        await db.flush()
        print(f"Created {len(COOLINGS)} cooling edges")

        # ── Edges: blocks ────────────────────────────────────────────
        for src, tgt in BLOCKS:
            db.add(Edge(
                source_node_id=user_nodes[src].id,
                target_node_id=user_nodes[tgt].id,
                type=EdgeType.BLOCK,
            ))
        await db.flush()
        print(f"Created {len(BLOCKS)} block edges")

        # ── Edges: responders ────────────────────────────────────────
        for user_idx, ctx_type, ctx_idx in RESPONDERS:
            context_node = org_nodes[ctx_idx] if ctx_type == "org" else event_nodes[ctx_idx]
            db.add(Edge(
                source_node_id=user_nodes[user_idx].id,
                target_node_id=context_node.id,
                type=EdgeType.RESPONDER,
            ))
        await db.flush()
        print(f"Created {len(RESPONDERS)} responder edges")

        # ── Messages ─────────────────────────────────────────────────
        msg_count = 0
        for thread in MESSAGES:
            from_idx = thread["from"]
            to_idx = thread["to"]
            ctx = thread["context"]
            context_node_id = None
            if ctx:
                ctx_type, ctx_idx = ctx
                context_node_id = (org_nodes[ctx_idx].id if ctx_type == "org"
                                   else event_nodes[ctx_idx].id)

            for i, (text, days_ago) in enumerate(thread["messages"]):
                # Alternate sender/recipient for conversation flow
                if i % 2 == 0:
                    sender, recipient = from_idx, to_idx
                else:
                    sender, recipient = to_idx, from_idx

                created_at = NOW + timedelta(days=days_ago)
                # Mark older messages as read
                read_at = created_at + timedelta(hours=random.randint(1, 8)) if days_ago < -1 else None

                db.add(Message(
                    from_user=user_nodes[sender].id,
                    to_user=user_nodes[recipient].id,
                    context_node_id=context_node_id,
                    content=text,
                    created_at=created_at,
                    read_at=read_at,
                ))
                msg_count += 1

        await db.flush()
        print(f"Created {msg_count} messages across {len(MESSAGES)} threads")

        # ── Signals ──────────────────────────────────────────────────
        for s in SIGNALS:
            db.add(Signal(
                node_id=user_nodes[s["user"]].id,
                direction=AttributeDirection(s["direction"]),
                content=s["content"],
                expires_at=NOW + timedelta(days=s["expires_days"]),
            ))
        await db.flush()
        print(f"Created {len(SIGNALS)} active signals")

        # ── Match history (synthetic past matches) ───────────────────
        # Create plausible matches: output from one user matched to input of another
        match_pairs = [
            # dex's furniture repair matched wren's need for someone to trade with
            (1, 8),
            # sam's python tutoring matched kai's need for tool library help
            (4, 6),
            # lia's gardening mentorship matched finn's permaculture interest
            (3, 11),
            # maya's graphic design matched arden's grant writing
            (0, 9),
            # river's sound engineering matched sol's podcast interest
            (2, 7),
            # kai's bike repair matched ozzy's need for home repair advice
            (6, 14),
            # cleo's career coaching matched iris's translation services
            (12, 10),
            # wren's cooking classes matched tash's kids activities
            (8, 13),
        ]
        match_count = 0
        for a_idx, b_idx in match_pairs:
            a_entries = user_membrane_ids.get(a_idx, [])
            b_entries = user_membrane_ids.get(b_idx, [])
            # Find an output from a and an input from b
            a_outputs = [(eid, d, c) for eid, d, c in a_entries if d == "output"]
            b_inputs = [(eid, d, c) for eid, d, c in b_entries if d == "input"]
            if a_outputs and b_inputs:
                a_out = a_outputs[0]
                b_in = b_inputs[0]
                db.add(MatchHistory(
                    node_a_id=user_nodes[a_idx].id,
                    node_b_id=user_nodes[b_idx].id,
                    attribute_a_id=a_out[0],
                    attribute_b_id=b_in[0],
                    attribute_a_type="membrane",
                    attribute_b_type="membrane",
                    similarity=round(random.uniform(0.65, 0.92), 4),
                    digest_sent_at=NOW - timedelta(days=random.randint(1, 14)),
                ))
                match_count += 1

        await db.flush()
        print(f"Created {match_count} match history entries")

        # ── Commit everything ────────────────────────────────────────
        await db.commit()

    print()
    print("=" * 60)
    print("Synthetic data seeded successfully!")
    print()
    print("Community:     Westfield Neighborhood Network")
    print(f"Users:         {len(USERS)}")
    print(f"Organizations: {len(ORGANIZATIONS)}")
    print(f"Events:        {len(EVENTS)}")
    print(f"Vouches:       {len(VOUCHES)}")
    print(f"Messages:      {msg_count} messages in {len(MESSAGES)} threads")
    print(f"Signals:       {len(SIGNALS)}")
    print(f"Matches:       {match_count}")
    print()
    print("To log in as any user, request a magic link for their email.")
    print("Root user: maya@example.com (the trust graph root)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_synthetic())
