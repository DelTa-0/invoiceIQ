import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
      <div className="flex max-w-2xl flex-col items-center gap-8 text-center">
        <p className="rounded-full border border-black/10 px-3 py-1 text-xs font-medium text-zinc-600 dark:border-white/15 dark:text-zinc-400">
          GDPR-first · EU data residency
        </p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-6xl">
          Accounts payable, without the pain
        </h1>
        <p className="max-w-xl text-lg leading-8 text-zinc-600 dark:text-zinc-400">
          InvoiceIQ reads your supplier invoices with deterministic rules and
          AI, flags low-confidence fields for a quick human check, and hands
          you clean, validated data for your accounting system.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            href="/register"
            className="rounded-full bg-zinc-900 px-6 py-3 font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            Get started
          </Link>
          <Link
            href="/login"
            className="rounded-full border border-black/10 px-6 py-3 font-medium transition-colors hover:bg-black/5 dark:border-white/15 dark:hover:bg-white/10"
          >
            Log in
          </Link>
        </div>
        <dl className="mt-8 grid w-full max-w-lg grid-cols-1 gap-4 text-left sm:grid-cols-3">
          <div className="rounded-xl border border-black/10 p-4 dark:border-white/15">
            <dt className="text-sm font-medium">EU-first AI</dt>
            <dd className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Mistral by default; US LLMs only as an explicit per-tenant opt-in.
            </dd>
          </div>
          <div className="rounded-xl border border-black/10 p-4 dark:border-white/15">
            <dt className="text-sm font-medium">Human-in-the-loop</dt>
            <dd className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Confidence scores route uncertain invoices into review.
            </dd>
          </div>
          <div className="rounded-xl border border-black/10 p-4 dark:border-white/15">
            <dt className="text-sm font-medium">Export &amp; API</dt>
            <dd className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Take clean data anywhere: CSV, accounting integrations, webhooks.
            </dd>
          </div>
        </dl>
      </div>
    </main>
  );
}
