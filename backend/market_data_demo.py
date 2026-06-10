1	"""FinAlly Market Data Simulator Demo.
2	
3	Run with:  uv run market_data_demo.py
4	
5	Displays a live-updating terminal dashboard of simulated stock prices
6	using the GBM simulator and Rich library.
7	"""
8	
9	from __future__ import annotations
10	
11	import asyncio
12	import time
13	from collections import deque
14	
15	from rich.console import Console
16	from rich.layout import Layout
17	from rich.live import Live
18	from rich.panel import Panel
19	from rich.table import Table
20	from rich.text import Text
21	
22	from app.market.cache import PriceCache
23	from app.market.seed_prices import SEED_PRICES
24	from app.market.simulator import SimulatorDataSource
25	
26	# Sparkline characters, low to high
27	SPARK_CHARS = "▁▂▃▄▅▆▇█"
28	
29	# Ordered ticker list matching the default watchlist
30	TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
31	
32	DURATION = 60  # seconds
33	
34	
35	def sparkline(values: list[float]) -> str:
36	    """Render a sequence of values as a unicode sparkline."""
37	    if len(values) < 2:
38	        return ""
39	    lo, hi = min(values), max(values)
40	    spread = hi - lo
41	    if spread == 0:
42	        return SPARK_CHARS[3] * len(values)
43	    n = len(SPARK_CHARS) - 1
44	    return "".join(SPARK_CHARS[int((v - lo) / spread * n)] for v in values)
45	
46	
47	def format_price(price: float) -> str:
48	    """Format a price with comma separator."""
49	    if price >= 1000:
50	        return f"{price:,.2f}"
51	    return f"{price:.2f}"
52	
53	
54	def build_table(
55	    cache: PriceCache,
56	    history: dict[str, deque],
57	    elapsed: float,
58	) -> Table:
59	    """Build the price table."""
60	    table = Table(
61	        title=None,
62	        expand=True,
63	        border_style="bright_black",
64	        header_style="bold bright_white",
65	        pad_edge=True,
66	        padding=(0, 1),
67	    )
68	    table.add_column("Ticker", style="bold bright_white", width=8)
69	    table.add_column("Price", justify="right", width=10)
70	    table.add_column("Change", justify="right", width=9)
71	    table.add_column("Chg %", justify="right", width=8)
72	    table.add_column("", width=3)  # arrow
73	    table.add_column("Sparkline", width=42, no_wrap=True)
74	
75	    for ticker in TICKERS:
76	        update = cache.get(ticker)
77	        if update is None:
78	            table.add_row(ticker, "---", "---", "---", "", "")
79	            continue
80	
81	        # Direction styling
82	        if update.direction == "up":
83	            color = "green"
84	            arrow = "[bold green]\u25b2[/]"
85	        elif update.direction == "down":
86	            color = "red"
87	            arrow = "[bold red]\u25bc[/]"
88	        else:
89	            color = "bright_black"
90	            arrow = "[bright_black]\u2500[/]"
91	
92	        price_str = f"[{color}]${format_price(update.price)}[/]"
93	        change_str = f"[{color}]{update.change:+.2f}[/]"
94	        pct_str = f"[{color}]{update.change_percent:+.2f}%[/]"
95	
96	        # Sparkline from history
97	        vals = list(history.get(ticker, []))
98	        spark_str = f"[bright_cyan]{sparkline(vals)}[/]" if len(vals) > 1 else ""
99	
100	        table.add_row(ticker, price_str, change_str, pct_str, arrow, spark_str)
101	
102	    return table
103	
104	
105	def build_event_log(events: deque) -> Panel:
106	    """Build the event log panel."""
107	    text = Text()
108	    for evt in events:
109	        text.append(evt)
110	        text.append("\n")
111	    if not events:
112	        text.append("Watching for notable moves (>1% change)...", style="bright_black italic")
113	    return Panel(
114	        text,
115	        title="[bold bright_yellow]Recent Events[/]",
116	        border_style="bright_black",
117	        height=8,
118	    )
119	
120	
121	def build_dashboard(
122	    cache: PriceCache,
123	    history: dict[str, deque],
124	    events: deque,
125	    start_time: float,
126	) -> Layout:
127	    """Build the full dashboard layout."""
128	    elapsed = time.time() - start_time
129	    remaining = max(0, DURATION - elapsed)
130	
131	    layout = Layout()
132	    layout.split_column(
133	        Layout(name="header", size=3),
134	        Layout(name="body"),
135	        Layout(name="footer", size=10),
136	    )
137	
138	    # Header
139	    header_text = Text.assemble(
140	        ("  FinAlly ", "bold bright_yellow"),
141	        ("Market Data Simulator", "bold bright_white"),
142	        ("  |  ", "bright_black"),
143	        (f"{elapsed:5.1f}s elapsed", "bright_cyan"),
144	        ("  |  ", "bright_black"),
145	        (f"{remaining:4.1f}s remaining", "bright_cyan"),
146	        ("  |  ", "bright_black"),
147	        (f"{len(cache)} tickers", "bright_white"),
148	        ("  |  ", "bright_black"),
149	        ("Ctrl+C to exit", "bright_black italic"),
150	    )
151	    layout["header"].update(Panel(header_text, border_style="bright_yellow"))
152	
153	    # Body: price table
154	    layout["body"].update(
155	        Panel(
156	            build_table(cache, history, elapsed),
157	            title="[bold bright_white]Live Prices[/]",
158	            border_style="bright_black",
159	        )
160	    )
161	
162	    # Footer: event log
163	    layout["footer"].update(build_event_log(events))
164	
165	    return layout
166	
167	
168	def print_summary(cache: PriceCache) -> None:
169	    """Print final summary comparing to seed prices."""
170	    console = Console()
171	    console.print()
172	    console.print("[bold bright_yellow]  FinAlly[/] [bold]Session Summary[/]")
173	    console.print()
174	
175	    table = Table(border_style="bright_black", header_style="bold bright_white", expand=False)
176	    table.add_column("Ticker", style="bold bright_white", width=8)
177	    table.add_column("Seed Price", justify="right", width=12)
178	    table.add_column("Final Price", justify="right", width=12)
179	    table.add_column("Session Change", justify="right", width=14)
180	
181	    for ticker in TICKERS:
182	        seed = SEED_PRICES.get(ticker, 0)
183	        update = cache.get(ticker)
184	        if update is None:
185	            continue
186	        final = update.price
187	        session_change = ((final - seed) / seed) * 100 if seed else 0
188	
189	        if session_change > 0:
190	            color = "green"
191	        elif session_change < 0:
192	            color = "red"
193	        else:
194	            color = "bright_black"
195	
196	        table.add_row(
197	            ticker,
198	            f"${format_price(seed)}",
199	            f"[{color}]${format_price(final)}[/]",
200	            f"[{color}]{session_change:+.2f}%[/]",
201	        )
202	
203	    console.print(table)
204	    console.print()
205	
206	
207	async def run() -> None:
208	    """Main demo loop."""
209	    cache = PriceCache()
210	    source = SimulatorDataSource(price_cache=cache, update_interval=0.5)
211	
212	    # Per-ticker price history for sparklines
213	    history: dict[str, deque] = {t: deque(maxlen=40) for t in TICKERS}
214	
215	    # Recent event log
216	    events: deque = deque(maxlen=12)
217	
218	    await source.start(TICKERS)
219	    start_time = time.time()
220	
221	    # Seed initial history points
222	    for ticker in TICKERS:
223	        update = cache.get(ticker)
224	        if update:
225	            history[ticker].append(update.price)
226	
227	    try:
228	        with Live(
229	            build_dashboard(cache, history, events, start_time),
230	            refresh_per_second=4,
231	            screen=True,
232	        ) as live:
233	            last_version = cache.version
234	            while time.time() - start_time < DURATION:
235	                await asyncio.sleep(0.25)
236	
237	                # Check for updates
238	                if cache.version == last_version:
239	                    continue
240	                last_version = cache.version
241	
242	                # Record history & detect events
243	                for ticker in TICKERS:
244	                    update = cache.get(ticker)
245	                    if update is None:
246	                        continue
247	                    history[ticker].append(update.price)
248	
249	                    # Log notable moves
250	                    if abs(update.change_percent) > 1.0:
251	                        direction = "\u25b2" if update.direction == "up" else "\u25bc"
252	                        color = "green" if update.direction == "up" else "red"
253	                        timestamp = time.strftime("%H:%M:%S")
254	                        events.appendleft(
255	                            f"[bright_black]{timestamp}[/]  "
256	                            f"[bold {color}]{direction} {ticker}[/]  "
257	                            f"[{color}]{update.change_percent:+.2f}%[/]  "
258	                            f"${format_price(update.price)}"
259	                        )
260	
261	                live.update(build_dashboard(cache, history, events, start_time))
262	
263	    except KeyboardInterrupt:
264	        pass
265	    finally:
266	        await source.stop()
267	
268	    print_summary(cache)
269	
270	
271	if __name__ == "__main__":
272	    asyncio.run(run())
273	