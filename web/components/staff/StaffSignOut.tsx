"use client";
import { useRouter } from "next/navigation";
import { signOut } from "@/lib/signout";

/** Clears only the staff cookie: the customer one may coexist on /demo. */
export function StaffSignOut({ className = "" }: { className?: string }) {
  const router = useRouter();
  return (
    <button type="button" onClick={() => void signOut("staff").then(() => router.replace("/login?staff=1"))}
      className={`rounded px-2 py-1 text-xs font-semibold underline focus-visible:outline-2 focus-visible:outline-c-signal ${className}`}>
      Sign out
    </button>
  );
}
