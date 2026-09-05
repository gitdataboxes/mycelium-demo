"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

type User = {
  node_id: string;
  username: string | null;
  email: string;
  is_active: boolean;
};

const DEV_MOCK = process.env.NEXT_PUBLIC_DEV_MOCK === "true";

const MOCK_USER: User = {
  node_id: "dev-node-001",
  username: "alice",
  email: "alice@example.com",
  is_active: true,
};

export function useAuth() {
  const [user, setUser] = useState<User | null>(DEV_MOCK ? MOCK_USER : null);
  const [loading, setLoading] = useState(!DEV_MOCK);

  const checkAuth = useCallback(async () => {
    if (DEV_MOCK) return;
    try {
      const me = await api.auth.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!DEV_MOCK) checkAuth();
  }, [checkAuth]);

  const logout = async () => {
    if (DEV_MOCK) { setUser(null); return; }
    await api.auth.logout();
    setUser(null);
  };

  return { user, loading, logout, refresh: checkAuth };
}
