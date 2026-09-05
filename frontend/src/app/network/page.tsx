"use client";

import { api, TrustGraph } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export default function NetworkPage() {
  const { user, loading: authLoading } = useAuth();
  const [graph, setGraph] = useState<TrustGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [vouchEmail, setVouchEmail] = useState("");
  const [vouchError, setVouchError] = useState("");
  const [vouchSuccess, setVouchSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadGraph = useCallback(async () => {
    try {
      const g = await api.trust.getGraph();
      setGraph(g);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) loadGraph();
  }, [user, loadGraph]);

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

  if (!graph) return null;

  const handleVouch = async (e: React.FormEvent) => {
    e.preventDefault();
    setVouchError("");
    setVouchSuccess("");
    setSubmitting(true);

    try {
      const result = await api.trust.vouch(vouchEmail);
      setVouchSuccess(
        result.invite_sent
          ? `Invite sent to ${vouchEmail}`
          : `Vouched for ${vouchEmail}`
      );
      setVouchEmail("");
      loadGraph();
    } catch (err) {
      setVouchError(err instanceof Error ? err.message : "Failed to vouch");
    } finally {
      setSubmitting(false);
    }
  };

  const handleWithdraw = async (vouchId: string) => {
    if (!confirm("Withdraw this vouch? If they have no other vouches, their account will be deactivated.")) {
      return;
    }
    await api.trust.withdrawVouch(vouchId);
    loadGraph();
  };

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <Link href="/" className="text-2xl font-bold hover:opacity-70">
          Mycelium
        </Link>
      </div>

      {/* Vouch someone */}
      <div className="bg-gray-50 rounded-lg p-6 mb-8">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Vouch for someone
        </h3>
        {graph.can_vouch ? (
          <form onSubmit={handleVouch} className="flex gap-2">
            <input
              type="email"
              value={vouchEmail}
              onChange={(e) => setVouchEmail(e.target.value)}
              placeholder="neighbor@example.com"
              required
              className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
            />
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50 transition"
            >
              Vouch
            </button>
          </form>
        ) : (
          <p className="text-sm text-gray-500">
            You&apos;ve already vouched for someone this week. You can vouch again next week.
          </p>
        )}
        {vouchError && <p className="text-sm text-red-600 mt-2">{vouchError}</p>}
        {vouchSuccess && <p className="text-sm text-green-700 mt-2">{vouchSuccess}</p>}
      </div>

      {/* Vouches given */}
      <div className="bg-gray-50 rounded-lg p-6 mb-8">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          People I&apos;ve vouched for
        </h3>
        {graph.vouches_given.length === 0 ? (
          <p className="text-sm text-gray-400">None yet.</p>
        ) : (
          <ul className="space-y-2">
            {graph.vouches_given.map((v) => (
              <li key={v.id} className="flex items-center justify-between group">
                <div>
                  <span className="text-sm font-medium">
                    {v.vouchee_username || v.vouchee_email}
                  </span>
                  {v.vouchee_username && (
                    <span className="text-xs text-gray-400 ml-2">{v.vouchee_email}</span>
                  )}
                </div>
                <button
                  onClick={() => handleWithdraw(v.id)}
                  className="text-xs text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition"
                >
                  withdraw
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Vouches received */}
      <div className="bg-gray-50 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Vouched for me
        </h3>
        {graph.vouches_received.length === 0 ? (
          <p className="text-sm text-gray-400">None yet.</p>
        ) : (
          <ul className="space-y-2">
            {graph.vouches_received.map((v) => (
              <li key={v.id} className="text-sm">
                <span className="font-medium">
                  {v.voucher_username || "Anonymous"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
