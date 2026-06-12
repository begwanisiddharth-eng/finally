import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "./ChatPanel";
import { useStore } from "@/lib/store";
import { resetStore } from "@/lib/testUtils";
import { api } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    chat: jest.fn(),
    getPortfolio: jest.fn().mockResolvedValue({ cash_balance: 0, total_value: 0, positions: [] }),
    getWatchlist: jest.fn().mockResolvedValue([]),
    getHistory: jest.fn().mockResolvedValue([]),
  },
}));

beforeEach(() => {
  resetStore();
  jest.clearAllMocks();
});

describe("ChatPanel", () => {
  test("shows an empty-state prompt initially", () => {
    render(<ChatPanel />);
    expect(screen.getByText(/Ask me about your portfolio/i)).toBeInTheDocument();
  });

  test("renders existing user and assistant messages with trade chips", () => {
    useStore.setState({
      chat: [
        { id: "1", role: "user", content: "Buy 10 AAPL" },
        {
          id: "2",
          role: "assistant",
          content: "Done.",
          trades: [{ ticker: "AAPL", side: "buy", quantity: 10, price: 195.5, ok: true }],
        },
      ],
    });
    render(<ChatPanel />);
    expect(screen.getByTestId("chat-msg-user")).toHaveTextContent("Buy 10 AAPL");
    expect(screen.getByTestId("chat-msg-assistant")).toHaveTextContent("Done.");
    expect(screen.getByTestId("chat-trade")).toHaveTextContent("10 AAPL");
  });

  test("sending a message calls the API and appends the reply", async () => {
    (api.chat as jest.Mock).mockResolvedValue({
      message: "Bought it.",
      trade_results: [{ ticker: "AAPL", side: "buy", quantity: 5, price: 195, ok: true }],
    });
    const user = userEvent.setup();
    render(<ChatPanel />);

    await user.type(screen.getByTestId("chat-input"), "buy 5 aapl");
    await user.click(screen.getByTestId("chat-send"));

    expect(api.chat).toHaveBeenCalledWith("buy 5 aapl");
    expect(await screen.findByText("Bought it.")).toBeInTheDocument();
    const messages = useStore.getState().chat;
    expect(messages).toHaveLength(2);
    expect(messages[0].content).toBe("buy 5 aapl");
  });
});
