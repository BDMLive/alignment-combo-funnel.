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
