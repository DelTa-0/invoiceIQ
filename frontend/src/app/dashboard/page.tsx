"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clearSession,
  getToken,
  getOrgId,
  isUnauthorized,
  listSessions,
  createSession,
  type Session,
} from "@/lib/api";

const POLL_MS = 2000;

export default function DashboardPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [sessionName, setSessionName] = useState("");
  const [sessionDesc, setSessionDesc] = useState("");
  const [fieldInput, setFieldInput] = useState("");
  const [fields, setFields] = useState<Array<{ name: string; type: string; description: string }>>([]);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    const orgId = getOrgId();
    if (!orgId) return;
    try {
      setSessions(await listSessions(orgId));
    } catch (err) {
      if (isUnauthorized(err)) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load sessions");
    }
  }, [router]);

  useEffect(() => {
    if (!getToken() || !getOrgId()) {
      router.replace("/login");
      return;
    }
    const initial = setTimeout(refresh, 0);
    const timer = setInterval(refresh, POLL_MS);
    return () => {
      clearTimeout(initial);
      clearInterval(timer);
    };
  }, [refresh, router]);

  function addField() {
    const trimmed = fieldInput.trim();
    if (!trimmed) return;
    const name = trimmed.split(/[:\s]+/)[0];
    const type = /date|time/i.test(trimmed) ? "date" : /amount|total|price|sum/i.test(trimmed) ? "currency" : /count|qty|quantity/i.test(trimmed) ? "number" : /email|phone/i.test(trimmed) ? "text" : "string";
    setFields((prev) => [...prev, { name, type, description: trimmed }]);
    setFieldInput("");
  }

  function removeField(idx: number) {
    setFields((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleCreate() {
    if (!sessionName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createSession({
        name: sessionName.trim(),
        description: sessionDesc.trim() || undefined,
        requested_fields: fields,
      });
      setSessionName("");
      setSessionDesc("");
      setFields([]);
      setShowNew(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setCreating(false);
    }
  }

  function onLogout() {
    clearSession();
    router.replace("/login");
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Sessions</h1>
        <div className="flex gap-3">
          <button onClick={() => setShowNew(true)} className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-white dark:text-black">
            New Session
          </button>
          <button onClick={onLogout} className="text-sm text-zinc-500 underline">
            Log out
          </button>
        </div>
      </header>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {showNew && (
        <section className="rounded-xl border border-black/10 p-6 dark:border-white/15">
          <h2 className="mb-4 text-lg font-medium">Create New Session</h2>
          <div className="flex flex-col gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium">Session Name</label>
              <input type="text" value={sessionName} onChange={(e) => setSessionName(e.target.value)} placeholder="e.g. March Expense Extraction" className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm dark:border-white/15" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Description</label>
              <input type="text" value={sessionDesc} onChange={(e) => setSessionDesc(e.target.value)} placeholder="Optional description" className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm dark:border-white/15" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Fields to Extract</label>
              <div className="flex gap-2">
                <input type="text" value={fieldInput} onChange={(e) => setFieldInput(e.target.value)} placeholder="e.g. Supplier Name, Invoice Date, Total Amount" onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addField(); } }} className="flex-1 rounded-lg border border-black/10 px-3 py-2 text-sm dark:border-white/15" />
                <button onClick={addField} className="rounded-lg border border-black/10 px-3 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/5">Add</button>
              </div>
              {fields.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-2">
                  {fields.map((f, i) => (
                    <li key={i} className="flex items-center gap-1 rounded-full border border-black/10 px-3 py-1 text-xs dark:border-white/15">
                      {f.name} <span className="text-zinc-400">({f.type})</span>
                      <button onClick={() => removeField(i)} className="ml-1 text-zinc-400 hover:text-red-500">&times;</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex gap-3">
              <button onClick={handleCreate} disabled={creating || !sessionName.trim()} className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-white dark:text-black">
                {creating ? "Creating..." : "Create Session"}
              </button>
              <button onClick={() => setShowNew(false)} className="rounded-lg border border-black/10 px-4 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/5">Cancel</button>
            </div>
          </div>
        </section>
      )}

      {sessions.length === 0 ? (
        <p className="text-center text-sm text-zinc-500">No sessions yet. Create one to get started.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {sessions.map((s) => (
            <div key={s.id} className="rounded-xl border border-black/10 p-4 dark:border-white/15">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">{s.name}</h3>
                <span className="rounded-full border border-black/10 px-2 py-0.5 text-xs dark:border-white/15">{s.status}</span>
              </div>
              {s.description && <p className="mt-1 text-sm text-zinc-500">{s.description}</p>}
              <div className="mt-2 flex items-center gap-4 text-xs text-zinc-400">
                <span>{s.result_count} results</span>
                <span>{new Date(s.created_at).toLocaleDateString()}</span>
              </div>
              {s.requested_fields.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {s.requested_fields.map((f) => (
                    <span key={f.name} className="rounded-full border border-black/5 px-2 py-0.5 text-xs dark:border-white/5">{f.name}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}