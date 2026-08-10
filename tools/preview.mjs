import { chromium } from 'playwright';
import fs from 'fs';

const file = process.argv[2] || process.env.ETF_PAGE;
if (!file) { console.error('usage: node tools/preview.mjs <built-page.html> [shot-dir]'); process.exit(2); }
const shotDir = process.argv[3] || process.env.ETF_SHOTS || '.';
const body = fs.readFileSync(file, 'utf8');
// mimic the Artifact publish wrapper
const page_html = `<!doctype html><html><head><meta charset="utf-8">
<style>*,*::before,*::after{box-sizing:border-box}body{margin:0}</style>
</head><body>${body}</body></html>`;
const tmp = `${shotDir}/wrapped.html`;
fs.writeFileSync(tmp, page_html);

// Prefer an explicit CHROME_PATH, then any chromium already on the machine, and only
// then whatever playwright bundled -- environments often ship a browser whose build
// number does not match the installed playwright.
function findChromium() {
  const candidates = [
    process.env.CHROME_PATH,
    '/opt/pw-browsers/chromium',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
  ].filter(Boolean);
  return candidates.find(p => fs.existsSync(p));
}

const exe = findChromium();
if (exe) console.log(`chromium: ${exe}`);
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const errors = [];

for (const scheme of ['light', 'dark']) {
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    colorScheme: scheme,
  });
  const p = await ctx.newPage();
  p.on('pageerror', e => errors.push(`[${scheme}] pageerror: ${e.message}`));
  p.on('console', m => { if (m.type() === 'error') errors.push(`[${scheme}] console: ${m.text()}`); });
  await p.goto('file://' + tmp);
  await p.waitForTimeout(600);

  const stats = await p.evaluate(() => ({
    rows: document.querySelectorAll('.row').length,
    shown: document.getElementById('ro-shown').textContent,
    bets: document.getElementById('ro-bets').textContent,
    asof: document.getElementById('asof').textContent,
    firstTkr: document.querySelector('.tkr')?.textContent,
    firstScore: document.querySelector('.sc')?.textContent,
    hScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    bodyColor: getComputedStyle(document.body).color,
  }));
  console.log(scheme, JSON.stringify(stats));

  await p.screenshot({ path: `${shotDir}/shot-${scheme}-top.png` });

  // expand a row + open method
  await p.locator('.row-hd').first().click();
  await p.waitForTimeout(150);
  const detailOpen = await p.locator('.detail').first().isVisible();
  await p.screenshot({ path: `${shotDir}/shot-${scheme}-expanded.png` });
  console.log(scheme, 'detail opens:', detailOpen);

  // interaction sweep
  await p.locator('#f-stk').click();           // include non-stock funds
  await p.waitForTimeout(150);
  const allAssets = await p.locator('.tkr').first().textContent();
  const allCount = await p.evaluate(() => document.getElementById('ro-shown').textContent);
  await p.locator('#f-stk').click();           // back to stocks only
  await p.waitForTimeout(120);
  const withCash = allAssets + '/' + allCount;
  await p.locator('[data-liq="500000000"]').click();
  await p.waitForTimeout(120);
  const liqTop = await p.locator('.tkr').first().textContent();
  await p.locator('[data-liq="5000000"]').click();
  await p.locator('[data-sort="sc"]').click();          // raw ratio, no T-bill netted
  await p.waitForTimeout(120);
  const rawTop = await p.locator('.tkr').first().textContent();
  await p.locator('[data-sort="xs"]').click();          // back to the headline score
  await p.locator('#q').fill('semiconductor');
  await p.waitForTimeout(150);
  const searchN = await p.locator('.row').count();
  await p.locator('#q').fill('');
  await p.waitForTimeout(120);

  console.log(scheme, `allAssets=${withCash} liq500M=${liqTop} byRaw=${rawTop} search"semiconductor"=${searchN} rows`);

  if (scheme === 'light') {
    // grouping + effective-bets checks against independently computed values
    const readout = async () => p.evaluate(() => ({
      shown: document.getElementById('ro-shown').textContent,
      folded: document.getElementById('ro-grp').textContent,
      bets: document.getElementById('ro-bets').textContent,
      line: document.getElementById('grpline').textContent,
      rows: document.querySelectorAll('.row').length,
    }));
    for (const t of ['bet', 'fund', 'off']) {
      await p.locator(`[data-grp="${t}"]`).click();
      await p.waitForTimeout(200);
      console.log(`  grp=${t}`, JSON.stringify(await readout()));
    }
    // the semis cluster: does one row absorb the rest?
    await p.locator('[data-grp="bet"]').click();
    await p.locator('[data-liq="100000000"]').click();
    await p.locator('#q').fill('semiconductor');
    await p.waitForTimeout(200);
    const semi = await p.evaluate(() => Array.from(document.querySelectorAll('.row')).map(r => ({
      tkr: r.querySelector('.tkr').textContent,
      grp: r.querySelector('.grp-toggle')?.textContent.trim().replace(/\s+/g, ' ') || null,
    })));
    console.log('  semis @0.95/$100M:', JSON.stringify(semi));
    await p.locator('.grp-toggle').first().click();
    await p.waitForTimeout(150);
    const mems = await p.evaluate(() => Array.from(document.querySelectorAll('.mem')).map(m =>
      m.querySelector('.mem-t').textContent + ' ' + m.querySelector('.mem-r').textContent));
    console.log('  expanded members:', JSON.stringify(mems));
    await p.screenshot({ path: `${shotDir}/shot-groups.png` });
    await p.locator('#q').fill('');
    await p.locator('[data-liq="5000000"]').click();
    await p.waitForTimeout(200);
    await p.screenshot({ path: `${shotDir}/shot-readout.png` });

    // --- formation window switch ---
    for (const w of ['12', '6']) {
      await p.locator(`[data-win="${w}"]`).click();
      await p.waitForTimeout(400);
      const st = await p.evaluate(() => ({
        h: document.getElementById('h-win').textContent,
        range: document.getElementById('winrange').textContent,
        shown: document.getElementById('ro-shown').textContent,
        folded: document.getElementById('ro-grp').textContent,
        bets: document.getElementById('ro-bets').textContent,
        top5: Array.from(document.querySelectorAll('.tkr')).slice(0, 5).map(e => e.textContent),
        firstScore: document.querySelector('.sc').textContent,
      }));
      console.log(`  win=${w}`, JSON.stringify(st));
    }
    // cross-window drift in the detail panel
    await p.locator('[data-win="12"]').click();
    await p.waitForTimeout(300);
    await p.locator('.row-hd').first().click();
    await p.waitForTimeout(150);
    const det = await p.evaluate(() => {
      const dl = document.querySelector('.detail dl');
      const dts = dl.querySelectorAll('dt'), dds = dl.querySelectorAll('dd');
      return Array.from(dts).map((d, i) =>
        d.textContent.replace(/\s+/g, ' ') + ' = ' + dds[i].textContent.replace(/\s+/g, ' '));
    });
    console.log('  detail:', JSON.stringify(det.slice(-2)));
    await p.screenshot({ path: `${shotDir}/shot-detail.png` });
    await p.locator('[data-win="6"]').click();
    await p.waitForTimeout(300);
    await p.screenshot({ path: `${shotDir}/shot-win6.png` });
    await p.locator('[data-win="12"]').click();
    await p.waitForTimeout(200);
  }

  if (scheme === 'dark') {
    await p.locator('.method summary').click();
    await p.waitForTimeout(200);
    await p.locator('.method').scrollIntoViewIfNeeded();
    await p.screenshot({ path: `${shotDir}/shot-method.png`, fullPage: false });
  }
  await ctx.close();
}

// explicit data-theme stamps (viewer toggle) over the opposite OS scheme
for (const [stamp, os] of [['light', 'dark'], ['dark', 'light']]) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: os });
  const p = await ctx.newPage();
  await p.goto('file://' + tmp);
  await p.evaluate(t => document.documentElement.setAttribute('data-theme', t), stamp);
  await p.waitForTimeout(200);
  const c = await p.evaluate(() => ({
    bg: getComputedStyle(document.body).backgroundColor,
    fg: getComputedStyle(document.body).color,
    rowBg: getComputedStyle(document.querySelector('.row')).backgroundColor,
  }));
  console.log(`stamp=${stamp} over os=${os}`, JSON.stringify(c));
  await ctx.close();
}

// desktop width
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const p = await ctx.newPage();
await p.goto('file://' + tmp);
await p.waitForTimeout(300);
await p.screenshot({ path: `${shotDir}/shot-desktop.png` });
await ctx.close();

await browser.close();
console.log(errors.length ? 'JS ERRORS:\n' + errors.join('\n') : 'no JS errors');
if (errors.length) process.exit(1);
