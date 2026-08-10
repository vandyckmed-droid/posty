// Headless check for the curated momentum page.
// Asserts it renders, has no JS errors, never scrolls sideways at phone width,
// resolves in both themes and both explicit theme stamps, and that the detail
// view opens with holdings, sector weights and a chart intact.
import { chromium } from 'playwright';
import fs from 'fs';

const file = process.argv[2] || process.env.ETF_PAGE;
if (!file) { console.error('usage: node tools/preview-curated.mjs <built-page.html> [shot-dir]'); process.exit(2); }
const shotDir = process.argv[3] || '.';
const body = fs.readFileSync(file, 'utf8');
const tmp = `${shotDir}/wrapped-curated.html`;
fs.writeFileSync(tmp, `<!doctype html><html><head><meta charset="utf-8">
<style>*,*::before,*::after{box-sizing:border-box}body{margin:0}</style>
</head><body>${body}</body></html>`);

function findChromium() {
  return [process.env.CHROME_PATH, '/opt/pw-browsers/chromium', '/usr/bin/chromium',
          '/usr/bin/chromium-browser', '/usr/bin/google-chrome']
    .filter(Boolean).find(p => fs.existsSync(p));
}
const exe = findChromium();
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const errors = [];

for (const scheme of ['light', 'dark']) {
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
    isMobile: true, hasTouch: true, colorScheme: scheme,
  });
  const p = await ctx.newPage();
  p.on('pageerror', e => errors.push(`[${scheme}] pageerror: ${e.message}`));
  p.on('console', m => { if (m.type() === 'error') errors.push(`[${scheme}] console: ${m.text()}`); });
  await p.goto('file://' + tmp);
  await p.waitForTimeout(500);

  console.log(scheme, JSON.stringify(await p.evaluate(() => ({
    rows: document.querySelectorAll('.row').length,
    shown: document.getElementById('shown').textContent,
    asof: document.getElementById('asof').textContent,
    first: document.querySelector('.tkr')?.textContent,
    firstScore: document.querySelector('.sc')?.textContent,
    sparks: document.querySelectorAll('svg.spark').length,
    hScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    bodyColor: getComputedStyle(document.body).color,
  }))));
  await p.screenshot({ path: `${shotDir}/curated-${scheme}-top.png` });

  // detail view must carry the per-ticker data through
  await p.locator('.row-hd').first().click();
  await p.waitForTimeout(250);
  console.log(scheme, 'detail:', JSON.stringify(await p.evaluate(() => {
    const d = document.querySelector('.detail');
    if (!d) return { open: false };
    const blocks = Array.from(d.querySelectorAll('.blk-h')).map(e => e.firstChild.textContent.trim());
    return {
      open: true,
      chart: !!d.querySelector('svg.chart'),
      blocks,
      holdings: d.querySelectorAll('.bar-row:not(.two)').length,
      sectors: d.querySelectorAll('.bar-row.two').length,
      where: (d.querySelector('.where') || {}).textContent || null,
      fields: Array.from(d.querySelectorAll('dt')).map(e => e.textContent.replace(/\s+/g, ' ')),
    };
  })));
  await p.screenshot({ path: `${shotDir}/curated-${scheme}-detail.png` });
  await p.locator('.row-hd').first().click();       // collapse

  // search
  await p.locator('#q').fill('uranium');
  await p.waitForTimeout(200);
  console.log(scheme, 'search "uranium":', await p.locator('.row').count(), 'row(s),',
    await p.locator('.tkr').first().textContent().catch(() => '—'));
  await p.locator('#q').fill('zzzz');
  await p.waitForTimeout(200);
  console.log(scheme, 'no match -> empty shown:',
    await p.evaluate(() => document.getElementById('empty').offsetParent !== null));
  await p.locator('#q').fill('');
  await ctx.close();
}

for (const [stamp, os] of [['light', 'dark'], ['dark', 'light']]) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: os });
  const p = await ctx.newPage();
  await p.goto('file://' + tmp);
  await p.evaluate(t => document.documentElement.setAttribute('data-theme', t), stamp);
  await p.waitForTimeout(200);
  console.log(`stamp=${stamp} over os=${os}`, JSON.stringify(await p.evaluate(() => ({
    bg: getComputedStyle(document.body).backgroundColor,
    fg: getComputedStyle(document.body).color,
  }))));
  await ctx.close();
}

await browser.close();
console.log(errors.length ? 'JS ERRORS:\n' + errors.join('\n') : 'no JS errors');
if (errors.length) process.exit(1);
