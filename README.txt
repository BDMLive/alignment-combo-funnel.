ALIGNMENT COMBO FUNNEL - PREVIEW

Static HTML, inline CSS and JavaScript. No build step or runtime dependencies.

LOCAL PREVIEW
From this directory run:
  python3 -m http.server 8000 --bind 127.0.0.1
Then open http://127.0.0.1:8000 in a browser.
Opening index.html directly also works; asset paths are relative.

CAMPAIGN SECTIONS
- Eight illustrated cards preserve the existing book framework verbatim.
  These are not a verified course syllabus; replace only with approved content.
- The guide section reuses the existing biography and an unretouched crop from
  alignment-full-cover.png. No face generation or identity edits were applied.
- The bundle retains all existing formats and confirmation notices.
- Navigation includes a keyboard-accessible mobile menu and skip link.
- Desktop cards use three columns, tablets two, and mobile one.

ASSETS
Original PNGs and apostle-hero.webp remain untouched.
assets/ contains optimized JPEG derivatives, eight lightweight SVG topic
illustrations, and a compass favicon. Below-the-fold images are lazy-loaded.
To regenerate JPEG derivatives with macOS sips:
  sips -s format jpeg -s formatOptions 82 -Z 960 alignment-combo-promo.png --out assets/alignment-combo.jpg
  sips -s format jpeg -s formatOptions 85 -Z 760 alignment-book-cover.png --out assets/alignment-cover.jpg
  sips -c 610 610 --cropOffset 160 1080 -s format jpeg -s formatOptions 88 alignment-full-cover.png --out assets/apostle-bible-davids.jpg

BEFORE LAUNCH
- Confirm actual combo contents, course curriculum and regional prices.
- Supply official Shopify checkout link and digital delivery details.
- Confirm physical book availability, shipping and refund terms.
- Replace disabled checkout with verified Shopify link.
- Complete translations. The existing language selector contains only a small
  dictionary and most current copy remains English.
- Connect a domain and deploy to hosting after approval.

There is no configured build, lint or test command. Browser validation for this
update used temporary Playwright tooling with installed Chrome at widths of
320, 390, 600, 768, 1024, 1100, 1280 and 1440 pixels. Checks cover overflow,
image loading, anchor targets, grid columns, mobile menu, FAQ, language selector,
reduced motion, JavaScript errors and failed requests. Visual review covers
module cards, guide and bundle on desktop, tablet and mobile.

This website is not yet deployed or connected to checkout.
