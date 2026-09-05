"use client";

import { api, OrgInfo } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export default function OrganizationsPage() {
  const { user, loading: authLoading } = useAuth();
  const [orgs, setOrgs] = useState<OrgInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const loadOrgs = useCallback(async () => {
    try {
      const res = await api.organizations.list(search || undefined);
      setOrgs(res.organizations);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    if (user) loadOrgs();
  }, [user, loadOrgs]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.organizations.create(newName.trim(), newDesc.trim() || undefined);
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      loadOrgs();
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
        <h2 className="text-xl font-semibold">Organizations</h2>
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
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Organization name"
            className="w-full px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
            autoFocus
          />
          <textarea
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500 resize-none"
          />
          <button
            type="submit"
            disabled={creating || !newName.trim()}
            className="px-4 py-2 bg-gray-900 text-white text-sm rounded hover:bg-gray-700 disabled:opacity-50 transition"
          >
            Create Organization
          </button>
        </form>
      )}

      <div className="mb-6">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search organizations..."
          className="w-full px-3 py-2 bg-transparent border border-neutral-700 rounded text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
        />
      </div>

      {orgs.length === 0 ? (
        <p className="text-sm text-neutral-400">No organizations found.</p>
      ) : (
        <>
          <div className="grid gap-4">
            {orgs.filter(o => o.graph_distance !== null).map((org) => (
              <Link
                key={org.node_id}
                href={`/organizations/${org.node_id}`}
                className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
                      {org.name}
                    </p>
                    {org.description && (
                      <p className="text-sm text-neutral-400 leading-relaxed mb-2">
                        {org.description}
                      </p>
                    )}
                    <div className="flex gap-3 text-xs text-neutral-500">
                      <span>{org.member_count} {org.member_count === 1 ? "member" : "members"}</span>
                      {org.graph_distance !== null && org.graph_distance > 0 && (
                        <span>{org.graph_distance} {org.graph_distance === 1 ? "hop" : "hops"}</span>
                      )}
                    </div>
                  </div>
                  {org.is_member && (
                    <span className="text-xs text-emerald-500 border border-emerald-800 rounded px-2 py-0.5">
                      member
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
          {orgs.some(o => o.graph_distance === null) && (
            <>
              <p className="text-xs text-neutral-500 mt-8 mb-4 uppercase tracking-wider">Beyond your network</p>
              <div className="grid gap-4">
                {orgs.filter(o => o.graph_distance === null).map((org) => (
                  <Link
                    key={org.node_id}
                    href={`/organizations/${org.node_id}`}
                    className="group block rounded-xl border border-neutral-800 bg-neutral-900/60 p-6 hover:border-neutral-600 hover:bg-neutral-800/80 transition-all opacity-70"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-base font-semibold text-white mb-1 group-hover:text-emerald-400 transition-colors">
                          {org.name}
                        </p>
                        {org.description && (
                          <p className="text-sm text-neutral-400 leading-relaxed mb-2">
                            {org.description}
                          </p>
                        )}
                        <p className="text-xs text-neutral-500">
                          {org.member_count} {org.member_count === 1 ? "member" : "members"}
                        </p>
                      </div>
                      {org.is_member && (
                        <span className="text-xs text-emerald-500 border border-emerald-800 rounded px-2 py-0.5">
                          member
                        </span>
                      )}
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
