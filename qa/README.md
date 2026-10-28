# Local campaign QA

The production site remains dependency-free. These optional Node scripts use
external developer tooling; they are not loaded by the website.

From the repository root:

```sh
npm install --prefix /tmp/alignment-qa-tools --no-save playwright @axe-core/playwright html-validate css-tree
python3 -m http.server 8000 --bind 127.0.0.1
```

In a second terminal:

```sh
NODE_PATH=/tmp/alignment-qa-tools/node_modules node qa/validate.cjs
NODE_PATH=/tmp/alignment-qa-tools/node_modules node qa/audit.cjs
git diff --check
```

The audit defaults to installed macOS Google Chrome. Override `CHROME_PATH` for
another installed Chromium binary, `QA_URL` for another local port, or `QA_OUTPUT`
for a different artifact directory. Results and screenshots are saved under
`alignment-audit-results` in the operating system temporary directory. Internet
access is required for actual Cloudinary metadata and playback tests.

The suite checks all nine requested viewport widths, every visible navigation
link/CTA, desktop book Flexbox, stages/topics grids, images, keyboard focus,
FAQ accordions, reduced motion, accessibility, video playback, errors, and no-JS
purchase fallback. Automated accessibility results do not establish full WCAG
compliance or certify caption accuracy.

Popup URLs are intercepted in the test browser: links and new-tab behavior are
verified without entering a storefront, cart or payment flow. The actual product
URL was independently checked read-only with HTTP HEAD. No purchases are made.

HTML validation allows existing inline styles and the approved long page title;
CSS parsing/declaration checks cover both the main and no-JS stylesheets. Custom
properties are resolved by the browser; the CSS grammar checker cannot certify
all `var()` substitutions. SVG XML and inline JavaScript syntax are also checked.

Device-width tests use headless Chrome; Safari, Firefox, physical mobile devices,
screen readers, native fullscreen media and real checkout/fulfillment remain
manual review tasks. Screenshot styling hides sticky navigation only for section
captures; full-page screenshots retain it. No production DOM/styles are changed
by these test-only screenshot overrides.

## Focused FAQ and footer check

Run the new audit from the project root (it supports opening the local file,
so a preview server is optional):

```sh
NODE_PATH=/tmp/alignment-qa-tools/node_modules node qa/faq-footer.cjs
```

It requires `playwright` and `@axe-core/playwright` in the temporary tooling
folder. It checks all eight questions with Enter/Space and pointer interaction,
single-open behavior (including the JavaScript fallback without native grouping),
ARIA state, answer visibility, plus/minus icons, purchase and ministry popup URLs,
all footer anchors and sticky-header clearance, dynamic year, reduced motion,
no-JavaScript fallback, scoped accessibility/contrast, and browser errors at
375, 390, 768, 1024, and 1440 pixels. External popup destinations are intercepted;
this does not verify Shopify fulfillment or complete a purchase.

For Safari-engine coverage, install and run temporary WebKit:

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/alignment-browser-tools node /tmp/alignment-qa-tools/node_modules/playwright/cli.js install webkit
QA_BROWSER=webkit PLAYWRIGHT_BROWSERS_PATH=/tmp/alignment-browser-tools NODE_PATH=/tmp/alignment-qa-tools/node_modules node qa/faq-footer.cjs
```

Use `QA_OUTPUT` to separate engine artifacts; defaults to `alignment-faq-footer`
in the operating system temporary directory. Screenshots and `results.json`
are saved there. WebKit coverage does not replace physical iOS/Safari or
screen-reader review.

Preview the website with `python3 -m http.server 8000 --bind 127.0.0.1`, then open
`http://127.0.0.1:8000/#faq`. No build step is needed.

Product details still requiring ministry confirmation: exact Combo inclusions,
available physical/digital formats, current pricing, delivery, and access
instructions. The official product page was rate-limited during this review;
FAQ answers link to it rather than promise unverified details. No approved
catalog destination exists in the ALIGNMENT project, so the footer omits
“Explore More Courses.” The live FAQ CTA now owns `#combo-product`, restoring
the shared purchase-link configuration after the former source was commented
out. No unrelated campaign sections were edited.

Verified 28 October 2026 in installed Chrome and Playwright WebKit 27.2 at all
five widths above: all focused checks passed, with no JavaScript/console errors,
no horizontal overflow, and no scoped WCAG A/AA violations from axe. CSS and
JavaScript validation passed; HTML validation reports only the existing lowercase
doctype convention. Desktop/mobile screenshots were visually reviewed. No
production deployment, merge, or push was performed.

## Multilingual regression check

See `../I18N.md` for the localization architecture, dictionary regeneration,
translation review requirements and multilingual QA commands. `qa/i18n.cjs`
checks all seven languages at 320, 375, 390, 768, 1024 and 1440 pixels, including
Arabic RTL, complete binding coverage, persistence and fallbacks, keyboard FAQs,
anchors, secure CTAs, scroll/UI/media state and scoped accessibility.
