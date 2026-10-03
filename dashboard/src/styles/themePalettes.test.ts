import { describe, expect, it } from "vitest";
import {
  ANTD_BRAND_TOKENS,
  DEFAULT_PALETTE,
  VALID_PALETTES,
  brandPrimary,
} from "./themePalettes";

function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map((offset) => {
    const value = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });

  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(foreground: string, background: string): number {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  const lighter = Math.max(foregroundLuminance, backgroundLuminance);
  const darker = Math.min(foregroundLuminance, backgroundLuminance);
  return (lighter + 0.05) / (darker + 0.05);
}

describe("theme palettes", () => {
  it("exposes the curated palette set", () => {
    expect(VALID_PALETTES).toEqual([
      "mint",
      "tech",
      "indigo",
      "teal",
      "violet",
      "emerald",
      "amber",
      "slate",
    ]);
  });

  it("uses the xiaoyibao mint brand sampled from the product logo", () => {
    expect(DEFAULT_PALETTE).toBe("mint");
    expect(ANTD_BRAND_TOKENS.mint.light.colorPrimary).toBe("#2F8F80");
    expect(ANTD_BRAND_TOKENS.mint.light.colorPrimaryHover).toBe("#26796C");
    expect(ANTD_BRAND_TOKENS.mint.light.colorPrimaryActive).toBe("#1F6459");
    // Dark mode lightens the brand so it stays legible on dark surfaces.
    expect(ANTD_BRAND_TOKENS.mint.dark.colorPrimary).toBe("#5FC7B4");
    expect(ANTD_BRAND_TOKENS.mint.dark.colorLink).toBe("#5FC7B4");
  });

  it.each(VALID_PALETTES.filter((palette) => palette !== "mint"))(
    "keeps %s solid Ant Design states readable with white text",
    (palette) => {
      for (const mode of ["light", "dark"] as const) {
        const tokens = ANTD_BRAND_TOKENS[palette][mode];
        for (const color of [
          tokens.colorPrimary,
          tokens.colorPrimaryHover,
          tokens.colorPrimaryActive,
        ]) {
          expect(contrastRatio(color, "#FFFFFF")).toBeGreaterThanOrEqual(4.5);
        }
      }
    },
  );

  it.each(VALID_PALETTES)(
    "uses the brighter %s link color for dark charts",
    (palette) => {
      expect(brandPrimary(palette, true)).toBe(
        ANTD_BRAND_TOKENS[palette].dark.colorLink,
      );
    },
  );
});
