import { render, screen } from "@testing-library/react";
import { PositionsTable } from "./PositionsTable";
import { useStore } from "@/lib/store";
import { resetStore, mockPortfolio } from "@/lib/testUtils";

beforeEach(() => resetStore());

describe("PositionsTable", () => {
  test("shows empty state with no positions", () => {
    render(<PositionsTable />);
    expect(screen.getByText("No open positions")).toBeInTheDocument();
  });

  test("renders a row per position with computed P&L", () => {
    useStore.setState({ portfolio: mockPortfolio });
    render(<PositionsTable />);

    const aapl = screen.getByTestId("position-row-AAPL");
    expect(aapl).toHaveTextContent("AAPL");
    expect(aapl).toHaveTextContent("$1,955.00"); // market value
    expect(aapl).toHaveTextContent("+2.89%");

    const tsla = screen.getByTestId("position-row-TSLA");
    expect(tsla).toHaveTextContent("-1.96%");
    expect(tsla).toHaveTextContent("-$24.50"); // negative unrealized P&L
  });

  test("clicking a row selects that ticker", () => {
    useStore.setState({ portfolio: mockPortfolio });
    render(<PositionsTable />);
    screen.getByTestId("position-row-TSLA").click();
    expect(useStore.getState().selectedTicker).toBe("TSLA");
  });
});
