/** Manual Jest mock: lightweight-charts is ESM-only and draws on canvas (no jsdom). */

export const createChart = () => ({
  addSeries: () => ({ setData: jest.fn() }),
  timeScale: () => ({ fitContent: jest.fn() }),
  remove: jest.fn(),
});

export const AreaSeries = {};
export const LineSeries = {};
