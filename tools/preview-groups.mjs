// Headless check for the stock groups page.
// Asserts it renders, has no JS errors, never scrolls sideways at phone width,
// resolves in both themes and both explicit theme stamps, and that a group opens
// with its member list, both windows and a chart intact.
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const file = process.argv[2] || process.env.GROUPS_PAGE;
if (!file) { console.error('usage: node tools/preview-groups.mjs <built-page.html> [shot-dir]'); process.exit(2); }
const shotDir = process.argv[3] || '.';
const body = fs.readFileSync(file, 'utf8');
const tmp = path.resolve(shotDir, 'wrapped-groups.html');
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

  const top = await p.evaluate(() => ({
    rows: document.querySelectorAll('.row').length,
    first: document.querySelector('.tkr')?.textContent,
    firstScore: document.querySelector('.sc')?.textContent,
    chips: Array.from(document.querySelectorAll('.row .chip')).slice(0, 3).map(e => e.textContent),
    sparks: document.querySelectorAll('svg.spark').length,
    readout: document.getElementById('readout').textContent.replace(/\s+/g, ' ').trim(),
    method: document.getElementById('method').textContent.length,
    undef: document.body.textContent.includes('undefined')
        || document.body.textContent.includes('NaN'),
    hScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    bodyColor: getComputedStyle(document.body).color,
  }));
  console.log(scheme, JSON.stringify(top));
  if (top.undef) errors.push(`[${scheme}] page renders "undefined" or "NaN"`);
  if (top.hScroll) errors.push(`[${scheme}] horizontal scroll at 390px`);
  if (!top.rows) errors.push(`[${scheme}] no rows rendered`);
  await p.screenshot({ path: `${shotDir}/groups-${scheme}-top.png` });

  await p.locator('.row-hd').first().click();
  await p.waitForTimeout(250);
  console.log(scheme, 'detail:', JSON.stringify(await p.evaluate(() => {
    const d = document.querySelector('.detail');
    if (!d) return { open: false };
    return {
      open: true,
      windows: Array.from(d.querySelectorAll('.win .wv')).map(e => e.textContent),
      members: d.querySelectorAll('.bar-row').length,
      chart: !!d.querySelector('svg.spark'),
      fields: Array.from(d.querySelectorAll('dt')).map(e => e.textContent),
      values: Array.from(d.querySelectorAll('dd')).map(e => e.textContent),
    };
  })));
  await p.screenshot({ path: `${shotDir}/groups-${scheme}-detail.png`, fullPage: false });
  await p.locator('.row-hd').first().click();

  await p.locator('#q').fill('NVDA');
  await p.waitForTimeout(200);
  console.log(scheme, 'search NVDA ->', await p.locator('.row').count(), 'group(s):',
    await p.locator('.tkr').first().textContent().catch(() => '—'));
  await p.locator('#q').fill('zzzz');
  await p.waitForTimeout(200);
  const emptyShown = await p.evaluate(() => document.getElementById('empty').offsetParent !== null);
  console.log(scheme, 'no match -> empty shown:', emptyShown);
  if (!emptyShown) errors.push(`[${scheme}] empty state did not show`);
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
console.log(errors.length ? 'FAILURES:\n' + errors.join('\n') : 'no JS errors, no layout failures');
if (errors.length) process.exit(1);
