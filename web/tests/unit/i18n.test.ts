import { describe, expect, it } from "vitest";
import { t } from "@/lib/i18n";

describe("i18n", () => {
  it("has the same keys in es and pt", () => {
    expect(Object.keys(t("pt")).sort()).toEqual(Object.keys(t("es")).sort());
    expect(Object.keys(t("pt").reasons).sort()).toEqual(Object.keys(t("es").reasons).sort());
  });
  it("interpolates names and dates", () => {
    expect(t("es").agentJoined("Ana R.")).toBe("Ana R., del equipo de LATAM Bank, se unió");
    expect(t("pt").asOf("17 de jun. de 2026")).toBe("Informações de 17 de jun. de 2026");
  });
});
