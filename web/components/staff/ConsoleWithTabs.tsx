"use client";
import { Console } from "./Console";

// Tabs are filled in by units 72-73; placeholders until then.
export function ConsoleWithTabs(props: { me: { sub: string; name: string }; initialId?: string }) {
  return <Console {...props} renderTab={(tab) => <p className="text-sm text-c-muted">{tab[0].toUpperCase() + tab.slice(1)} tab arrives in the next unit.</p>} />;
}
