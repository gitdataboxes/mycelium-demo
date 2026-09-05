"use client";

import { api, ContactInfo, ThreadInfo } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function MessagesPage() {
  const { user, loading: authLoading } = useAuth();
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [contacts, setContacts] = useState<ContactInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewMessage, setShowNewMessage] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [threadData, contactData] = await Promise.all([
        api.messages.list(),
        api.messages.contacts(),
      ]);
      setThreads(threadData.threads);
      setContacts(contactData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) loadData();
  }, [user, loadData]);

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

  function threadUrl(t: ThreadInfo) {
    const base = `/messages/${t.other_node_id}`;
    return t.context_node_id ? `${base}?context=${t.context_node_id}` : base;
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="flex items-center justify-between mb-8">
        <Link href="/" className="text-2xl font-bold hover:opacity-70">
          Mycelium
        </Link>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Messages</h2>
        {contacts.length > 0 && (
          <button
            onClick={() => setShowNewMessage(!showNewMessage)}
            className="text-sm text-emerald-400 hover:text-emerald-300 transition"
          >
            {showNewMessage ? "Cancel" : "New message"}
          </button>
        )}
      </div>

      {showNewMessage && (
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4 mb-6">
          <p className="text-sm text-neutral-400 mb-3">Start a direct message with a contact:</p>
          <div className="space-y-2">
            {contacts.map((c) => (
              <Link
                key={c.node_id}
                href={`/messages/${c.node_id}`}
                className="block text-sm text-neutral-300 hover:text-emerald-400 transition py-1"
              >
                {c.username || c.node_id.slice(0, 8)}
              </Link>
            ))}
            {contacts.length === 0 && (
              <p className="text-sm text-neutral-500">
                No contacts yet. Contact someone through an event or organization first.
              </p>
            )}
          </div>
        </div>
      )}

      {threads.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-neutral-400 mb-2">No messages yet.</p>
          <p className="text-sm text-neutral-500">
            Contact someone through an{" "}
            <Link href="/events" className="text-emerald-400 hover:underline">event</Link>
            {" "}or{" "}
            <Link href="/organizations" className="text-emerald-400 hover:underline">organization</Link>
            {" "}to start a conversation.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {threads.map((t) => (
            <Link
              key={`${t.other_node_id}:${t.context_node_id || "direct"}`}
              href={threadUrl(t)}
              className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  {t.context_name && (
                    <p className="text-xs text-emerald-500 mb-1">{t.context_name}</p>
                  )}
                  <p className="text-sm font-medium text-neutral-200 group-hover:text-white transition">
                    {t.other_username || t.other_node_id.slice(0, 8)}
                  </p>
                  <p className="text-sm text-neutral-500 truncate mt-0.5">
                    {t.last_message.from_node_id === user.node_id ? "You: " : ""}
                    {t.last_message.content.length > 80
                      ? t.last_message.content.slice(0, 80) + "..."
                      : t.last_message.content}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className="text-xs text-neutral-500">
                    {timeAgo(t.last_message.created_at)}
                  </span>
                  {t.unread_count > 0 && (
                    <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-medium bg-emerald-600 text-white rounded-full">
                      {t.unread_count}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
