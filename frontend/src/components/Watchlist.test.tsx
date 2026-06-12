import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Watchlist } from "./Watchlist";
import { useStore } from "@/lib/store";
import { resetStore, mockWatchlist } from "@/lib/testUtils";
import { api } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    addTicker: jest.fn().mockResolvedValue({}),
    removeTicker: jest.fn().mockResolvedValue({}),
  },
}));

beforeEach(() => {
  resetStore();
  jest.clearAllMocks();
});

describe("Watchlist", () => {
  test("renders rows with prices and change percent", () => {
    useStore.setState({
      watchlist: mockWatchlist,
      prices: {
        AAPL: { price: 195.5, prev_price: 194.2, session_open: 190, change_pct: 2.89, direction: "up", tick: 1 },
        TSLA: { price: 245.1, prev_price: 248, session_open: 250, change_pct: -1.96, direction: "down", tick: 1 },
      },
    });
    render(<Watchlist />);
    expect(screen.getByTestId("watch-price-AAPL")).toHaveTextContent("195.50");
    expect(screen.getByTestId("watch-row-TSLA")).toHaveTextContent("-1.96%");
  });

  test("add ticker calls the API and inserts a row", async () => {
    const user = userEvent.setup();
    render(<Watchlist />);

    await user.type(screen.getByTestId("watch-add-input"), "nvda");
    await user.click(screen.getByTestId("watch-add-btn"));

    expect(api.addTicker).toHaveBeenCalledWith("NVDA");
    expect(useStore.getState().watchlist.some((w) => w.ticker === "NVDA")).toBe(true);
  });

  test("remove ticker calls the API and drops the row", async () => {
    const user = userEvent.setup();
    useStore.setState({ watchlist: mockWatchlist });
    render(<Watchlist />);

    await user.click(screen.getByTestId("watch-remove-AAPL"));

    expect(api.removeTicker).toHaveBeenCalledWith("AAPL");
    expect(useStore.getState().watchlist.some((w) => w.ticker === "AAPL")).toBe(false);
  });

  test("price flash class appears when a price ticks", () => {
    useStore.setState({
      watchlist: [mockWatchlist[0]],
      prices: { AAPL: { price: 195, prev_price: 194, session_open: 190, change_pct: 2.6, direction: "up", tick: 1 } },
    });
    render(<Watchlist />);
    const cell = screen.getByTestId("watch-price-AAPL");
    expect(cell.className).not.toMatch(/animate-flash/);

    act(() => {
      useStore.setState({
        prices: { AAPL: { price: 196, prev_price: 195, session_open: 190, change_pct: 3.1, direction: "up", tick: 2 } },
      });
    });
    expect(screen.getByTestId("watch-price-AAPL").className).toMatch(/animate-flash-up/);
  });
});
