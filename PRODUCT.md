# Product

<!-- impeccable:product-schema 1 -->

Full requirements live in `docs/SPEC.md`; working rules in `CLAUDE.md`. This file is the short product record the design skills read.

## Platform

web

## Stack

React 18 + Vite in plain JavaScript (JSX), React Router v7 (7.18+, switched from v6 at the user's request to clear security advisories), Axios, Recharts, Tailwind CSS v4. Backend FastAPI + MongoDB. Confirmed by the user (2026-10-19).

## Users

- **IQAC coordinator (admin):** sets up departments, courses, cycles and forms; runs analysis; reviews the moderation queue; builds the NAAC 1.4 report. Works in long desk sessions near the end of each semester.
- **Head of department (HoD):** reviews faculty pages and the bias & sarcasm panel for their department; approves Action Taken entries.
- **Faculty:** maintain their profile data, approve the generated profile, read moderated and redacted feedback about their own courses, respond to improvement areas.
- **Students:** log in with a roll number and submit one anonymous feedback form per course per cycle. They never see analysis.

## Product Purpose

Turn semester feedback that is usually read by hand, or not at all, into a fair, evidence-backed picture of teaching. Put it on one page beside an auto-generated faculty profile, and export what NAAC Criterion 1.4 asks for.

## Positioning

One page per faculty member that joins an LLM-written, fact-grounded profile with aspect-level teaching insights. Every strength or improvement links to the redacted sentences behind it. Comments are moderated and redacted before faculty see them. Unreliable signals (sarcasm, possible gendered language) are flagged, not hidden.

## Operating Context

Indian engineering college; B.Tech mini project demo on an unknown Windows PC with no GPU (4 cores, 8 GB RAM assumed). Feedback cycles per semester (for example "2026-27 Odd Sem"). NAAC accreditation paperwork is the external ritual the report serves.

## Capabilities and Constraints

- CPU-only NLP, cached per comment; the app must work with no Groq key (no-LLM fallback) and offline after models are downloaded.
- Students are anonymous to faculty. Comment-level detail is hidden below `MIN_RESPONSES_FOR_DISPLAY` responses.
- Feedback comes only from in-app student submissions (no CSV upload).
- Out of scope: code-mixed language models, trend alerts, chatbot, mobile app.

## Evidence on Hand

No real feedback yet. Seed data will be synthetic, marked `is_synthetic`, and excluded from evaluation. Never invent metrics, testimonials or institution facts. Every number on screen comes from the API.

## Product Principles

1. Evidence before opinion: every claim on a faculty page links to the sentences that support it.
2. Protect both sides: student anonymity and faculty dignity (moderation, redaction, minimum counts).
3. Flag uncertainty openly rather than smoothing it away.
4. Honest numbers only: measured on this hardware, from `ml/results/` and the API.

## Accessibility & Inclusion

WCAG AA contrast, full keyboard navigation, visible focus, `prefers-reduced-motion` respected. Charts never rely on red/green alone and always carry text labels.
