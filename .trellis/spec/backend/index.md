# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains guidelines for backend development. Fill in each file with your project's specific conventions.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | To fill |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | To fill |
| [Error Handling](./error-handling.md) | Error types, handling strategies | To fill |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | To fill |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | To fill |
| [Income and age eligibility](./income-eligibility.md) | Tri-state membership, exact income bounds, age and final-review consistency | Active |
| [Confirmed failure filtering](./failure-filtering.md) | Upload certainty, provisional continuity and submission blockers | Active |
| [Document OCR and Form Contracts](./document-form-contracts.md) | Resident-number redaction, coordinate forms, arithmetic, identity and review boundaries | Active |
| [Demo stage-two seeding](./seed-application.md) | Guarded developer CLI, shared validation, ownership cleanup and same-tab upload restoration | Active |
| [Private case verification](./verify-cases.md) | Shared upload assessments, ignored manifests, value-free snapshots and signed regression differences | Active |
| [Application and officer access](./application-access.md) | Owner cookies, signed officer sessions, projections and authenticated test fixtures | Active |
| [Generic program review](./generic-program-review.md) | Posting boundaries, evidence confirmations and shared decision guards | Active |
| [Public notice drafts](./notice-drafts.md) | Provenance, conservative grammar and existing-rule bindings | Active |
| [Form draft detection](./form-draft-detection.md) | Inline blanks, choice words, signature marks, false-positive guards, dedupe and officer snap | Active |
| [Scanned resident completeness](./resident-scan-completeness.md) | 11-26 temporary no-auto-PASS guard for OCR-read 초본, end evidence, audit field and re-allow conditions | Active |
| [Common OCR parity](./common-ocr-parity.md) | 11-27 common OCR (pipeline, PP-OCRv5 ONNX, 초본 extractor and completeness signals, page integrity) identical in savings-officer and youth; manifest + CI parity test; business rules separate | Active |
| [Officer reason projection](./officer-reason-projection.md) | 11-27 response-time mapping of stored stage1 reasons to each document's actual review reason; scan completeness vs OCR confidence; audit origin | Active |

---

## How to Fill These Guidelines

For each guideline file:

1. Document your project's **actual conventions** (not ideals)
2. Include **code examples** from your codebase
3. List **forbidden patterns** and why
4. Add **common mistakes** your team has made

The goal is to help AI assistants and new team members understand how YOUR project works.

---

**Language**: All documentation should be written in **English**.

- [Review integrity and household discovery](./review-integrity.md): lifetime DML guards, cross-application preservation, mixed-version tests and seed retention.

- [Manual youth receipts](./receipt-manual-review.md): receipt-only OCR exclusion, original-presence and existing CAS audit boundary.
