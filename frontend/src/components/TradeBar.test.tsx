import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TradeBar } from "./TradeBar";
import { useStore } from "@/lib/store";
import { resetStore } from "@/lib/testUtils";
import { api } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    trade: jest.fn(),
    reset: jest.fn().mockResolvedValue({ ok: true }),
    getPortfolio: jest.fn().mockResolvedValue({ cash_balance: 10000, total_value: 10000, positions: [] }),
    getHistory: jest.fn().mockResolvedValue([]),
  },
}));

beforeEach(() => {
  resetStore();
  jest.clearAllMocks();
});

describe("TradeBar", () => {
  test("buy submits ticker, quantity, and side", async () => {
    (api.trade as jest.Mock).mockResolvedValue({
      ok: true,
      ticker: "AAPL",
      side: "buy",
      quantity: 3,
      price: 195.5,
    });
    const user = userEvent.setup();
    render(<TradeBar />);

    await user.type(screen.getByTestId("trade-ticker"), "aapl");
    await user.type(screen.getByTestId("trade-quantity"), "3");
    await user.click(screen.getByTestId("trade-buy"));

    expect(api.trade).toHaveBeenCalledWith("AAPL", 3, "buy");
    expect(await screen.findByTestId("trade-status")).toHaveTextContent("Bought 3 AAPL");
  });

  test("rejects empty or non-positive quantity without calling the API", async () => {
    const user = userEvent.setup();
    render(<TradeBar />);
    await user.type(screen.getByTestId("trade-ticker"), "AAPL");
    await user.click(screen.getByTestId("trade-buy"));
    expect(api.trade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-status")).toHaveTextContent(/positive quantity/i);
  });

  test("reset calls the reset endpoint", async () => {
    const user = userEvent.setup();
    render(<TradeBar />);
    await user.click(screen.getByTestId("trade-reset"));
    expect(api.reset).toHaveBeenCalled();
    expect(await screen.findByTestId("trade-status")).toHaveTextContent(/reset/i);
  });

  test("falls back to the selected ticker when input is empty", async () => {
    (api.trade as jest.Mock).mockResolvedValue({
      ok: true, ticker: "TSLA", side: "sell", quantity: 2, price: 245,
    });
    useStore.setState({ selectedTicker: "TSLA" });
    const user = userEvent.setup();
    render(<TradeBar />);
    await user.type(screen.getByTestId("trade-quantity"), "2");
    await user.click(screen.getByTestId("trade-sell"));
    expect(api.trade).toHaveBeenCalledWith("TSLA", 2, "sell");
  });
});
