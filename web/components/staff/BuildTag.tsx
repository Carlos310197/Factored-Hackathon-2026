export function BuildTag() {
  const sha = process.env.NEXT_PUBLIC_GIT_SHA;
  if (!sha) return null;
  return <footer className="px-4 py-2 text-[11px] text-c-muted tabular-nums">build {sha.slice(0, 7)}</footer>;
}
