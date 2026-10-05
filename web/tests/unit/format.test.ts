import { describe, expect, it } from "vitest";
import { fmtAge, fmtDate, fmtMoney, fmtTime } from "@/lib/format";

describe("fmtMoney", () => {
  it("formats COP without decimals in es-CO and pt-BR", () => {
    expect(fmtMoney(184900, "COP", "es")).toBe("COP 184.900");
    expect(fmtMoney(184900, "COP", "pt")).toBe("COP 184.900");
  });
  it("formats USD with cents in the locale's style", () => {
    expect(fmtMoney(420, "USD", "es")).toBe("USD 420.00");
    expect(fmtMoney(420, "USD", "pt")).toBe("USD 420,00");
    expect(fmtMoney(1240.5, "USD", "es")).toBe("USD 1,240.50");
  });
  it("never prints a raw float", () => {
    expect(fmtMoney(0.1 + 0.2, "USD", "es")).toBe("USD 0.30");
  });
});

describe("fmtDate", () => {
  it("formats an ISO date in the locale without timezone drift", () => {
    expect(fmtDate("2026-06-17", "es")).toMatch(/17.*jun.*2026/);
    expect(fmtDate("2026-06-17", "pt")).toMatch(/17.*jun.*2026/);
  });
});

describe("fmtAge", () => {
  it("shows minutes, hours and days", () => {
    const now = new Date("2026-09-30T12:00:00Z");
    expect(fmtAge("2026-09-30T11:58:00Z", now)).toBe("2 min");
    expect(fmtAge("2026-09-30T09:00:00Z", now)).toBe("3 h");
    expect(fmtAge("2026-09-28T12:00:00Z", now)).toBe("2 d");
  });
});

describe("fmtTime", () => {
  it("shows hours and minutes in the customer's locale", () => {
    expect(fmtTime("2026-10-05T14:05:00.000000+00:00", "es", "UTC")).toBe("14:05");
    expect(fmtTime("2026-10-05T09:30:00Z", "pt", "UTC")).toBe("09:30");
  });
  it("is empty for a timestamp it can't read", () => {
    expect(fmtTime("t", "es")).toBe("");
  });
});
