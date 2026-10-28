/* Run with temporary Playwright and axe tooling; see I18N.md. */
const { chromium, webkit } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '..');
const languages = ['en', 'fr', 'es', 'pt', 'ar', 'de', 'it'];
const widths = [320, 375, 390, 768, 1024, 1440];
const dictionaries = Object.fromEntries(languages.map(lang => [lang, JSON.parse(fs.readFileSync(path.join(root, 'locales', `${lang}.json`)))]));
const product = 'https://bibledavids.myshopify.com/products/alignment-what-you-are-looking-for-is-looking-for-you-combo-package';
const out = process.env.QA_OUTPUT || path.join(require('node:os').tmpdir(), 'alignment-i18n');
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const engine = process.env.QA_BROWSER === 'webkit' ? webkit : chromium;
  const browser = await engine.launch({ headless: true, ...(engine === chromium ? { executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' } : {}) });
  const results = { engine: engine.name(), layouts: [], errors: [], media: {} };
  try {
    const context = await browser.newContext({ reducedMotion: 'reduce', locale: 'fr-FR' });
    await context.route(product, route => route.fulfill({ contentType: 'text/html', body: '<title>Destination verified</title>' }));
    const page = await context.newPage();
    page.on('pageerror', e => results.errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') results.errors.push(m.text()); });
    const url = process.env.QA_URL || pathToFileURL(path.join(root, 'index.html')).href;
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.AlignmentI18n);
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');
    // No written text is omitted except approved brands, counters and native language names.
    const unbound = await page.evaluate(() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const missing = [];
      while (walker.nextNode()) {
        const node = walker.currentNode, parent = node.parentElement;
        const text = node.textContent.trim().replace(/\s+/g, ' ');
        if (!text || parent.closest('script, style, noscript, option, #language-feedback, #copyright-year, [translate="no"]')) continue;
        if (/^(\d{2}( \/ ALIGNMENT)?|↗|BIBLE DAVIDS MINISTRIES|Bible Davids Ministries ↗|ALIGNMENT)$/.test(text)) continue;
        if (!parent.hasAttribute('data-i18n-text')) missing.push(text);
      }
      return missing;
    });
    assert.deepEqual(unbound, [], 'Unbound page text');
    const video = page.locator('#hero-video');
    await video.evaluate(v => { window.__originalVideo = v; });
    for (const language of languages) {
      await page.selectOption('#language-select', language);
      await page.waitForFunction(lang => document.documentElement.lang === lang, language);
      await page.evaluate(() => new Promise(requestAnimationFrame));
      const actual = await page.evaluate(() => ({
        lang: document.documentElement.lang, dir: document.documentElement.dir,
        bindings: [...document.querySelectorAll('[data-i18n-text]')].flatMap(el => {
          const keys = el.dataset.i18nText.split(' ');
          const nodes = [...el.childNodes].filter(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
          return nodes.map((n, i) => [keys[i], n.textContent.trim()]);
        }),
        attrs: ['alt', 'aria-label', 'aria-description', 'content', 'title', 'placeholder'].flatMap(attr => [...document.querySelectorAll(`[data-i18n-${attr}]`)].map(el => [el.getAttribute(`data-i18n-${attr}`), el.getAttribute(attr)])),
        sameVideo: window.__originalVideo === document.querySelector('#hero-video'),
        badAnchors: [...document.querySelectorAll('a[href^="#"]')].filter(a => !document.querySelector(a.getAttribute('href'))).map(a => a.getAttribute('href')),
      }));
      assert.equal(actual.dir, language === 'ar' ? 'rtl' : 'ltr');
      assert(actual.sameVideo);
      assert.deepEqual(actual.badAnchors, []);
      for (const [key, text] of [...actual.bindings, ...actual.attrs]) assert.equal(text, dictionaries[language][key], `${language}.${key}`);
      for (const width of widths) {
        await page.setViewportSize({ width, height: 1000 });
        // Verify every expanded answer at every language and width, not only the first one.
        for (let i = 0; i < 8; i++) {
          await page.locator('.faq summary').nth(i).focus();
          await page.keyboard.press(i % 2 ? 'Space' : 'Enter');
          await page.waitForFunction(index => document.querySelectorAll('.faq details')[index].open && document.querySelectorAll('.faq summary')[index].getAttribute('aria-expanded') === 'true', i);
          assert.equal(await page.locator('.faq details[open]').count(), 1);
          assert(await page.locator(`#faq-answer-${i + 1}`).isVisible());
        }
        await page.locator('.faq summary').last().click();
        // Scroll at the top of a section through actual navigation, accounting for the sticky header.
        const footerLink = page.locator('.footer nav a[href="#book"]');
        await footerLink.click();
        const sectionTop = await page.locator('#book').evaluate(el => el.getBoundingClientRect().top);
        const headerHeight = await page.locator('body > header').evaluate(el => el.getBoundingClientRect().height);
        assert(sectionTop >= headerHeight - 1, `Anchor obscured ${language}/${width}`);
        const layout = await page.evaluate(() => ({
          width: innerWidth, pageWidth: document.documentElement.scrollWidth,
          overflow: [...document.querySelectorAll('body *')].filter(el => {
            if (el.closest('script, style, #language-feedback, .skip-link') || ['OPTION', 'VIDEO'].includes(el.tagName)) return false;
            const r = el.getBoundingClientRect();
            return r.width > 0 && (r.left < -1 || r.right > innerWidth + 1 || el.scrollWidth > el.clientWidth + 3);
          }).map(el => `${el.tagName}.${el.className}`),
        }));
        results.layouts.push({ language, ...layout });
        assert(layout.pageWidth <= width, `Page overflow ${language}/${width}: ${JSON.stringify(layout)}`);
        assert.deepEqual(layout.overflow, [], `Clipping ${language}/${width}`);
        if ([320, 768, 1440].includes(width)) {
          for (const selector of ['body > header', '#revelation', '#faq', '.footer']) {
            await page.locator(selector).screenshot({ path: path.join(out, `${language}-${width}-${selector.replace(/[^a-z]/g, '')}.png`), style: '.skip-link { visibility: hidden !important; } body > header { position: relative !important; }' });
          }
        }
      }
      // A persisted selection is restored on reload; no browser-language detection overrides it.
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForFunction(lang => document.documentElement.lang === lang && !!window.AlignmentI18n, language);
      await video.evaluate(v => { window.__originalVideo = v; });
      console.log(`PASS ${language}: complete copy/attributes, six widths, FAQ, navigation, persistence`);
    }
    // Preserve scroll and open FAQ/menu state on a language change.
    await page.locator('.faq summary').first().click();
    await page.evaluate(() => window.scrollTo(0, 1500));
    await page.locator('.mobile-navigation').evaluate(el => { el.open = true; });
    const scrollBefore = await page.evaluate(() => scrollY);
    await page.selectOption('#language-select', 'fr');
    await page.evaluate(() => new Promise(requestAnimationFrame));
    assert(Math.abs(await page.evaluate(() => scrollY) - scrollBefore) <= 1, 'Scroll position changed');
    assert(await page.locator('.faq details').first().getAttribute('open') !== null);
    assert(await page.locator('.mobile-navigation').evaluate(el => el.open));
    await page.locator('.mobile-navigation').evaluate(el => { el.open = false; });
    // Real purchase destination and secure popup behavior in a translated page.
    for (const link of await page.locator('[data-combo-purchase]').all()) {
      assert.equal(await link.getAttribute('href'), product);
      assert.equal(await link.getAttribute('target'), '_blank');
      assert.equal(await link.getAttribute('rel'), 'noopener noreferrer');
    }
    const popupPromise = context.waitForEvent('page');
    await page.locator('#combo-product').click();
    const popup = await popupPromise; await popup.waitForLoadState(); assert.equal(popup.url(), product); await popup.close();
    // Exercise actual video playback, then switch language without replacing or resetting it.
    await page.locator('#hero-video').scrollIntoViewIfNeeded();
    await page.waitForFunction(() => document.querySelector('#hero-video').readyState >= 1 || document.querySelector('#hero-video').error, {}, { timeout: 60000 });
    results.media = await video.evaluate(async v => { if (v.error) return { error: v.error.message }; v.muted = true; await v.play(); return { src: v.currentSrc, time: v.currentTime }; });
    assert(!results.media.error, JSON.stringify(results.media));
    await page.waitForFunction(() => document.querySelector('#hero-video').currentTime > 0.3);
    const before = await video.evaluate(v => ({ time: v.currentTime, src: v.currentSrc }));
    await page.selectOption('#language-select', 'ar');
    const after = await video.evaluate(v => ({ time: v.currentTime, src: v.currentSrc, paused: v.paused, same: v === window.__originalVideo }));
    assert(after.same && !after.paused && after.src === before.src && after.time >= before.time);
    results.media.preserved = true;
    await video.evaluate(v => v.pause());
    for (const lang of ['ar', 'de', 'en']) {
      await page.selectOption('#language-select', lang);
      const scan = await new AxeBuilder({ page }).include('body > header').include('#faq').include('.footer').withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      assert.deepEqual(scan.violations, [], JSON.stringify(scan.violations));
    }
    // Missing/corrupt language bundle, blocked storage and invalid preference all fail to English.
    const failed = await browser.newContext();
    await failed.route('**/assets/i18n-catalog.js', route => route.fulfill({ contentType: 'text/javascript', body: '// Simulated missing catalog' }));
    const fallback = await failed.newPage(); await fallback.goto(url, { waitUntil: 'domcontentloaded' });
    await fallback.selectOption('#language-select', 'fr');
    assert.equal(await fallback.locator('html').getAttribute('lang'), 'en');
    assert.equal(await fallback.locator('#language-select').inputValue(), 'en');
    assert(await fallback.locator('#language-feedback').isVisible());
    await failed.close();
    const blocked = await browser.newContext();
    await blocked.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('Blocked storage'); } }); });
    const privatePage = await blocked.newPage(); await privatePage.goto(url, { waitUntil: 'domcontentloaded' });
    await privatePage.selectOption('#language-select', 'de');
    assert.equal(await privatePage.locator('html').getAttribute('lang'), 'de'); await blocked.close();
    const invalid = await browser.newContext();
    await invalid.addInitScript(() => localStorage.setItem('alignment-language', 'unknown'));
    const invalidPage = await invalid.newPage(); await invalidPage.goto(url, { waitUntil: 'domcontentloaded' });
    await invalidPage.waitForFunction(() => !!window.AlignmentI18n);
    assert.equal(await invalidPage.locator('html').getAttribute('lang'), 'en'); await invalid.close();
    assert.deepEqual(results.errors, [], 'Browser errors');
    fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2));
    console.log(`PASS state preservation, real video playback, Shopify, accessibility, load/storage fallbacks. Artifacts: ${out}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
