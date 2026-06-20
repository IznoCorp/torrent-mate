// Reactive viewport check for the mobile layout branch (responsive mobile, DESIGN §3).
// 768px = phones + small tablets portrait. Re-renders when the viewport crosses the breakpoint.
import React from "react";

const QUERY = "(max-width: 768px)";

export default function useIsMobile() {
  const get = () =>
    typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia(QUERY).matches
      : false;
  const [isMobile, setIsMobile] = React.useState(get);
  React.useEffect(() => {
    const mq = window.matchMedia(QUERY);
    const onChange = () => setIsMobile(mq.matches);
    mq.addEventListener("change", onChange);
    onChange(); // sync in case it changed between render and effect
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return isMobile;
}
