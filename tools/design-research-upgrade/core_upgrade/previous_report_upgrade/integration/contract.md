## Proposed-method report extension

For `research --report-profile proposed-method`, add `method_ideas` to the dossier. Its base structure is the existing `method_ideation.py` schema, with the baseline's `id` linked to the dossier and a `presentation` on the selected candidate. See `proposed-method-report.md` for the exact fields.

All compared candidate IDs and names, source identities/read levels, component references and verification experiment IDs must agree with the dossier. The run's target count is frozen (default 5). The parent runs both the existing evidence/receipt validation and the new design-description validation; neither one replaces the other. Graph files are conceptual design artifacts, not successful experiment receipts.
