"use client";

import { api, Attribute, EventInfo, EventParticipant, ResponderInfo } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
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

export default function EventDetailPage() {
  const { user, loading: authLoading } = useAuth();
  const params = useParams();
  const router = useRouter();
  const eventId = params.id as string;

  const [event, setEvent] = useState<EventInfo | null>(null);
  const [participants, setParticipants] = useState<EventParticipant[]>([]);
  const [responders, setResponders] = useState<ResponderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newContent, setNewContent] = useState("");
  const [newDirection, setNewDirection] = useState<"input" | "output">("output");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const [vouchNodeId, setVouchNodeId] = useState("");
  const [vouching, setVouching] = useState(false);
  const [vouchError, setVouchError] = useState("");

  const loadEvent = useCallback(async () => {
    try {
      const [evtData, partData, respData] = await Promise.all([
        api.events.get(eventId),
        api.events.getParticipants(eventId),
        api.events.getResponders(eventId),
      ]);
      setEvent(evtData);
      setParticipants(partData);
      setResponders(respData);
    } catch {
      setError("Event not found");
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    if (user) loadEvent();
  }, [user, loadEvent]);

  const handleAddAttribute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;
    setAdding(true);
    try {
      await api.events.createAttribute(eventId, newDirection, newContent.trim());
      setNewContent("");
      loadEvent();
    } finally {
      setAdding(false);
    }
  };

  const handleSaveEdit = async (attrId: string) => {
    if (!editContent.trim()) return;
    await api.events.updateAttribute(eventId, attrId, editContent.trim());
    setEditingId(null);
    loadEvent();
  };

  const handleDeleteAttr = async (attrId: string) => {
    await api.events.deleteAttribute(eventId, attrId);
    loadEvent();
  };

  const handleVouch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vouchNodeId.trim()) return;
    setVouching(true);
    setVouchError("");
    try {
      await api.events.vouchParticipant(eventId, vouchNodeId.trim());
      setVouchNodeId("");
      loadEvent();
    } catch (err) {
      setVouchError(err instanceof Error ? err.message : "Failed to vouch");
    } finally {
      setVouching(false);
    }
  };

  const handleLeave = async () => {
    try {
      await api.events.leave(eventId);
      loadEvent();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to leave");
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

  if (error || !event) {
    return (
      <div className="max-w-2xl mx-auto p-8">
        <Link href="/events" className="text-sm text-neutral-400 hover:text-white">&larr; Back</Link>
        <p className="mt-4 text-red-400">{error || "Event not found"}</p>
      </div>
    );
  }

  const renderAttributes = (title: string, direction: "input" | "output", attrs: Attribute[]) => (
    <div>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">{title}</h3>
      {attrs.length === 0 && <p className="text-sm text-gray-400 mb-3">None yet.</p>}
      <ul className="space-y-2 mb-4">
        {attrs.map((attr) => (
          <li key={attr.id} className="flex items-start gap-2 group">
            {editingId === attr.id ? (
              <div className="flex-1 flex gap-2">
                <input
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="flex-1 px-3 py-1.5 bg-transparent border border-neutral-700 rounded text-sm"
                  autoFocus
                />
                <button onClick={() => handleSaveEdit(attr.id)} className="text-sm font-medium">Save</button>
                <button onClick={() => setEditingId(null)} className="text-sm text-gray-400">Cancel</button>
              </div>
            ) : (
              <>
                <span className="flex-1 text-sm text-neutral-300">{attr.content}</span>
                {event.is_participant && (
                  <span className="opacity-0 group-hover:opacity-100 flex gap-2 transition">
                    <button
                      onClick={() => { setEditingId(attr.id); setEditContent(attr.content); }}
                      className="text-xs text-gray-400 hover:text-gray-200"
                    >edit</button>
                    <button
                      onClick={() => handleDeleteAttr(attr.id)}
                      className="text-xs text-red-400 hover:text-red-300"
                    >remove</button>
                  </span>
                )}
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <Link href="/events" className="text-sm text-neutral-400 hover:text-white">&larr; Events</Link>
      </div>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold">{event.title}</h2>
          {event.description && <p className="text-sm text-neutral-400 mt-1">{event.description}</p>}
          <div className="flex flex-wrap gap-3 text-xs text-neutral-500 mt-2">
            {event.starts_at && <span>{formatDate(event.starts_at)}{event.ends_at ? ` \u2014 ${formatDate(event.ends_at)}` : ""}</span>}
            {event.location && <span>{event.location}</span>}
            {event.urgency === "spontaneous" && (
              <span className="text-amber-500 border border-amber-800 rounded px-2 py-0.5">spontaneous</span>
            )}
          </div>
        </div>
        {event.is_participant && (
          <button
            onClick={handleLeave}
            className="text-xs text-red-400 hover:text-red-300 border border-red-800 rounded px-2 py-1"
          >
            Leave
          </button>
        )}
      </div>

      {/* Contact button */}
      {user && responders.length > 0 && !responders.some(r => r.node_id === user.node_id) && (
        <button
          onClick={() => {
            const responder = responders[0];
            router.push(`/messages/${responder.node_id}?context=${eventId}`);
          }}
          className="w-full mb-6 px-4 py-3 bg-emerald-700 text-white text-sm font-medium rounded-xl hover:bg-emerald-600 transition"
        >
          Contact about this event
        </button>
      )}

      {/* Membrane */}
      <div className="grid gap-6 mb-8">
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-6">
          {renderAttributes("Outputs \u2014 what this event provides", "output", event.outputs)}
        </div>
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-6">
          {renderAttributes("Inputs \u2014 what this event needs", "input", event.inputs)}
        </div>

        {event.is_participant && (
          <form onSubmit={handleAddAttribute} className="flex gap-2">
            <select
              value={newDirection}
              onChange={(e) => setNewDirection(e.target.value as "input" | "output")}
              className="px-2 py-1.5 bg-transparent border border-neutral-700 rounded text-sm"
            >
              <option value="output">Output</option>
              <option value="input">Input</option>
            </select>
            <input
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              placeholder={newDirection === "output" ? "What does this event provide?" : "What does this event need?"}
              className="flex-1 px-3 py-1.5 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
            />
            <button
              type="submit"
              disabled={adding || !newContent.trim()}
              className="px-3 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50 transition"
            >
              Add
            </button>
          </form>
        )}
      </div>

      {/* Participants */}
      <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-6 mb-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Participants ({participants.length})
        </h3>
        <ul className="space-y-2">
          {participants.map((p) => (
            <li key={p.node_id} className="flex items-center justify-between text-sm">
              <span className="text-neutral-300">{p.username || p.name || p.node_id.slice(0, 8)}</span>
              <span className="text-xs text-neutral-500">
                joined {new Date(p.joined_at).toLocaleDateString()}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Vouch someone in */}
      {event.is_participant && (
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Vouch someone in
          </h3>
          <form onSubmit={handleVouch} className="flex gap-2">
            <input
              value={vouchNodeId}
              onChange={(e) => setVouchNodeId(e.target.value)}
              placeholder="User node ID"
              className="flex-1 px-3 py-1.5 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
            />
            <button
              type="submit"
              disabled={vouching || !vouchNodeId.trim()}
              className="px-3 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50 transition"
            >
              Vouch
            </button>
          </form>
          {vouchError && <p className="text-sm text-red-400 mt-2">{vouchError}</p>}
        </div>
      )}
    </div>
  );
}
