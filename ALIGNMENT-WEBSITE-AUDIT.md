# ALIGNMENT website audit

Audit date: 27 October 2026. Branch: `audit/alignment-campaign-qa`.

## Executive summary — initial audit

This is a static campaign page: one HTML file with inline CSS and JavaScript,
16 original/derived image files plus a favicon, and a README. There is no package
manifest, build pipeline, analytics pixel, tag manager, or existing test command.
Existing uncommitted changes were retained; a baseline copy and patch were saved
outside the repository before repairs. The existing section order, copy, artwork,
Shopify destination and video destination are the audit baseline.

The initial browser scan found no page overflow at the nine requested widths and
no JavaScript exceptions. Shopify and Cloudinary both returned HTTP 200. The
following issues were confirmed before changes to the website.

## Initial issues discovered

| Severity | Finding | Evidence / impact |
| --- | --- | --- |
| HIGH | Misleading language selector | Four advertised languages have almost no matching translations. Selecting them changes `html.lang` while the page remains English, including for assistive technology. |
| HIGH | Text contrast failures | axe found brand subtext at 3.37:1, journey introduction at 4.4:1, and book heading gold at 2.9:1 against ivory; below the applicable 4.5:1 / 3:1 thresholds. |
| HIGH | Purchase destination depends entirely on JavaScript | All six purchase links initially point to `#offer` with `_blank`; without initialization they open another copy of the landing page, including the bundle's final purchase link. |
| MEDIUM | Conflicting hero typography | `.hero p` overrides the lead's responsive font/width and the small caption's intended 10px size. At 1440px both render at 18px with a 520px maximum, causing unnecessary wrapping. |
| MEDIUM | Small-screen heading and intro wrapping | Fixed 42px section-heading minimum and missing balanced wrapping make major headings awkward on narrow screens. FAQ eyebrow and centered title use different alignments. |
| MEDIUM | Keyboard/menu polish | Menu closes on link/Escape but lacks outside-click handling and intentional focus restoration after hiding its links. |
| MEDIUM | Purchase buttons lack consistent hover/pressed treatment | Global focus styling exists, but most CTA variants have no clear hover or active state. |
| MEDIUM | Video error leaves a failed player visible | Error message appears, but the errored player and its controls remain. No approved caption file is present. Caption/content suitability requires review. |
| MEDIUM | Social preview metadata absent | Title and description exist; no Open Graph title, description, type or site name. Production domain is not supplied. |
| LOW | Dead CSS and conflicting legacy rules | Unused mockups, video placeholders, cinematic layouts, old card/step styles and disabled checkout styling remain. No corresponding live elements or script references. |
| LOW | README contradicts current implementation | Says checkout is disabled/unconnected even though production links were supplied and connected. |
| LOW | HTML convention warning | HTML validator flags lowercase doctype; no other initial HTML errors and no CSS parse/declaration errors. |

No confirmed critical issue affects the normal JavaScript-enabled purchase path.
A full purchase, fulfillment, caption accuracy and advertising attribution have
not been verified. No payment will be submitted as part of this audit.

## Initial section inventory

Header/desktop and mobile navigation; `#home` hero/video; `#problem` book and four
problem cards; `#journey` combo image/four stages; `#book` eight existing framework
topics; `#revelation`; `#author`; `#offer`; `#faq`; `#closing`; footer.
The problem-awareness and book introduction content share one section. The
learning topics are the existing book framework, not a verified course syllabus.
Footer contains attribution and a Shopify purchase note, with no actual links.

## Verification and repairs

In progress. Final findings, CTA inventory, responsive results and outstanding
launch requirements will be recorded below when verification is complete.
