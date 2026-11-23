# Design

Canonical DocRequirement.doc_type == PAYMENT_RECEIPT selects manual processing before the shared assessment reader. A file-envelope check opens PDF/images without reading text, computing quality or classifying content; malformed/empty/encrypted files are request errors, not automatic document FAILs. Save NEEDS_REVIEW with a dedicated reason and no OCR measurements. Keep the explicit-slot, single-file flow and existing original streaming.

During application review exclude receipt requirements and their document rows from the automatic engine, then append original references and a manual-review reason, preserving FAIL precedence from other documents. Receipt presence remains governed by the ordinary required-slot blocker. Preserve stored historic data and decision records; no backfill. Existing officer memo/decision/CAS is the only result-writing flow. Show a manual-review panel in the existing detail viewer.

Auto splitting is already rejected before file processing. A combined PDF in a receipt slot covers only that receipt slot; the same source must be uploaded to each other required slot, where normal OCR still runs.
