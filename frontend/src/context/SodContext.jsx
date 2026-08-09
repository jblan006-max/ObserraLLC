import { createContext, useContext } from "react";

// Shared SoD Command Center state/handlers. The parent (SodCommandCenter) builds the value once
// and its extracted cards read what they need via useSod(), removing the 50+ prop pass-throughs.
const SodContext = createContext(null);

export function SodProvider({ value, children }) {
  return <SodContext.Provider value={value}>{children}</SodContext.Provider>;
}

export const useSod = () => useContext(SodContext);
