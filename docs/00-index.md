# InvoiceIQ — Documentation Index

> InvoiceIQ: the AI accounts-payable employee for European SMEs. Upload an invoice in any format — scanned or digital PDF, image, mobile photo, email attachment — and receive validated, accounting-ready data with per-field confidence, human review, and audit trail.

**Status:** Draft v0.1 · **Round:** 1 (Core technical package) · **Owner:** CTO/Founder

## Decisions locked (2026)

| Decision | Choice | Rationale |
|---|---|---|
| Scope of this round | Core technical package | Marketing/GTM deliverables (GTM, demo, landing copy, pricing, pitch, future features) follow in Round 2 |
| Data residency | **EU-only by default**; US LLMs per-tenant opt-in with DPA | GDPR/Schrems II sales differentiator; Klippa-style wedge |
| Deployment | Single EU VPS first (Hetzner/OVH), Docker Compose → K8s later | Solo-founder economics; clean migration path documented |
| MVP | Extraction core + review + export + API | Fastest path to first paying customer; no billing/SSO/email/workflows |
| Working name | InvoiceIQ | Alternatives: InvoicePilot, Extractly, LedgerAI, InvoiceFlow AI. Revisit before launch |
| Queue broker | Celery + Redis | Redis already required; RabbitMQ is a config swap at scale |
| Default LLM | Mistral (EU, France) | EU-hosted, GDPR-clean, low cost; OpenAI/Claude/Gemini in registry as opt-in |
| Dev machine | Host-run Next/FastAPI, Docker for Postgres/Redis only | 16 GB RAM / 22 GB free disk — see `docs/17` §DevMachine |

## Deliverable map (25 total; 19 in this round)

| # | Deliverable | File | Round |
|---|---|---|---|
| 1 | Product Requirements Document | `docs/01-product-requirements.md` | 1 |
| 2 | Technical Architecture | `docs/02-technical-architecture.md` | 1 |
| 3 | System Design | `docs/03-system-design.md` | 1 |
| 4 | Database Schema | `docs/04-database-schema.md` | 1 |
| 5 | API Specification | `docs/05-api-specification.md` | 1 |
| 6 | Folder Structure | `docs/06-folder-structure.md` | 1 |
| 7 | Development Roadmap | `docs/07-development-roadmap.md` | 1 |
| 8 | MVP Scope | `docs/08-mvp-scope.md` | 1 |
| 9 | Enterprise Roadmap | `docs/09-enterprise-roadmap.md` | 1 |
| 10 | UI Wireframes | `docs/10-ui-wireframes.md` | 1 |
| 11 | Component List | `docs/11-component-list.md` | 1 |
| 12 | AI Pipeline | `docs/12-ai-pipeline.md` | 1 |
| 13 | Prompt Engineering Strategy | `docs/13-prompt-strategy.md` | 1 |
| 14 | OCR Strategy | `docs/14-ocr-strategy.md` | 1 |
| 15 | Validation Rules | `docs/15-validation-rules.md` | 1 |
| 16 | Testing Strategy | `docs/16-testing-strategy.md` | 1 |
| 17 | Deployment Guide | `docs/17-deployment-guide.md` | 1 |
| 18 | Security Checklist | `docs/18-security-checklist.md` | 1 |
| 19 | GDPR Checklist | `docs/19-gdpr-checklist.md` | 1 |
| 20 | Go-to-Market Strategy | Round 2 | 2 |
| 21 | Demo Script | Round 2 | 2 |
| 22 | Landing Page Copy | Round 2 | 2 |
| 23 | Pricing Strategy | Round 2 | 2 |
| 24 | Investor Pitch Outline | Round 2 | 2 |
| 25 | Future AI Features | Round 2 | 2 |

## Reading order
Product people: 01 → 08 → 10 → 11 → 09 → 20 (Round 2).
Engineers: 02 → 03 → 12 → 14 → 13 → 15 → 04 → 05 → 06 → 16 → 17 → 18 → 19 → 07.
Everyone: start at 01.

## Market context (research, 2026)
- Manual invoice entry costs **$12–20/invoice**; automated best-in-class ~$2.78 (78% gap).
- Competitor pricing: Rossum ~$18k+/yr (enterprise-only), Veryfi ~$350/mo for 500 docs, Mindee ~$0.10/page but **no validation, fraud, or human-review UX**, Nanonets/Docsumo mid-market $500+/mo.
- SMB per-page processing runs **$0.05–0.30** — InvoiceIQ must land in this band with EU residency as the wedge.
- **EU AI Act fully applicable Aug 2, 2026**: invoice extraction is minimal/low-risk but requires transparency (AI-disclosure), human-in-the-loop for decisions, logging, and EU-resident processing preference.
- Benchmarks: dedicated IDP ~98.7% field accuracy; VLM direct-image 90–96% zero-template; hybrid OCR→LLM is industry best practice and the cheapest robust path.
