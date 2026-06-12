import { money, price, pct, qty, pnlColor } from "./format";

describe("format helpers", () => {
  test("money renders USD with two decimals", () => {
    expect(money(11234.5)).toBe("$11,234.50");
    expect(money(0)).toBe("$0.00");
  });

  test("price renders grouped two-decimal numbers", () => {
    expect(price(1955)).toBe("1,955.00");
    expect(price(195.5)).toBe("195.50");
  });

  test("pct prefixes sign and appends percent", () => {
    expect(pct(2.89)).toBe("+2.89%");
    expect(pct(-1.96)).toBe("-1.96%");
    expect(pct(0)).toBe("0.00%");
  });

  test("qty keeps integers clean and fractions to 3dp", () => {
    expect(qty(10)).toBe("10");
    expect(qty(0.5)).toBe("0.500");
  });

  test("pnlColor maps sign to tailwind class", () => {
    expect(pnlColor(5)).toBe("text-gain");
    expect(pnlColor(-5)).toBe("text-loss");
    expect(pnlColor(0)).toBe("text-muted");
  });
});
