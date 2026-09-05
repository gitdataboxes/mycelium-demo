"use client";

import { api, SignalInfo } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function timeUntil(dateStr: string): string {
  const diff = new Date(dateStr).getTime() - Date.now();
  if (diff <= 0) return "expired";
  const days = Math.floor(diff / 86400000);
  if (days > 1) return `${days} days left`;
  const hours = Math.floor(diff / 3600000);
  if (hours > 1) return `${hours} hours left`;
  return "expiring soon";
}

export default function SignalsPage() {
  const { user, loading: authLoading } = useAuth();
  const [signals, setSignals] = useState<SignalInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const [content, setContent] = useState("");
  const [direction, setDirection] = useState<"input" | "output">("output");
  const [expiresInDays, setExpiresInDays] = useState(30);
  const [submitting, setSubmitting] = useState(false);

  const loadSignals = useCallback(async () => {
    try {
      const s = await api.signals.list();
      setSignals(s);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) loadSignals();
  }, [user, loadSignals]);

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

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    setSubmitting(true);
    try {
      await api.signals.create(direction, content.trim(), expiresInDays);
      setContent("");
      loadSignals();
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    await api.signals.remove(id);
    loadSignals();
  };

  const outputSignals = signals.filter((s) => s.direction === "output");
  const inputSignals = signals.filter((s) => s.direction === "input");

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <Link href="/" className="text-2xl font-bold hover:opacity-70">
          Mycelium
        </Link>
      </div>

      {/* Create signal */}
      <div className="bg-gray-50 rounded-lg p-6 mb-8">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          New signal
        </h3>
        <p className="text-sm text-gray-500 mb-4">
          What&apos;s alive for you right now? Signals are time-bound — they expire naturally.
        </p>
        <form onSubmit={handleCreate} className="space-y-3">
          <div className="flex gap-2">
            <select
              value={direction}
              onChange={(e) => setDirection(e.target.value as "input" | "output")}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm bg-white"
            >
              <option value="output">I&apos;m offering...</option>
              <option value="input">I&apos;m looking for...</option>
            </select>
            <select
              value={expiresInDays}
              onChange={(e) => setExpiresInDays(Number(e.target.value))}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm bg-white"
            >
              <option value={7}>1 week</option>
              <option value={14}>2 weeks</option>
              <option value={30}>1 month</option>
              <option value={60}>2 months</option>
              <option value={90}>3 months</option>
            </select>
          </div>
          <div className="flex gap-2">
            <input
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="e.g. Hosting a potluck this Saturday"
              className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
            />
            <button
              type="submit"
              disabled={submitting || !content.trim()}
              className="px-4 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50 transition"
            >
              Send
            </button>
          </div>
        </form>
      </div>

      {/* Active signals */}
      {outputSignals.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-6 mb-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Offering
          </h3>
          <ul className="space-y-2">
            {outputSignals.map((s) => (
              <li key={s.id} className="flex items-start justify-between group">
                <div>
                  <p className="text-sm text-gray-800">{s.content}</p>
                  <p className="text-xs text-gray-400">{timeUntil(s.expires_at)}</p>
                </div>
                <button
                  onClick={() => handleDelete(s.id)}
                  className="text-xs text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition"
                >
                  remove
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {inputSignals.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-6 mb-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Looking for
          </h3>
          <ul className="space-y-2">
            {inputSignals.map((s) => (
              <li key={s.id} className="flex items-start justify-between group">
                <div>
                  <p className="text-sm text-gray-800">{s.content}</p>
                  <p className="text-xs text-gray-400">{timeUntil(s.expires_at)}</p>
                </div>
                <button
                  onClick={() => handleDelete(s.id)}
                  className="text-xs text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition"
                >
                  remove
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {signals.length === 0 && (
        <p className="text-sm text-gray-400 text-center">
          No active signals. Post one above to let the network know what&apos;s alive for you.
        </p>
      )}
    </div>
  );
}
