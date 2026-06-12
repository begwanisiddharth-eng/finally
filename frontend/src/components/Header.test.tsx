import { render, screen } from "@testing-library/react";
import { Header } from "./Header";
import { useStore } from "@/lib/store";
import { resetStore, mockPortfolio } from "@/lib/testUtils";

beforeEach(() => resetStore());

describe("Header", () => {
  test("shows placeholders before data loads", () => {
    render(<Header />);
    expect(screen.getByTestId("total-value")).toHaveTextContent("—");
  });

  test("renders total value and cash from the store", () => {
    useStore.setState({ portfolio: mockPortfolio });
    render(<Header />);
    expect(screen.getByTestId("total-value")).toHaveTextContent("$11,234.56");
    expect(screen.getByTestId("cash-balance")).toHaveTextContent("$8,500.00");
  });

  test("reflects connection status", () => {
    useStore.setState({ connection: "connected" });
    render(<Header />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "connected");
    expect(screen.getByText("Live")).toBeInTheDocument();
  });
});
