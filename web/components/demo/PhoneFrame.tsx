import { forwardRef } from "react";

export const PhoneFrame = forwardRef<HTMLIFrameElement, { src: string }>(function PhoneFrame({ src }, ref) {
  return (
    <div className="rounded-[34px] ring-[10px] ring-b-ink shadow-xl overflow-hidden bg-b-surface w-[340px] h-[660px] shrink-0">
      <iframe ref={ref} src={src} title="Customer's phone" className="w-full h-full border-0" />
    </div>
  );
});
