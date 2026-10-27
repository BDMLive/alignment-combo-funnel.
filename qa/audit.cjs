/* Local-only regression audit. Install optional tooling outside the site; see qa/README.md. */
const { chromium } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const baseUrl = process.env.QA_URL || 'http://127.0.0.1:8000/';
const out = process.env.QA_OUTPUT || path.join(os.tmpdir(), 'alignment-audit-results');
const executablePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const widths = [320, 375, 390, 430, 768, 1024, 1280, 1440, 1920];
const product = 'https://bibledavids.myshopify.com/products/alignment-what-you-are-looking-for-is-looking-for-you-combo-package';
const media = 'https://res.cloudinary.com/scjeyulc/video/upload/v1792490313/DELIVERANCE_BY_FIRE.....mp4';
const expectedSections = ['home', 'problem', 'journey', 'book', 'revelation', 'author', 'offer', 'faq', 'closing'];
const results = { baseUrl, engine: 'installed Chrome / Playwright', widths: [], errors: [], failedRequests: [], media: {}, checks: {} };
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const context = await browser.newContext();
    // Each popup uses its real destination URL, but no cart/payment/store UI is exercised.
    await context.route(product, route => route.fulfill({ contentType: 'text/html', body: '<title>Destination check</title>' }));
    const page = await context.newPage();
    page.on('pageerror', e => results.errors.push(e.message));
    page.on('console', message => { if (message.type() === 'error') results.errors.push(message.text()); });
    page.on('response', response => { if (response.status() >= 400) results.failedRequests.push({ url: response.url(), status: response.status() }); });
    page.on('requestfailed', request => results.failedRequests.push({ url: request.url(), error: request.failure() }));
    for (const width of widths) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => document.querySelector('video').readyState >= 1 || document.querySelector('video').error, {}, { timeout: 60000 });
      const video = page.locator('#hero-video');
      const mediaState = await video.evaluate(v => ({ error: v.error?.message, ready: v.readyState, controls: v.controls, inline: v.playsInline, preload: v.preload, autoplay: v.autoplay, paused: v.paused, poster: v.getAttribute('poster'), src: v.currentSrc, height: v.clientHeight }));
      assert(!mediaState.error, JSON.stringify(mediaState));
      assert(mediaState.controls && mediaState.inline && mediaState.paused && !mediaState.autoplay);
      assert.equal(mediaState.preload, 'metadata'); assert.equal(mediaState.src, media);
      assert.equal(mediaState.poster, 'assets/alignment-cover.jpg');
      assert.equal(mediaState.height, width <= 600 ? 330 : 440);
      if ([320, 1440].includes(width)) {
        await video.scrollIntoViewIfNeeded(); await video.click();
        await video.evaluate(async v => { if (v.paused) await v.play(); });
        await page.waitForFunction(() => document.querySelector('video').currentTime > .4, {}, { timeout: 60000 });
        results.media[width] = await video.evaluate(v => ({ time: v.currentTime, duration: v.duration, width: v.videoWidth, height: v.videoHeight }));
        await video.evaluate(v => { v.pause(); v.currentTime = 0; });
      }
      for (const img of await page.locator('img:not([hidden])').all()) { await img.scrollIntoViewIfNeeded(); await img.evaluate(i => i.decode()); }
      const scan = await page.evaluate(() => {
        const header = document.querySelector('.nav').getBoundingClientRect();
        const left = document.querySelector('.book-intro__copy').getBoundingClientRect(), right = document.querySelector('.book-intro__art').getBoundingClientRect();
        return {
          width: innerWidth, pageWidth: document.documentElement.scrollWidth,
          sections: [...document.querySelectorAll('main > section')].map(s => s.id),
          duplicateIds: [...document.querySelectorAll('[id]')].map(e => e.id).filter((id, i, ids) => ids.indexOf(id) !== i),
          missingAnchors: [...document.querySelectorAll('a[href^="#"]')].filter(a => !a.hash || !document.getElementById(a.hash.slice(1))).map(a => a.outerHTML),
          overflowing: [...document.querySelectorAll('body *')].filter(e => {
            const r = e.getBoundingClientRect(); return r.width > 0 && !['VIDEO', 'OPTION'].includes(e.tagName) && (r.right > innerWidth + 1 || e.scrollWidth > e.clientWidth + 2);
          }).map(e => e.tagName + '.' + e.className),
          brokenImages: [...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => i.src),
          dimensionlessImages: [...document.images].filter(i => !i.hasAttribute('width') || !i.hasAttribute('height')).map(i => i.src),
          eagerBelowFold: [...document.querySelectorAll('main > section:not(#home) img')].filter(i => i.loading !== 'lazy').map(i => i.src),
          bookLayout: { display: getComputedStyle(document.querySelector('.book-intro__layout')).display, direction: getComputedStyle(document.querySelector('.book-intro__layout')).flexDirection, ratio: left.width / right.width, sideBySide: right.x > left.x + left.width, imageOnly: document.querySelector('.book-intro__art').children.length === 1 },
          chapterColumns: getComputedStyle(document.querySelector('.chapter-grid')).gridTemplateColumns.split(' ').length,
          stageColumns: getComputedStyle(document.querySelector('.alignment-experience__grid')).gridTemplateColumns.split(' ').length,
          headerHeight: header.height,
          h1Count: document.querySelectorAll('h1').length,
          lang: document.documentElement.lang,
          languageControl: !!document.getElementById('language'),
          textAlignment: { guide: getComputedStyle(document.querySelector('.guide-copy p')).textAlign, book: getComputedStyle(document.querySelector('.book-intro__copy p')).textAlign, faqEyebrow: getComputedStyle(document.querySelector('.faq-eyebrow')).textAlign },
          ctas: [...document.querySelectorAll('a.btn,a.navlink,a.alignment-experience__button')].map(a => ({ text: a.textContent.trim().replace(/\s+/g, ' '), href: a.href, target: a.target, rel: a.rel, section: a.closest('section')?.id || 'header' })),
        };
      });
      assert.equal(scan.pageWidth, width); assert.deepEqual(scan.overflowing, []);
      assert.deepEqual(scan.sections, expectedSections); assert.deepEqual(scan.duplicateIds, []);
      assert.deepEqual(scan.missingAnchors, []); assert.deepEqual(scan.brokenImages, []);
      assert.deepEqual(scan.dimensionlessImages, []); assert.deepEqual(scan.eagerBelowFold, []);
      assert.equal(scan.bookLayout.display, 'flex'); assert.equal(scan.bookLayout.direction, width <= 991 ? 'column' : 'row'); assert(scan.bookLayout.imageOnly);
      if (width >= 1024) { assert(scan.bookLayout.sideBySide); assert(Math.abs(scan.bookLayout.ratio - 55 / 45) < .01); }
      assert.equal(scan.chapterColumns, width > 1100 ? 3 : width > 600 ? 2 : 1);
      assert.equal(scan.stageColumns, width > 1024 ? 4 : width > 600 ? 2 : 1);
      assert.equal(scan.h1Count, 1); assert.equal(scan.lang, 'en'); assert.equal(scan.languageControl, false);
      assert.equal(scan.textAlignment.faqEyebrow, 'center'); assert.notEqual(scan.textAlignment.guide, 'center'); assert.notEqual(scan.textAlignment.book, 'center');
      const purchaseLinks = page.locator('[data-combo-purchase]'); assert.equal(await purchaseLinks.count(), 6);
      for (let i = 0; i < await purchaseLinks.count(); i++) {
        const link = purchaseLinks.nth(i);
        assert.equal(await link.getAttribute('href'), product); assert.equal(await link.getAttribute('target'), '_blank'); assert.equal(await link.getAttribute('rel'), 'noopener noreferrer');
        if (await link.isVisible()) { const popupPromise = context.waitForEvent('page'); await link.click(); const popup = await popupPromise; await popup.waitForURL(product); await popup.close(); }
      }
      // Exercise every visible in-page link; reopen the native mobile menu as needed.
      for (const anchor of await page.locator('a[href^="#"]').all()) {
        const isMobileLink = await anchor.evaluate(a => !!a.closest('.mobile-navigation'));
        if (isMobileLink && await page.locator('.mobile-navigation').isVisible()) await page.locator('.mobile-navigation').evaluate(e => { e.open = true; });
        if (!await anchor.isVisible()) continue;
        if (await anchor.evaluate(a => a.classList.contains('skip-link'))) await anchor.focus();
        const hash = await anchor.getAttribute('href'); await anchor.click();
        await page.waitForFunction(hash => location.hash === hash, hash);
        await page.waitForFunction(hash => { const target = document.querySelector(hash); const offset = parseFloat(getComputedStyle(target).scrollMarginTop); const expected = Math.max(0, Math.min(target.getBoundingClientRect().top + scrollY - offset, document.documentElement.scrollHeight - innerHeight)); return Math.abs(scrollY - expected) < 2 && target.getBoundingClientRect().top >= document.querySelector('.nav').getBoundingClientRect().bottom - 1; }, hash);
      }
      const menu = page.locator('.mobile-navigation'), summary = menu.locator('summary');
      if (await menu.isVisible()) {
        await summary.focus(); await page.keyboard.press('Enter'); assert(await menu.evaluate(e => e.open));
        await page.keyboard.press('Escape'); assert(!await menu.evaluate(e => e.open)); assert(await summary.evaluate(e => e === document.activeElement));
        await summary.click(); await page.mouse.click(10, 900); assert(!await menu.evaluate(e => e.open));
        await summary.click(); await menu.locator('a[href="#faq"]').click(); assert(!await menu.evaluate(e => e.open));
        await page.waitForFunction(() => document.querySelector('.mobile-navigation summary') === document.activeElement);
      }
      for (const details of await page.locator('.faq details').all()) {
        const summary = details.locator('summary'); await summary.click(); assert(await details.evaluate(e => e.open)); await summary.click(); assert(!await details.evaluate(e => e.open));
        await summary.focus(); await page.keyboard.press('Enter'); assert(await details.evaluate(e => e.open)); await page.keyboard.press('Enter');
      }
      await page.locator('.skip-link').focus(); assert(await page.locator('.skip-link').evaluate(e => getComputedStyle(e).outlineStyle !== 'none' && e.getBoundingClientRect().top >= 0));
      await page.keyboard.press('Enter'); assert(await page.locator('main').evaluate(e => e === document.activeElement));
      await page.emulateMedia({ reducedMotion: 'reduce' });
      assert.equal(await page.locator('html').evaluate(e => getComputedStyle(e).scrollBehavior), 'auto');
      assert.equal(await page.locator('.alignment-experience__button').evaluate(e => getComputedStyle(e).transitionDuration), '0s');
      await page.emulateMedia({ reducedMotion: 'no-preference' });
      const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice']).analyze();
      scan.accessibilityViolations = axe.violations.map(v => ({ id: v.id, help: v.help, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) }));
      scan.accessibilityManualReview = axe.incomplete.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) }));
      assert.deepEqual(scan.accessibilityViolations, []);
      await page.evaluate(() => { document.activeElement.blur(); window.scrollTo({ top: 0, behavior: 'instant' }); });
      await page.screenshot({ path: path.join(out, `page-${width}.png`), fullPage: true, style: '.skip-link{visibility:hidden!important}' });
      if ([390, 768, 1440].includes(width)) {
        for (const id of expectedSections) await page.locator('#' + id).screenshot({ path: path.join(out, `${id}-${width}.png`), style: '.nav,.skip-link{visibility:hidden!important}' });
      }
      results.widths.push(scan); fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2));
      console.log('PASS', width, 'layout, links/popups, keyboard/menu/FAQ, images, reduced motion, axe');
    }
    assert.deepEqual(results.errors, []); assert.deepEqual(results.failedRequests, []);
    results.checks.runtime = 'PASS';
    const failure = await context.newPage(); await failure.route(media, route => route.abort()); await failure.goto(baseUrl);
    await failure.locator('#hero-video-error').waitFor({ state: 'visible' }); assert(await failure.locator('#hero-video').isHidden()); assert(await failure.locator('#hero-video-poster').isVisible());
    await failure.locator('#hero-video-poster').evaluate(i => i.decode()); results.checks.videoFailure = 'PASS'; await failure.close();
    const noJsContext = await browser.newContext({ javaScriptEnabled: false }); const noJs = await noJsContext.newPage(); await noJs.goto(baseUrl);
    assert.equal(await noJs.locator('#combo-product').getAttribute('href'), product); assert.equal(await noJs.locator('#combo-product').getAttribute('target'), '_blank');
    for (const a of await noJs.locator('[data-combo-purchase]:not(#combo-product)').all()) { assert.equal(await a.getAttribute('href'), '#offer'); assert.equal(await a.getAttribute('target'), null); }
    assert(await noJs.locator('#hero-video').isHidden()); assert(await noJs.locator('#hero-video-poster').isVisible());
    results.checks.noJavaScript = 'PASS';
    // Keyboard focus and header clearance when zoom/reflow narrows the layout.
    results.checks.realStorePayment = 'NOT TESTED: no cart or financial transaction submitted';
    results.checks.crossBrowser = 'NOT TESTED: installed Chrome only; viewport simulation is not physical-device testing';
    fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2));
    console.log('PASS: real media playback, empty console/error logs, video failure poster, no-JS Shopify fallback');
    console.log('Results and screenshots:', out);
  } finally { await browser.close(); }
})().catch(error => { results.error = error.stack; fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2)); console.error(error); process.exit(1); });
