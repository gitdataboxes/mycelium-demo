"use client";

import { api, EventInfo } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

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

export default function EventsPage() {
  const { user, loading: authLoading } = useAuth();
  const [events, setEvents] = useState<EventInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [upcomingOnly, setUpcomingOnly] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", location: "", starts_at: "", ends_at: "", urgency: "standard" });

  const loadEvents = useCallback(async () => {
    try {
      const res = await api.events.list(search || undefined, upcomingOnly);
      setEvents(res.events);
    } finally {
      setLoading(false);
    }
  }, [search, upcomingOnly]);

  useEffect(() => {
    if (user) loadEvents();
  }, [user, loadEvents]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      await api.events.create({
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        location: form.location.trim() || undefined,
        starts_at: form.starts_at || undefined,
        ends_at: form.ends_at || undefined,
        urgency: form.urgency,
      });
      setForm({ title: "", description: "", location: "", starts_at: "", ends_at: "", urgency: "standard" });
      setShowCreate(false);
      loadEvents();
    } finally {
      setCreating(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p>You need to log in first.</p>
        <Link href="/auth" className="underline">Log in</Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <Link href="/" className="text-2xl font-bold hover:opacity-70">Mycelium</Link>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Events</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 transition"
        >
          {showCreate ? "Cancel" : "Create"}
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="mb-6 p-4 bg-neutral-900/60 border border-neutral-800 rounded-xl space-y-3">
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Event title"
            className="w-full px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
            autoFocus
          />
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Description (optional)"
            rows={2}
            className="w-full px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500 resize-none"
          />
          <input
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            placeholder="Location (optional)"
            className="w-full px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
          />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-neutral-500 mb-1">Starts</label>
              <input
                type="datetime-local"
                value={form.starts_at}
                onChange={(e) => setForm({ ...form, starts_at: e.target.value })}
                className="w-full px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
              />
            </div>
            <div>
              <label className="block text-xs text-neutral-500 mb-1">Ends</label>
              <input
                type="datetime-local"
                value={form.ends_at}
                onChange={(e) => setForm({ ...form, ends_at: e.target.value })}
                className="w-full px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
              />
            </div>
          </div>
          <select
            value={form.urgency}
            onChange={(e) => setForm({ ...form, urgency: e.target.value })}
            className="px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm"
          >
            <option value="standard">Standard</option>
            <option value="spontaneous">Spontaneous</option>
          </select>
          <div>
            <button
              type="submit"
              disabled={creating || !form.title.trim()}
              className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50 transition"
            >
              Create Event
            </button>
          </div>
        </form>
      )}

      <div className="flex gap-3 mb-6">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search events..."
          className="flex-1 px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
        />
        <label className="flex items-center gap-2 text-sm text-neutral-400">
          <input
            type="checkbox"
            checked={upcomingOnly}
            onChange={(e) => setUpcomingOnly(e.target.checked)}
            className="rounded"
          />
          Upcoming
        </label>
      </div>

      {events.length === 0 ? (
        <p className="text-sm text-neutral-400">No events found.</p>
      ) : (
        <>
          <div className="grid gap-4">
            {events.filter(e => e.graph_distance !== null).map((evt) => (
              <Link
                key={evt.node_id}
                href={`/events/${evt.node_id}`}
                className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
                      {evt.title}
                    </p>
                    {evt.description && (
                      <p className="text-sm text-neutral-400 leading-relaxed mb-2">{evt.description}</p>
                    )}
                    <div className="flex flex-wrap gap-3 text-xs text-neutral-500">
                      {evt.starts_at && <span>{formatDate(evt.starts_at)}</span>}
                      {evt.location && <span>{evt.location}</span>}
                      <span>{evt.participant_count} {evt.participant_count === 1 ? "participant" : "participants"}</span>
                      {evt.graph_distance !== null && evt.graph_distance > 0 && (
                        <span>{evt.graph_distance} {evt.graph_distance === 1 ? "hop" : "hops"}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    {evt.is_participant && (
                      <span className="text-xs text-emerald-500 border border-emerald-800 rounded px-2 py-0.5">
                        joined
                      </span>
                    )}
                    {evt.urgency === "spontaneous" && (
                      <span className="text-xs text-amber-500 border border-amber-800 rounded px-2 py-0.5">
                        spontaneous
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
          {events.some(e => e.graph_distance === null) && (
            <>
              <p className="text-xs text-neutral-500 mt-8 mb-4 uppercase tracking-wider">Beyond your network</p>
              <div className="grid gap-4">
                {events.filter(e => e.graph_distance === null).map((evt) => (
                  <Link
                    key={evt.node_id}
                    href={`/events/${evt.node_id}`}
                    className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all opacity-70"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
                          {evt.title}
                        </p>
                        {evt.description && (
                          <p className="text-sm text-neutral-400 leading-relaxed mb-2">{evt.description}</p>
                        )}
                        <div className="flex flex-wrap gap-3 text-xs text-neutral-500">
                          {evt.starts_at && <span>{formatDate(evt.starts_at)}</span>}
                          {evt.location && <span>{evt.location}</span>}
                          <span>{evt.participant_count} {evt.participant_count === 1 ? "participant" : "participants"}</span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {evt.is_participant && (
                          <span className="text-xs text-emerald-500 border border-emerald-800 rounded px-2 py-0.5">
                            joined
                          </span>
                        )}
                        {evt.urgency === "spontaneous" && (
                          <span className="text-xs text-amber-500 border border-amber-800 rounded px-2 py-0.5">
                            spontaneous
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
