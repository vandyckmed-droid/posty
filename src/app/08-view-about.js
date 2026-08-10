/* Method: what the numbers mean and when they were taken. */
const About = (() => {
  function render(host) {
    const d = new Date(DATA.generatedAt);
    host.innerHTML = `
      <div class="section-h"><h2>Data</h2></div>
      <div class="card" style="padding:4px 14px 8px">
        <div class="prose">
          <div class="kv"><span>Market close</span><b>${Fmt.day(DATA.dataAsOf)}</b></div>
          <div class="kv"><span>Retrieved</span><b>${d.toLocaleString(undefined, { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" })}</b></div>
          <div class="kv"><span>Screened</span><b>${DATA.candidatesScreened.toLocaleString()}</b></div>
          <div class="kv"><span>Ranking universe</span><b>${DATA.universeSize.toLocaleString()}</b></div>
          <div class="kv" style="border-bottom:0"><span>Displayed</span><b>${DATA.displaySize} per basis</b></div>
        </div>
      </div>

      <div class="section-h"><h2>Method</h2></div>
      <div class="card" style="padding:2px 14px 16px">
        <div class="prose">
          <h3>Universe</h3>
          U.S.-listed common stocks on NYSE, NASDAQ and NYSE American. ETFs, funds, ADRs,
          preferred shares, warrants, rights and units are excluded. The
          ${DATA.universeSize.toLocaleString()} with the highest 63-day average daily dollar
          volume &mdash; <code>mean(close × volume)</code> &mdash; form the ranking universe.
          Dollar volume is traded notional, so it is the one figure here taken from
          unadjusted prices.

          <h3>Momentum</h3>
          Every return is a total return, from dividend-adjusted closes.
          <code>12-1</code> runs from 252 trading days ago to 21 trading days ago;
          <code>6-1</code> from 126 trading days ago to the same endpoint. Skipping the most
          recent month avoids short-term reversal. Each leg is percentile-ranked within the
          universe and blended <code>0.5 × P12-1 + 0.5 × P6-1</code>.

          <h3>Risk-adjusted basis</h3>
          The <b>Risk-adj</b> toggle divides each leg by the standard deviation over that
          leg's own window &mdash; both ending a month back, where the return ends:
          <code>ln(1+R) / (&sigma;&radic;N)</code> over N = 252 and 126 daily log returns.
          A cumulative log return over N days has standard deviation <code>&sigma;&radic;N</code>,
          which makes the ratio a t-statistic of drift. Inverse-volatility weighting is unaffected.

          <h3>Volatility &amp; weights</h3>
          Realized volatility is the sample standard deviation of the last 126 daily returns,
          annualized by <code>&radic;252</code>. Watchlist weights are inverse-volatility,
          <code>w = (1/&sigma;) / &Sigma;(1/&sigma;)</code>, recomputed on every change and
          normalized to 100%. Weights are held at full precision and rounded for display only.

          <h3>Privacy</h3>
          Prices come from Financial Modeling Prep, retrieved server-side and baked into this
          page. No credentials or raw API responses reach the browser. Your watchlist is stored
          on this device only.
        </div>
      </div>
      <p class="note" style="padding:0 2px 8px">
        For research and educational use. These are mechanical outputs of the formulas above &mdash;
        not investment advice, and not a recommendation to buy or sell any security.
        Past performance says nothing about future returns.
      </p>`;
  }
  return { render };
})();
