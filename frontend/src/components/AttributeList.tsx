"use client";

import { api, Attribute } from "@/lib/api";
import { useState } from "react";

type Props = {
  title: string;
  direction: "input" | "output";
  attributes: Attribute[];
  editable: boolean;
  onUpdate: () => void;
};

export function AttributeList({
  title,
  direction,
  attributes,
  editable,
  onUpdate,
}: Props) {
  const [newContent, setNewContent] = useState("");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;
    setAdding(true);
    try {
      await api.profile.createAttribute(direction, newContent.trim());
      setNewContent("");
      onUpdate();
    } finally {
      setAdding(false);
    }
  };

  const handleSaveEdit = async (id: string) => {
    if (!editContent.trim()) return;
    await api.profile.updateAttribute(id, editContent.trim());
    setEditingId(null);
    onUpdate();
  };

  const handleDelete = async (id: string) => {
    await api.profile.deleteAttribute(id);
    onUpdate();
  };

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
        {title}
      </h3>

      {attributes.length === 0 && (
        <p className="text-sm text-gray-400 mb-3">None yet.</p>
      )}

      <ul className="space-y-2 mb-4">
        {attributes.map((attr) => (
          <li
            key={attr.id}
            className="flex items-start gap-2 group"
          >
            {editingId === attr.id ? (
              <div className="flex-1 flex gap-2">
                <input
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm"
                  autoFocus
                />
                <button
                  onClick={() => handleSaveEdit(attr.id)}
                  className="text-sm text-gray-900 font-medium"
                >
                  Save
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="text-sm text-gray-400"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <>
                <span className="flex-1 text-sm text-gray-800">
                  {attr.content}
                </span>
                {editable && (
                  <span className="opacity-0 group-hover:opacity-100 flex gap-2 transition">
                    <button
                      onClick={() => {
                        setEditingId(attr.id);
                        setEditContent(attr.content);
                      }}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      edit
                    </button>
                    <button
                      onClick={() => handleDelete(attr.id)}
                      className="text-xs text-red-400 hover:text-red-600"
                    >
                      remove
                    </button>
                  </span>
                )}
              </>
            )}
          </li>
        ))}
      </ul>

      {editable && (
        <form onSubmit={handleAdd} className="flex gap-2">
          <input
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder={
              direction === "output"
                ? "What do you offer or know?"
                : "What are you looking for or curious about?"
            }
            className="flex-1 px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
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
  );
}
