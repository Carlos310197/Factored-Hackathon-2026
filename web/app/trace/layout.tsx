import { BuildTag } from "@/components/staff/BuildTag";

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <BuildTag />
    </>
  );
}
