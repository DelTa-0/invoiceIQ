# 10 — UI Wireframes

Design language: Linear + Stripe + Vercel — dense but calm, dark-mode-first, keyboard-first for reviewers. Layout grid 12-col; max content width 1280 px; type: Inter (UI) + JetBrains Mono (numbers/source snippets). Full ASCII wireframes below; component specs in `docs/11`.

## 1. App shell

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ◆ InvoiceIQ    ⌘K search…                [◉ org A ▾]  [🌙]  [avatar ▾]       │
├───────────────┬──────────────────────────────────────────────────────────────┤
│ Invoices      │                                                              │
│  Review queue │                    (page content)                            │
│  Suppliers    │                                                              │
│ Reports       │                                                              │
│ ───────────── │                                                              │
│ Settings      │                                                              │
│  Org/Team     │                                                              │
│  API keys     │                                                              │
│  Webhooks     │                                                              │
│ Usage         │                                                              │
├───────────────┴──────────────────────────────────────────────────────────────┤
│ 54 invoices this month · 12 left on Starter                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```
Sidebar 220 px, collapsible. Top bar: global search (⌘K), org switcher, theme, profile. Footer: usage meter (nudge to upgrade, non-blocking in MVP).

## 2. Invoices list

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Invoices                          [Upload ▾] [Export ▾] [⋮ bulk]              │
│ [Search…] [Status▾] [Supplier▾] [Date▾] [VAT flag▾] [⟳]  Show: 50            │
├───────────────┬───────────────┬────────┬────────┬──────┬──────┬──────┬────────┤
│ Supplier      │ Invoice #     │ Date   │ Total  │ VAT  │ Conf │ St   │ ▸      │
│ ├☐ Bosch GmbH │ RE-2026-0142  │ 12.03  │ 1,284€ │ ✓    │ 98%  │ Done │        │
│ ├☐ ACME GmbH  │ R2026/0091    │ 11.03  │ 5,000€ │ ⚠    │ 72%  │ Review│       │
│ ├☐ Studio Fx  │ F-2026-077    │ 10.03  │ 320€   │ ✓    │ 94%  │ Done │        │
│ └☐ …          │               │        │        │      │      │      │        │
└──────────────────────────────────────────────────────────────────────────────┘
Selection checkboxes; row click → review. Column toggles; sticky header; virtualized.
Badges: Status (Done/Review/Failed/Queued), VAT (✓/⚠/✕), Confidence ring.
```

## 3. Review screen (the product)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ‹ 12/48   RE-2026-0142 · Bosch GmbH · 1,284.00 €          [Approve] [Reject] │
├──────────────────────────────┬───────────────────────────────────────────────┤
│  Document                     │  Fields (tabs: Header | Lines | Validation)   │
│  ┌─────────────────────────┐  │ ┌─────────────────────────────────────────┐  │
│  │  Bosch GmbH             │◄─│ │ Supplier name           98%  ✓ Bosch     │  │
│  │  USt-IdNr: DE811123456  │  │ │ VAT number              99%  ✓ DE81…     │  │
│  │                         │  │ │ Invoice number   [RE-2026-0142]    92%   │  │
│  │   RE-2026-0142          │  │ │ Invoice date      [12.03.2026]    96%   │  │
│  │   Item   Qty  Net  VAT  │  │ │ Due date          [12.04.2026]    88%   │  │
│  │   …                      │  │ │ ── validation ───────────────────────  │  │
│  │   Net: 1,079.00         │  │ │ ✓ VAT reconciles (19%)                  │  │
│  │   VAT:  205.01          │  │ │ ⚠ IBAN mod-97 FAILED                    │  │
│  │   Total:1,284.01        │  │ │ └ click → highlight + detail              │  │
│  └─────────────────────────┘  │ ┌─────────────────────────────────────────┐  │
│  [page dots ● ○ ○]            │ │ Lines                                   │  │
│  click field → highlight box  │ │ # │ desc   │ qty │ unit │ net │ VAT │gross││
│                               │ │ … grid editable inline                  │  │
│                               │ │ Σ subtotal 1,079.00 ✓ VAT 205.01 ✓      │  │
│                               │ └─────────────────────────────────────────┘  │
├──────────────────────────────┴───────────────────────────────────────────────┤
│ Ctrl/⌘+Enter approve · ←/→ next/prev · click badge shows source popover      │
└──────────────────────────────────────────────────────────────────────────────┘
```
Key interaction: clicking a field (or a validation warning) draws the source **bbox highlight** on the rendered page and shows a popover with OCR text + confidence + validator detail. Reviewers never hunt.

## 4. Field source popover

```
┌────────────────────────────────┐
│ VAT number · 99%  ✓            │
│ ─────────────────────────      │
│ "USt-IdNr.: DE811123456"       │  (mono, from OCR at bbox)
│ page 1 · y0.21                 │
│ method: regex+VIES             │
│ VIES: VALID (12.03.2026)       │
│ [Edit]  [Recompute]            │
└────────────────────────────────┘
```

## 5. Upload

```
┌──────────────────────────────────────────────────────────┐
│  Drop invoices anywhere                                    │
│  [or browse] [or paste]  max 20MB · PDF/PNG/JPG/HEIC/ZIP   │
│ ┌────────────────────────────────────────────────────┐    │
│ │ inv.pdf       ▓▓▓▓▓▓▓▓░ 71%  Processing…           │    │
│ │ scan_001.jpg  ✓ Done → review (2 fields flagged)   │    │
│ │ batch.zip     ✓ Done (12/12)                        │    │
│ └────────────────────────────────────────────────────┘    │
│  [Open review queue]                                      │
└──────────────────────────────────────────────────────────┘
```
Full-page drop overlay with animated target; per-file rows with progress, error, dedupe notice (`Already in your invoices →`).

## 6. Suppliers

```
┌────────────────────────────────────────────────────────┐
│ Suppliers                    [merge] [flag]             │
│ Bosch GmbH           128 inv · €48k · acc 98.1% · ✓    │
│ ACME GmbH            54  inv · €9.5k · acc 71.2% · ⚠   │
│ Studio Fx …                                            │
└────────────────────────────────────────────────────────┘
```

## 7. Settings / API keys / Webhooks

```
API keys:    iiq_uX2…pQ9L (Production)   scopes [invoices.rw, exports.w]
             created 01.03 · last used 3h ago  [rotate] [revoke]
             [+ Create key]  — shown ONCE, then hashed.
Webhooks:    https://erp.example.com/hook   events [completed, failed]
             last delivery: 200 OK 12s ago · [test] [log] [replay]
Usage:       Pages 1,244 / 10,000 · bar · cost estimate €/page by source
```

## 8. States & empty
- Empty inbox → illustration + "Drop your first invoice".
- Failed → banner with stage + error code + `Reprocess` action.
- Dark mode default; light mode toggle; all colors pass AA on critical badges.

## 9. Mobile (P2)
Read-only review + photo upload via web app; native app P4.
