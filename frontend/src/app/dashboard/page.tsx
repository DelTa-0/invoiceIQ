"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearSession, getToken, getOrgId, isUnauthorized, listInvoices, uploadInvoice, type Invoice } from "@/lib/api";

const POLL_MS = 2000;

export default function DashboardPage() {
  const router = useRouter();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    const orgId = getOrgId();
    if (!orgId) return;
    try {
      setInvoices(await listInvoices(orgId));
    } catch (err) {
      if (isUnauthorized(err)) {
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load invoices");
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

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadInvoice(file);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  function onLogout() {
    clearSession();
    router.replace("/login");
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Invoices</h1>
        <button onClick={onLogout} className="text-sm text-zinc-500 underline">
          Log out
        </button>
      </header>

      <label className="flex cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-black/15 px-6 py-10 text-sm text-zinc-500 transition-colors hover:border-black/30 dark:border-white/20 dark:hover:border-white/40">
        {uploading ? "Uploading…" : "Drop a PDF or image here or click to upload"}
        <input type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,application/pdf,image/*" className="hidden" onChange={onUpload} disabled={uploading} />
      </label>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {invoices.length === 0 ? (
        <p className="text-center text-sm text-zinc-500">No invoices yet.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="border-b border-black/10 dark:border-white/15">
            <tr>
              <th className="py-2 pr-4 font-medium">File</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 pr-4 font-medium">Supplier</th>
              <th className="py-2 font-medium">Total</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id} className="border-b border-black/5 dark:border-white/5">
                <td className="py-2 pr-4">{inv.filename}</td>
                <td className="py-2 pr-4">
                  <span className="inline-flex rounded-full border border-black/10 px-2 py-0.5 text-xs dark:border-white/15">
                    {inv.status}
                  </span>
                </td>
                <td className="py-2 pr-4">{inv.supplier_name ?? "—"}</td>
                <td className="py-2">
                  {inv.total ? `${inv.total} ${inv.currency ?? ""}` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
