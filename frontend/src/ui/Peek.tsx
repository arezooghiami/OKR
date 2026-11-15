import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { Icon } from "./parts";

interface PeekApi { open: (node: ReactNode) => void; close: () => void; isOpen: boolean }
const Ctx = createContext<PeekApi>({ open: () => {}, close: () => {}, isOpen: false });
export const usePeek = () => useContext(Ctx);

/** Side panel (bottom sheet on phones). Esc closes. */
export function PeekProvider({ children }: { children: ReactNode }) {
  const [node, setNode] = useState<ReactNode>(null);
  const close = useCallback(() => setNode(null), []);
  const open = useCallback((n: ReactNode) => setNode(n), []);
  const { pathname } = useLocation();
  // the panel belongs to the page it was opened on: leaving the page (e.g. a link inside it) closes it
  useEffect(() => setNode(null), [pathname]);

  useEffect(() => {
    if (!node) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [node, close]);

  return (
    <Ctx.Provider value={{ open, close, isOpen: node !== null }}>
      {children}
      <aside className={`peek ${node ? "on" : ""}`} aria-label="جزئیات" aria-hidden={!node}>
        <button className="ib x" aria-label="بستن" onClick={close}><Icon d="M6 6l12 12M18 6L6 18" /></button>
        {node}
      </aside>
    </Ctx.Provider>
  );
}
