/** POST the logout route for one cookie; a failed fetch still lets the caller navigate to login. */
export async function signOut(who: "customer" | "staff"): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ who }) });
  } catch { /* navigate anyway */ }
}
