import "@testing-library/jest-dom";

// lightweight-charts is ESM-only and draws on canvas; the manual mock in
// __mocks__/lightweight-charts.ts is picked up automatically for all tests.

// Stub the 2D canvas context used by the Sparkline component.
HTMLCanvasElement.prototype.getContext = jest.fn(() => ({
  scale: jest.fn(),
  clearRect: jest.fn(),
  beginPath: jest.fn(),
  moveTo: jest.fn(),
  lineTo: jest.fn(),
  closePath: jest.fn(),
  stroke: jest.fn(),
  fill: jest.fn(),
})) as unknown as typeof HTMLCanvasElement.prototype.getContext;

// jsdom does not implement Element.scrollTo (used to auto-scroll the chat history).
Element.prototype.scrollTo = jest.fn();

// EventSource is not present in jsdom; provide a minimal stub.
class MockEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readyState = MockEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  close = jest.fn();
}
// @ts-expect-error -- attach stub to global for tests
global.EventSource = MockEventSource;
