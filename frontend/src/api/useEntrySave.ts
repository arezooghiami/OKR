import { useCallback, useEffect, useRef } from "react";
import { api } from "./client";
import { parseNumber } from "../domain/format";

export type SaveState = "saving" | "saved" | "error";

/** Saves one KR's value + note for a round.
 *  - Saves only when asked (blur / Enter), never mid-typing, so half-typed numbers don't reach the audit log.
 *  - One request in flight at a time: a newer value waits for the previous response and goes out with the
 *    version it returned, so fast edits never cause a false "someone else changed this" conflict.
 *  - Skips a save when nothing changed since the last one, and flushes a pending change when the card unmounts. */
export function useEntrySave(opts: {
  sessionId: string | null | undefined;
  krId: string;
  entryVersion: number | null | undefined;
  initial: { val: string; note: string };
  onState: (s: SaveState, detail?: string) => void;
  onSaved?: (value: number | null) => void;
}) {
  const version = useRef<number | null>(opts.entryVersion ?? null);
  const saved = useRef(key(opts.initial.val, opts.initial.note));
  const inFlight = useRef(false);
  const queued = useRef<{ val: string; note: string } | null>(null);
  const latest = useRef(opts);
  latest.current = opts;

  const send = useCallback((val: string, note: string) => {
    const { sessionId, krId, onState, onSaved } = latest.current;
    const v = parseNumber(val);
    if (v === undefined || !sessionId) return;
    const k = key(val, note);
    if (k === saved.current) return;
    if (inFlight.current) { queued.current = { val, note }; return; }
    inFlight.current = true;
    onState("saving");
    api<{ entry_version: number }>(`/sessions/${sessionId}/entries/${krId}`, {
      method: "PUT", body: { value: v, note: note.trim() || null, expected_version: version.current },
    })
      .then((r) => { version.current = r.entry_version; saved.current = k; latest.current.onState("saved"); onSaved?.(v); })
      .catch((e: Error) => { queued.current = null; latest.current.onState("error", e.message); })
      .finally(() => {
        inFlight.current = false;
        const next = queued.current;
        queued.current = null;
        if (next) send(next.val, next.note);
      });
  }, []);

  const pending = useRef<{ val: string; note: string }>(opts.initial);
  /** Remember the latest text without saving (call from onChange). */
  const track = useCallback((val: string, note: string) => { pending.current = { val, note }; }, []);
  /** Save the latest text now (call from onBlur / Enter). */
  const flush = useCallback(() => send(pending.current.val, pending.current.note), [send]);

  // leaving the page or closing the card: don't lose a typed value
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (key(pending.current.val, pending.current.note) !== saved.current && parseNumber(pending.current.val) !== undefined) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => { window.removeEventListener("beforeunload", warn); flush(); };
  }, [flush]);

  return { track, flush };
}

const key = (val: string, note: string) => `${parseNumber(val) ?? ""}\u0000${note.trim()}`;
