/* Focused FAQ/footer audit. See qa/README.md for temporary Playwright tooling. */
const { chromium, webkit } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const product = 'https://bibledavids.myshopify.com/products/alignment-what-you-are-looking-for-is-looking-for-you-combo-package';
const out = process.env.QA_OUTPUT || path.join(require('node:os').tmpdir(), 'alignment-faq-footer');
const url = process.env.QA_URL || pathToFileURL(path.resolve('index.html')).href;
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const engine = process.env.QA_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await engine.launch({
    ...(engine === chromium ? { executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' } : {}),
    headless: true,
  });
  try {
    const context = await browser.newContext({ reducedMotion: 'reduce' });
    // Check destinations without entering a storefront, cart or payment flow.
    await context.route(product, route => route.fulfill({ contentType: 'text/html', body: '<title>Verified destination</title>' }));
    await context.route('https://bibledavids.org/', route => route.fulfill({ contentType: 'text/html', body: '<title>Ministry destination</title>' }));
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    const results = [];
    for (const width of [375, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      const summaries = page.locator('.faq summary');
      assert.equal(await summaries.count(), 8);
      // Open every answer using native keyboard interaction; close every answer using a click.
      for (let i = 0; i < 8; i++) {
        const summary = summaries.nth(i);
        await summary.focus();
        await page.keyboard.press(i % 2 ? 'Space' : 'Enter');
        await page.waitForFunction(index => document.querySelectorAll('.faq summary')[index].getAttribute('aria-expanded') === 'true', i);
        assert.equal(await page.locator('.faq details[open]').count(), 1);
        const answer = page.locator('#' + await summary.getAttribute('aria-controls'));
        assert(await answer.isVisible());
        assert((await answer.innerText()).length > 40);
        assert.equal(await summary.locator('.faq-symbol').evaluate(el => getComputedStyle(el, '::before').content), '"−"');
        await summary.click();
        await page.waitForFunction(index => document.querySelectorAll('.faq summary')[index].getAttribute('aria-expanded') === 'false', i);
        assert.equal(await page.locator('.faq details[open]').count(), 0);
      }
      // Check the JavaScript fallback without native name grouping at one width.
      if (width === 1024) await page.locator('.faq details').evaluateAll(items => items.forEach(item => item.removeAttribute('name')));
      // Opening the next question closes the previous one.
      await summaries.nth(0).click();
      await summaries.nth(1).click();
      await page.waitForFunction(() => document.querySelectorAll('.faq details')[1].open && document.querySelectorAll('.faq summary')[0].getAttribute('aria-expanded') === 'false');
      assert.equal(await page.locator('.faq details[open]').count(), 1);
      for (const selector of ['#faq .faq-cta a', '.footer a[data-combo-purchase]', '.footer a[href="https://bibledavids.org"]']) {
        const link = page.locator(selector);
        assert.equal(await link.getAttribute('target'), '_blank');
        assert.equal(await link.getAttribute('rel'), 'noopener noreferrer');
        const popupPromise = context.waitForEvent('page');
        await link.click();
        const popup = await popupPromise;
        await popup.waitForLoadState();
        assert.equal(popup.url(), new URL(await link.getAttribute('href')).href);
        await popup.close();
      }
      for (const link of await page.locator('.footer a[href^="#"]').all()) {
        const hash = await link.getAttribute('href');
        assert.equal(await page.locator(hash).count(), 1);
        await link.click();
        assert.equal(new URL(page.url()).hash, hash);
        const top = await page.locator(hash).evaluate(el => el.getBoundingClientRect().top);
        const headerHeight = await page.locator('body > header').evaluate(el => el.getBoundingClientRect().height);
        assert(top >= headerHeight - 1, `${hash} hidden behind header at ${width}`);
      }
      for (const link of await page.locator('.faq-answer a').all()) {
        assert.equal(await link.getAttribute('href'), product);
        assert.equal(await link.getAttribute('target'), '_blank');
        assert.equal(await link.getAttribute('rel'), 'noopener noreferrer');
      }
      const metrics = await page.evaluate(() => ({
        width: innerWidth,
        overflow: document.documentElement.scrollWidth > innerWidth,
        footerColumns: getComputedStyle(document.querySelector('.footer-layout')).gridTemplateColumns.split(' ').length,
        faqColumns: getComputedStyle(document.querySelector('.faq-layout')).gridTemplateColumns.split(' ').length,
        year: document.querySelector('#copyright-year').textContent,
        answerAnimation: getComputedStyle(document.querySelector('.faq details[open] .faq-answer')).animationName,
      }));
      assert(!metrics.overflow);
      assert.equal(metrics.year, String(new Date().getFullYear()));
      assert.equal(metrics.answerAnimation, 'none');
      assert.equal(metrics.footerColumns, width <= 600 ? 1 : width <= 991 ? 2 : 3);
      assert.equal(metrics.faqColumns, width <= 991 ? 1 : 2);
      const accessibility = await new AxeBuilder({ page }).include('#faq').include('.footer').withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      assert.deepEqual(accessibility.violations, [], JSON.stringify(accessibility.violations));
      for (const [selector, name] of [['#faq', 'faq'], ['.footer', 'footer']]) {
        await page.locator(selector).screenshot({
          path: path.join(out, `${name}-${width}.png`),
          style: 'body > header, .skip-link { visibility: hidden !important; }',
        });
      }
      results.push(metrics);
      console.log(`PASS ${width}px: FAQ, keyboard, links, CTA, overflow, reduced motion, accessibility`);
    }
    // Native details remains usable without JavaScript; direct FAQ purchase URL remains available.
    const fallback = await browser.newContext({ javaScriptEnabled: false });
    const nojs = await fallback.newPage();
    await nojs.goto(url, { waitUntil: 'domcontentloaded' });
    await nojs.locator('.faq summary').first().click();
    assert(await nojs.locator('#faq-answer-1').isVisible());
    assert.equal(await nojs.locator('#faq .faq-cta a').getAttribute('href'), product);
    await fallback.close();
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    assert.equal(await page.locator('.faq details[open] .faq-answer').evaluate(el => getComputedStyle(el).animationName), 'faq-reveal');
    assert.deepEqual(errors, [], `Browser errors: ${errors.join('\n')}`);
    fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify({ results, errors, noJavaScript: 'PASS', accessibility: 'No scoped WCAG A/AA violations' }, null, 2));
    console.log(`PASS no-JS fallback and animation preference; no console or JavaScript errors. Artifacts: ${out}`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
