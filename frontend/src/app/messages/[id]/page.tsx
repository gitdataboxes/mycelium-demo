"use client";

import { api, MessageInfo } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import Link from "next/link";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function ThreadPage() {
  const { user, loading: authLoading } = useAuth();
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  const otherNodeId = params.id as string;
  const contextNodeId = searchParams.get("context") || undefined;

  const [messages, setMessages] = useState<MessageInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const otherUsername = messages.length > 0
    ? (messages[0].from_node_id === otherNodeId
        ? messages[0].from_username
        : messages[0].to_username)
    : null;

  const contextName = messages.length > 0 ? messages[0].context_name : null;

  const loadMessages = useCallback(async () => {
    try {
      const data = await api.messages.getThread(otherNodeId, contextNodeId);
      setMessages(data.messages);
      // Mark as read
      api.messages.markRead(otherNodeId, contextNodeId).catch(() => {});
    } catch {
      setError("Could not load messages");
    } finally {
      setLoading(false);
    }
  }, [otherNodeId, contextNodeId]);

  useEffect(() => {
    if (user) loadMessages();
  }, [user, loadMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim() || sending) return;
    setSending(true);
    setError("");
    try {
      const msg = await api.messages.send(newMessage.trim(), {
        toNodeId: contextNodeId ? undefined : otherNodeId,
        contextNodeId: contextNodeId,
      });
      setMessages((prev) => [...prev, msg]);
      setNewMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setSending(false);
    }
  };

  const handleBlock = async () => {
    if (!confirm("Block this user? They won't be able to message you.")) return;
    try {
      await api.trust.block(otherNodeId);
      router.push("/messages");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to block");
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
    <div className="max-w-2xl mx-auto flex flex-col h-screen">
      {/* Header */}
      <div className="px-6 py-4 border-b border-neutral-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/messages" className="text-sm text-neutral-400 hover:text-white">
              &larr;
            </Link>
            <div>
              {contextName && (
                <p className="text-xs text-emerald-500">{contextName}</p>
              )}
              <p className="text-sm font-medium">
                {otherUsername || otherNodeId.slice(0, 8)}
              </p>
            </div>
          </div>
          <button
            onClick={handleBlock}
            className="text-xs text-neutral-500 hover:text-red-400 transition"
          >
            Block
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
        {messages.length === 0 && !error && (
          <p className="text-sm text-neutral-500 text-center py-8">
            No messages yet. Send one to start the conversation.
          </p>
        )}
        {messages.map((msg) => {
          const isMe = msg.from_node_id === user.node_id;
          return (
            <div
              key={msg.id}
              className={`flex ${isMe ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] rounded-xl px-4 py-2.5 ${
                  isMe
                    ? "bg-emerald-900/40 border border-emerald-800/50"
                    : "bg-neutral-800 border border-neutral-700"
                }`}
              >
                <p className="text-sm text-neutral-200">{msg.content}</p>
                <p className={`text-xs mt-1 ${isMe ? "text-emerald-600" : "text-neutral-500"}`}>
                  {formatTime(msg.created_at)}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Compose */}
      <div className="px-6 py-4 border-t border-neutral-800">
        {error && <p className="text-sm text-red-400 mb-2">{error}</p>}
        <form onSubmit={handleSend} className="flex gap-2">
          <input
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type a message..."
            maxLength={2000}
            className="flex-1 px-4 py-2.5 bg-transparent border border-neutral-700 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-neutral-500"
          />
          <button
            type="submit"
            disabled={sending || !newMessage.trim()}
            className="px-4 py-2.5 bg-emerald-700 text-white text-sm rounded-xl hover:bg-emerald-600 disabled:opacity-50 transition"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
