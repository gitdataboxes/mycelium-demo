"use client";

import { api, MatchListItem } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export default function MatchesPage() {
  const { user, loading: authLoading } = useAuth();
  const [matches, setMatches] = useState<MatchListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadMatches = useCallback(async () => {
    try {
      const m = await api.matches.list();
      setMatches(m);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) loadMatches();
  }, [user, loadMatches]);

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
        <Link href="/" className="text-2xl font-bold hover:opacity-70">
          Mycelium
        </Link>
      </div>

      <h2 className="text-lg font-semibold mb-4">Your connections</h2>

      {matches.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-6 text-center">
          <p className="text-gray-500">
            No matches yet. The network will find connections as more people join
            and share what they offer and seek.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {matches.map((m) => (
            <li key={m.match_id}>
              <Link
                href={`/matches/${m.match_id}`}
                className="block bg-gray-50 rounded-lg p-5 hover:bg-gray-100 transition"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900">
                    {m.other_username || "Someone"}
                  </span>
                  <span className="text-xs text-gray-400">
                    {Math.round(m.similarity * 100)}% match
                  </span>
                </div>
                <p className="text-sm text-gray-600 mb-1">
                  <span className="text-gray-400">
                    {m.own_direction === "output" ? "You offer: " : "You seek: "}
                  </span>
                  &ldquo;{m.own_content}&rdquo;
                </p>
                <p className="text-sm text-gray-600">
                  <span className="text-gray-400">
                    {m.other_direction === "output" ? "They offer: " : "They seek: "}
                  </span>
                  &ldquo;{m.other_content}&rdquo;
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
