"use client";

import { api, MatchDetail } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function MatchDetailPage() {
  const { user, loading: authLoading } = useAuth();
  const params = useParams();
  const matchId = params.id as string;

  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadMatch = useCallback(async () => {
    try {
      const m = await api.matches.getDetail(matchId);
      setMatch(m);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load match");
    } finally {
      setLoading(false);
    }
  }, [matchId]);

  useEffect(() => {
    if (user && matchId) loadMatch();
  }, [user, matchId, loadMatch]);

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

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-red-600">{error}</p>
        <Link href="/matches" className="underline">Back to matches</Link>
      </div>
    );
  }

  if (!match) return null;

  // Determine which node is "me" and which is "other"
  const isNodeA = match.node_a.node_id === user.node_id;
  const me = isNodeA ? match.node_a : match.node_b;
  const other = isNodeA ? match.node_b : match.node_a;

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <Link href="/" className="text-2xl font-bold hover:opacity-70">
          Mycelium
        </Link>
      </div>

      <Link href="/matches" className="text-sm text-gray-500 hover:text-gray-700 mb-6 block">
        &larr; All connections
      </Link>

      <div className="bg-gray-50 rounded-lg p-6 mb-4">
        <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">You</p>
        <p className="text-sm text-gray-800">
          <span className="text-gray-400">
            {me.attribute_direction === "output" ? "Offer: " : "Seek: "}
          </span>
          &ldquo;{me.attribute_content}&rdquo;
        </p>
        <p className="text-xs text-gray-400 mt-1">
          {me.attribute_type === "signal" ? "Active signal" : "Membrane"}
        </p>
      </div>

      <div className="flex justify-center my-2">
        <span className="text-xs text-gray-400">
          {Math.round(match.similarity * 100)}% semantic match
        </span>
      </div>

      <div className="bg-gray-50 rounded-lg p-6 mb-6">
        <p className="text-xs text-gray-400 uppercase tracking-wide mb-2">
          {other.username || "Someone"}
        </p>
        <p className="text-sm text-gray-800">
          <span className="text-gray-400">
            {other.attribute_direction === "output" ? "Offers: " : "Seeks: "}
          </span>
          &ldquo;{other.attribute_content}&rdquo;
        </p>
        <p className="text-xs text-gray-400 mt-1">
          {other.attribute_type === "signal" ? "Active signal" : "Membrane"}
        </p>
      </div>

      {/* Next steps */}
      <div className="border border-gray-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold mb-3">Next steps</h3>
        <p className="text-sm text-gray-600 mb-3">
          The network found a connection between you and{" "}
          <strong>{other.username || "this person"}</strong>. To follow up:
        </p>
        <ul className="text-sm text-gray-600 space-y-2">
          <li>
            <Link
              href={`/profile/${other.node_id}`}
              className="text-gray-900 underline"
            >
              View their full profile
            </Link>
            {" "}to learn more about what they offer and seek.
          </li>
          <li>
            Find them through a shared{" "}
            <Link href="/events" className="text-gray-900 underline">event</Link>
            {" "}or{" "}
            <Link href="/organizations" className="text-gray-900 underline">organization</Link>
            {" "}to start a conversation.
          </li>
        </ul>
      </div>
    </div>
  );
}
