ALIGNMENT CAMPAIGN - LOCAL REVIEW

Static HTML, inline CSS and JavaScript. No build step or production dependencies.

LOCAL PREVIEW
From this directory run:
  python3 -m http.server 8000 --bind 127.0.0.1
Open http://127.0.0.1:8000 in a browser. Asset paths are relative, so opening
index.html directly or serving from a subdirectory is also supported.

PRODUCTION DESTINATIONS
- The canonical Shopify product URL is defined once on #combo-product in
  index.html. campaignConfig reads it and applies it to all six purchase CTAs.
- With JavaScript enabled all six purchase CTAs open Shopify in a new tab with
  noopener noreferrer. Section navigation and book discovery stay internal.
- Without JavaScript the final purchase link still works; other combo CTAs scroll
  to the offer in the same tab. The page explains this fallback.
- heroVideoUrl is defined once in campaignConfig. The HTML5 player uses native
  controls, playsinline, metadata preload, and no autoplay. On failure or when
  JavaScript is disabled, the original book poster remains visible.
- The navbar supports English, French, Spanish, Portuguese, Arabic (RTL), German
  and Italian with saved language preferences. See I18N.md for dictionary editing,
  local preview, test commands, editorial review and international SEO notes.

PRESERVED CONTENT AND ASSETS
- The eight topic cards preserve the existing book framework; they are not a
  verified course syllabus. Use approved content for future curriculum updates.
- The guide biography and existing portrait crop are retained without face edits.
- Original PNGs and apostle-hero.webp are untouched. assets/ contains the optimized
  derivatives, lightweight topic SVGs and favicon used by the landing page.
- Below-the-fold images use lazy loading and explicit dimensions.
- Book introduction uses 55/45 Flexbox columns above 991px, with content first
  and image below at narrower widths. Topic cards use three/two/one columns.

AUDIT AND VERIFICATION
See ALIGNMENT-WEBSITE-AUDIT.md for findings, verified destinations, results and
remaining launch decisions. Optional repeatable audit tools and setup are in
qa/README.md. No site build/lint command or package manifest is required.

BEFORE PAID CAMPAIGN LAUNCH
- Approve final combo contents, course curriculum, regional pricing and delivery.
- Review actual Shopify availability, shipping/refund terms and fulfillment.
- Confirm the supplied video is the intended campaign content and provide approved
  captions/transcript if it includes speech or other meaningful audio.
- Supply the production domain for canonical and absolute social-image metadata.
- Approve analytics, conversion/attribution requirements and relevant consent setup.
- Review Safari/Firefox and physical mobile devices, and test Shopify end to end.

No deployment, push or merge is authorized by this audit.
