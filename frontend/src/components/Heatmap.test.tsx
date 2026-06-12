import { render, screen } from "@testing-library/react";
import { Heatmap } from "./Heatmap";
import { useStore } from "@/lib/store";
import { resetStore, mockPortfolio } from "@/lib/testUtils";

beforeEach(() => resetStore());

describe("Heatmap", () => {
  test("shows empty state without positions", () => {
    render(<Heatmap />);
    expect(screen.getByText("No positions yet")).toBeInTheDocument();
  });

  test("renders one tile per position", () => {
    useStore.setState({ portfolio: mockPortfolio });
    render(<Heatmap />);
    expect(screen.getByTestId("heat-tile-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("heat-tile-TSLA")).toBeInTheDocument();
  });
});
