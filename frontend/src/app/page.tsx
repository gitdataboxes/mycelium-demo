"use client";

import { api, EventInfo } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useEffect, useState } from "react";

function formatDate(iso: string | null) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function Home() {
  const { user, loading, logout } = useAuth();
  const [upcomingEvents, setUpcomingEvents] = useState<EventInfo[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (user) {
      api.messages.unreadCount().then((res) => setUnreadCount(res.count)).catch(() => {});
      api.events.list(undefined, true).then((res) => {
        const sorted = [...res.events].sort((a, b) => {
          if (a.starts_at && b.starts_at) return new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime();
          if (a.starts_at) return -1;
          if (b.starts_at) return 1;
          return 0;
        });
        setUpcomingEvents(sorted.slice(0, 5));
      }).catch(() => {});
    }
  }, [user]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-6">
        <div className="max-w-md text-center">
          <h1 className="text-5xl font-bold mb-3">Mycelium</h1>
          <p className="text-lg text-gray-600 mb-2">
            Community coordination network
          </p>
          <p className="text-sm text-gray-400 mb-8 max-w-sm mx-auto">
            A resource-flow graph for your local community. Describe what you
            offer and what you seek — the network finds the connections.
          </p>
          <Link
            href="/auth"
            className="inline-block px-6 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition"
          >
            Log in
          </Link>
          <p className="text-xs text-gray-400 mt-4">
            Membership is by invitation only.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="flex items-center justify-between mb-10">
        <h1 className="text-2xl font-bold tracking-tight">Mycelium</h1>
        <button
          onClick={logout}
          className="text-sm text-neutral-400 hover:text-white transition"
        >
          Log out
        </button>
      </div>

      {upcomingEvents.length > 0 && (
        <div className="mb-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-neutral-400 uppercase tracking-wider">Upcoming Events</h2>
            <Link href="/events" className="text-xs text-neutral-500 hover:text-white transition">View all</Link>
          </div>
          <div className="grid gap-3">
            {upcomingEvents.map((evt) => (
              <Link
                key={evt.node_id}
                href={`/events/${evt.node_id}`}
                className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-white group-hover:text-emerald-400 transition-colors">
                      {evt.title}
                    </p>
                    <div className="flex flex-wrap gap-3 text-xs text-neutral-500 mt-1">
                      {evt.starts_at && <span>{formatDate(evt.starts_at)}</span>}
                      {evt.location && <span>{evt.location}</span>}
                      {evt.graph_distance !== null && evt.graph_distance > 0 && (
                        <span>{evt.graph_distance} {evt.graph_distance === 1 ? "hop" : "hops"}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {evt.urgency === "spontaneous" && (
                      <span className="text-xs text-amber-500 border border-amber-800 rounded px-2 py-0.5">
                        spontaneous
                      </span>
                    )}
                    {evt.is_participant && (
                      <span className="text-xs text-emerald-500 border border-emerald-800 rounded px-2 py-0.5">
                        joined
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      <nav className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          href="/messages"
          className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
        >
          <div className="flex items-center justify-between mb-1">
            <p className="text-base font-semibold text-white group-hover:text-emerald-400 transition-colors">
              Messages
            </p>
            {unreadCount > 0 && (
              <span className="text-xs font-medium text-emerald-500">
                {unreadCount} new
              </span>
            )}
          </div>
          <p className="text-sm text-neutral-400 leading-relaxed">
            Conversations about events and organizations.
          </p>
        </Link>
        <Link
          href="/matches"
          className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
        >
          <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
            Connections
          </p>
          <p className="text-sm text-neutral-400 leading-relaxed">
            See who the network thinks you should meet.
          </p>
        </Link>
        <Link
          href="/profile"
          className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
        >
          <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
            My Profile
          </p>
          <p className="text-sm text-neutral-400 leading-relaxed">
            Edit your membrane — what you offer and what you seek.
          </p>
        </Link>
        <Link
          href="/signals"
          className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
        >
          <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
            Signals
          </p>
          <p className="text-sm text-neutral-400 leading-relaxed">
            Post what&apos;s alive for you right now — time-bound offers and needs.
          </p>
        </Link>
        <Link
          href="/network"
          className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
        >
          <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
            My Network
          </p>
          <p className="text-sm text-neutral-400 leading-relaxed">
            Vouch for people, view your trust connections.
          </p>
        </Link>
        <Link
          href="/organizations"
          className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
        >
          <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
            Organizations
          </p>
          <p className="text-sm text-neutral-400 leading-relaxed">
            Browse and join community groups.
          </p>
        </Link>
        <Link
          href="/events"
          className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
        >
          <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
            Events
          </p>
          <p className="text-sm text-neutral-400 leading-relaxed">
            Discover and create community gatherings.
          </p>
        </Link>
      </nav>
    </div>
  );
}
