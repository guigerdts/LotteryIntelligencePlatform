import { useEffect, useRef, useState } from "react";

/**
 * Tracks elapsed whole seconds while `active` is true. Resets to 0 each time
 * the timer (re)starts and clears the interval on stop/unmount. Used to
 * reassure users during long, non-incremental backend computes — the backend
 * returns one answer after minutes, so this is elapsed time, never fake
 * progress.
 */
export function useElapsedTime(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  const startRef = useRef(0);

  useEffect(() => {
    if (!active) return;
    startRef.current = Date.now();
    setSeconds(0);
    const id = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, [active]);

  return seconds;
}

/** Format a seconds count as M:SS for compact display. */
export function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
