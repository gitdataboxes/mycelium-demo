"use client";

import { AttributeList } from "@/components/AttributeList";
import { api, Profile } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export default function ProfilePage() {
  const { user, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingUsername, setEditingUsername] = useState(false);
  const [username, setUsername] = useState("");
  const [usernameError, setUsernameError] = useState("");

  const loadProfile = useCallback(async () => {
    try {
      const p = await api.profile.get();
      setProfile(p);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) loadProfile();
  }, [user, loadProfile]);

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
        <Link href="/auth" className="underline">
          Log in
        </Link>
      </div>
    );
  }

  if (!profile) return null;

  const handleUsernameSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUsernameError("");
    try {
      await api.profile.updateUsername(username);
      setEditingUsername(false);
      loadProfile();
    } catch (err) {
      setUsernameError(
        err instanceof Error ? err.message : "Failed to update username"
      );
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <Link href="/" className="text-2xl font-bold hover:opacity-70">
          Mycelium
        </Link>
      </div>

      {/* Username section */}
      <div className="mb-8">
        {editingUsername ? (
          <form onSubmit={handleUsernameSubmit} className="flex gap-2 items-center">
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Choose a username"
              className="px-3 py-1.5 border border-gray-300 rounded text-lg font-medium focus:outline-none focus:ring-1 focus:ring-gray-900"
              autoFocus
            />
            <button
              type="submit"
              className="text-sm text-gray-900 font-medium"
            >
              Save
            </button>
            <button
              onClick={() => setEditingUsername(false)}
              className="text-sm text-gray-400"
            >
              Cancel
            </button>
            {usernameError && (
              <span className="text-sm text-red-600">{usernameError}</span>
            )}
          </form>
        ) : (
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold">
              {profile.username || "No username set"}
            </h2>
            <button
              onClick={() => {
                setUsername(profile.username || "");
                setEditingUsername(true);
              }}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              edit
            </button>
          </div>
        )}
        <p className="text-sm text-gray-500 mt-1">{profile.email}</p>
      </div>

      {/* Membrane */}
      <div className="grid gap-8">
        <div className="bg-gray-50 rounded-lg p-6">
          <AttributeList
            title="Outputs — what I offer"
            direction="output"
            attributes={profile.outputs}
            editable={true}
            onUpdate={loadProfile}
          />
        </div>

        <div className="bg-gray-50 rounded-lg p-6">
          <AttributeList
            title="Inputs — what I seek"
            direction="input"
            attributes={profile.inputs}
            editable={true}
            onUpdate={loadProfile}
          />
        </div>
      </div>
    </div>
  );
}
