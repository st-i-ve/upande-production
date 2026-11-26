export function DraftBar({ restored, onDiscard }: { restored: boolean; onDiscard: () => void }) {
  if (!restored) return null;
  return (
    <div className="flex items-center justify-between rounded-md border border-[var(--sd-line)] bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground">
      <span>Draft restored</span>
      <button type="button" className="font-medium underline underline-offset-2 hover:text-foreground" onClick={onDiscard}>
        Discard
      </button>
    </div>
  );
}
