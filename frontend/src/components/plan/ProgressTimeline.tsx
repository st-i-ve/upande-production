import { useEffect, useState } from "react";
import { Paperclip } from "lucide-react";
import { q, rowDate } from "@/components/plan/fmt";
import { listTaskProgress, type ProgressLog } from "@/lib/api";
import { isError } from "@/lib/frappe";

/** A task's progress logs, newest first. Re-reads when `refreshKey` changes. */
export function ProgressTimeline({ plan, task, refreshKey = 0 }: { plan: string; task: string; refreshKey?: number }) {
  const [logs, setLogs] = useState<ProgressLog[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void listTaskProgress(plan, task).then((r) => {
      if (!live) return;
      if (isError(r)) {
        setFailure(r.error);
        setLogs([]);
      } else {
        setFailure(null);
        setLogs([...(r as ProgressLog[])].sort((a, b) => (a.logged_at < b.logged_at ? 1 : a.logged_at > b.logged_at ? -1 : 0)));
      }
    });
    return () => {
      live = false;
    };
  }, [plan, task, refreshKey]);

  if (logs === null) return <p className="text-[13px] text-[var(--sd-muted)]">Loading…</p>;
  if (failure) return <p role="alert" className="text-[13px] text-[var(--sd-muted)]">{failure}</p>;
  if (logs.length === 0) return <p className="text-[13px] text-[var(--sd-muted)]">No progress logged yet.</p>;

  return (
    <ul className="flex flex-col divide-y divide-[var(--sd-line-soft)] rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-3.5 shadow-[var(--sd-shadow-inset)]">
      {logs.map((l) => {
        const images = l.attachments.filter((a) => !!a.is_image);
        const others = l.attachments.filter((a) => !a.is_image);
        return (
          <li key={l.name} className="flex flex-col gap-1.5 py-2.5 text-[13px]">
            <div className="flex items-center gap-2 text-[12.5px] text-[var(--sd-muted)]">
              <span className="font-medium text-[var(--sd-ink)]">{l.logged_by_name || l.logged_by}</span>
              <span className="tabular-nums">{rowDate(l.log_date)}</span>
              {l.qty > 0 && (
                <span className="ml-auto tabular-nums text-[var(--sd-ink)]">
                  {q(l.qty)}
                  {l.uom ? ` ${l.uom}` : ""}
                </span>
              )}
            </div>
            {l.notes && <p className="whitespace-pre-line text-[var(--sd-ink)]">{l.notes}</p>}
            {images.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {images.map((a) => (
                  <a key={a.file_url} href={a.file_url} target="_blank" rel="noreferrer">
                    <img src={a.file_url} alt={a.file_name} loading="lazy" className="size-20 rounded-[var(--sd-radius)] object-cover" />
                  </a>
                ))}
              </div>
            )}
            {others.map((a) => (
              <a key={a.file_url} href={a.file_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--sd-ink)] underline">
                <Paperclip className="size-3.5" aria-hidden />
                {a.file_name}
              </a>
            ))}
          </li>
        );
      })}
    </ul>
  );
}
