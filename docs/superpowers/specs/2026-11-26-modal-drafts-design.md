# Modals close only on X; unsaved form work kept as a draft

Date: 2026-11-26. User: "when a modal is open and someone clicks away ... it doesn't close and lose their work, it should
save as draft ... close the modal not by clicking away but only clicking the x".

## Desk (frontend/)
- The shared dialog (frontend/src/components/ui/dialog.tsx) ignores outside clicks/pointer-downs and Escape
  (Claude's call: Escape too — as easy to hit by accident). Close only via the ✕ button or a dialog's own
  Cancel/Done buttons. Confirm-style dialogs behave the same.
- Drafts: a hook `useDialogDraft({ key, value, setValue, open, isDirty? })` stores a form's state in browser
  localStorage under `draft:<user>:<key>` when the dialog closes (or every few seconds while dirty) without a save,
  restores it on the next open with a bar "Draft restored · Discard", and clears it on successful save. Drafts older
  than 7 days are dropped on read. Keys include the record (e.g. `edit-cycle:CYC-2026-0071`, `add-task:<plan>`).
  Wrapped in try/catch (storage may be unavailable). Files/attachments are not stored in drafts (names only noted).
- Apply to every form dialog (dialogs where the user types or picks values before saving); read-only/confirm
  dialogs only get the close rule.
## Phone (reactnative/upande-production)
- Bottom sheets close only via their ✕ (no backdrop tap, Android back button asks "Keep as draft?" no — back keeps
  the draft and closes, same as ✕).
- Extend the existing record-draft mechanism (useRecordDraft, "Continue recording") to the add-task, log-progress
  and resubmit sheets.
