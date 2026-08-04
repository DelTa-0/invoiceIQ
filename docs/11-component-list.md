# 11 — Component List

shadcn/ui primitives + custom domain components. Every component is typed against `packages/schemas` (Zod) so the UI cannot render a field shape the backend doesn't produce.

## 1. shadcn/ui primitives (installed base)
`button, badge, card, dialog, dropdown-menu, input, select, tabs, table, checkbox, tooltip, popover, skeleton, alert, sheet, command, toast, separator, switch, progress, skeleton, calendar, textarea, collapsible, avatar, scroll-area, context-menu, sheet, sonner`

## 2. Layout & shell
| Component | Purpose |
|---|---|
| `AppShell` | sidebar + topbar + footer meter |
| `Sidebar` / `NavItem` | nav with active state + badge counts (review queue) |
| `OrgSwitcher` | org dropdown w/ create |
| `ThemeToggle` | dark/light/system |
| `CommandPalette` | ⌘K: navigation, invoice lookup, NL search (P2) |
| `UsageMeter` | pages vs plan bar (footer) |
| `Breadcrumbs` | settings/deep pages |

## 3. Upload
| Component | Purpose |
|---|---|
| `UploadDropzone` | drag/drop, paste, browse; full-page overlay |
| `UploadQueue` | per-file rows: progress, status, error, dedupe link |
| `BulkProgress` | batch summary (n/total, success/review/fail) |
| `FormatChip` | pdf/img/zip icon + size |

## 4. Invoice list
| Component | Purpose |
|---|---|
| `InvoiceTable` | TanStack Table: sort/filter/virtualize/columns toggle |
| `InvoiceFilters` | status/supplier/date/vat/currency + saved filters (P2) |
| `StatusBadge` | queued/processing/review/completed/failed |
| `ConfidenceBadge` | % + ring color by threshold |
| `VatBadge` | ✓ valid / ⚠ warn / ✕ fail + reason tooltip |
| `RowMenu` | row actions (view, export, reprocess, delete) |
| `BulkBar` | bulk approve/export/delete |
| `ReviewQueueStrip` | next/prev, count, progress bar |

## 5. Review (core surface)
| Component | Purpose |
|---|---|
| `ReviewSplit` | document + fields pane; resizable |
| `DocumentViewer` | PDF/image render (pdf.js), page nav, zoom, rotate |
| `HighlightLayer` | overlays bboxes from `fields[*].bbox`; click→focus |
| `FieldCard` | one field: label, value, confidence, method, validator badge |
| `FieldInput` | typed editor (money/date/text/select) w/ validation on blur |
| `ConfidenceRing` | radial % + delta after edit |
| `SourcePopover` | OCR snippet, bbox coords, method, VIES result |
| `ValidationPanel` | grouped pass/warn/fail checks w/ evidence (expected vs actual) |
| `LinesTable` | editable line-item grid w/ running totals + reconciliation row |
| `ApproveBar` | approve/reject + shortcuts hint |
| `CorrectionHistory` | timeline of edits (who/what/when) |
| `ReprocessDialog` | stage picker + confirm |
| `DuplicateBanner` | "matches invoice #…" notice |

## 6. Suppliers & misc
| Component | Purpose |
|---|---|
| `SupplierTable` | profile + accuracy + flags |
| `SupplierDetail` | spend, invoices, corrections stats |
| `MergeDialog` | choose keep/merge |
| `ApiKeyList` / `ApiKeyCreate` | show-once secret, scopes, rotate |
| `WebhookForm` / `WebhookEventLog` | config + delivery status + replay |
| `UsageChart` | pages/day, cost by source |
| `AuditTable` | admin log viewer |
| `EmptyState` | illustration + CTA |
| `ErrorState` | code + retry |

## 7. Hooks & lib
| Hook/Util | Purpose |
|---|---|
| `useInvoices` (React Query) | list/detail/refetch on events |
| `useUpload` | multipart + queue state machine |
| `useReviewActions` | approve/reject/correct mutations + optimistic UI |
| `useWebhookEvents` | SSE/poll for live status |
| `useOrg` / `useRBAC` | session org + permissions |
| `money` / `datefmt` / `locale` utils | display rounding, locale parsing |
| `apiClient` | fetch wrapper: JWT/API-key, retry, error envelope, idempotency key |
| `cn` (clsx+twMerge) | class merging |

## 8. State management
- Server state: **React Query** (cache invoices/detail/usage; invalidate on mutation + webhook event).
- Client state: lightweight `useState`/`useReducer` for UI (upload queue, filters, selection). Zustand only if cross-tree state grows (P2).
- Mutations: React Query optimistic updates for edits; rollback on 4xx.

## 9. Accessibility & DX rules
- All interactive elements keyboard operable; review screen fully keyboard-first.
- Colors: badges convey via icon + text, not color alone (AA).
- Every async action has loading/error/empty states; skeleton loaders over spinners where possible.
