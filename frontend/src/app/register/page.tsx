"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { register, setSession } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "", full_name: "", org_name: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function update(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      setSession(await register(form));
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-24">
      <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
        <label className="flex flex-col gap-1 text-sm">
          Full name
          <input
            type="text"
            required
            value={form.full_name}
            onChange={update("full_name")}
            className="rounded-lg border border-black/10 bg-transparent px-3 py-2 dark:border-white/15"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Company name
          <input
            type="text"
            required
            value={form.org_name}
            onChange={update("org_name")}
            className="rounded-lg border border-black/10 bg-transparent px-3 py-2 dark:border-white/15"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Work email
          <input
            type="email"
            required
            value={form.email}
            onChange={update("email")}
            className="rounded-lg border border-black/10 bg-transparent px-3 py-2 dark:border-white/15"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            type="password"
            required
            minLength={10}
            value={form.password}
            onChange={update("password")}
            className="rounded-lg border border-black/10 bg-transparent px-3 py-2 dark:border-white/15"
          />
          <span className="text-xs text-zinc-500">At least 10 characters</span>
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-full bg-zinc-900 px-6 py-2.5 font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {submitting ? "Creating…" : "Create account"}
        </button>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Already registered?{" "}
          <Link href="/login" className="font-medium underline">
            Log in
          </Link>
        </p>
      </form>
    </main>
  );
}
