"use client";

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen items-center justify-center bg-white p-6 dark:bg-black">
        <div className="flex flex-col items-center gap-3 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Something went wrong</h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {error.message || "An unexpected error occurred."}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-full bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white dark:bg-white dark:text-black"
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
