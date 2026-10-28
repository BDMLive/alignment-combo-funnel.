/* Translate text nodes in place: preserve markup, links, media and interface state. */
(() => {
  'use strict';
  const names = { en: 'English', fr: 'Français', es: 'Español', pt: 'Português', ar: 'العربية', de: 'Deutsch', it: 'Italiano' };
  const storageKey = 'alignment-language';
  const root = document.documentElement;
  const select = document.getElementById('language-select');
  const status = document.getElementById('language-feedback');
  const catalog = window.ALIGNMENT_LOCALES || {};
  const english = { ...(catalog.en || {}) };
  const textBindings = [];
  const attributeBindings = [];
  let revision = 0;
  const originalScrollBehavior = root.style.scrollBehavior;
  for (const element of document.querySelectorAll('[data-i18n-text]')) {
    const keys = element.dataset.i18nText.split(' ');
    const nodes = [...element.childNodes].filter(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
    nodes.forEach((node, index) => {
      const key = keys[index];
      if (!key) return;
      const original = node.textContent;
      english[key] ??= original.trim().replace(/\s+/g, ' ');
      textBindings.push({ node, key, before: original.match(/^\s*/)[0], after: original.match(/\s*$/)[0] });
    });
  }
  for (const link of document.querySelectorAll('[data-combo-purchase]')) {
    link.dataset.i18nAriaDescription = 'accessibility.shopifyNewTab';
  }
  for (const attribute of ['alt', 'aria-label', 'aria-description', 'title', 'placeholder', 'content']) {
    for (const element of document.querySelectorAll(`[data-i18n-${attribute}]`)) {
      const key = element.getAttribute(`data-i18n-${attribute}`);
      english[key] ??= element.getAttribute(attribute) || '';
      attributeBindings.push({ element, attribute, key });
    }
  }
  // These English messages are also present in locales/en.json. They work if the bundle fails.
  english['accessibility.languageFailure'] ??= status.dataset.loadError;
  english['accessibility.languageStatus'] ??= status.dataset.changed;
  const keys = Object.keys(english);
  function available(language) {
    return language === 'en' || (Object.hasOwn(names, language) && catalog[language] && keys.every(key => typeof catalog[language][key] === 'string' && catalog[language][key].trim()));
  }
  function setLanguage(requested, { persist = true, announce = true } = {}) {
    const failed = !available(requested);
    const language = failed ? 'en' : requested;
    const dictionary = language === 'en' ? english : catalog[language];
    const translate = key => dictionary[key] || english[key] || '';
    const scrollY = window.scrollY;
    const currentRevision = ++revision;
    root.style.scrollBehavior = 'auto';
    root.lang = language;
    root.dir = language === 'ar' ? 'rtl' : 'ltr';
    for (const { node, key, before, after } of textBindings) {
      node.textContent = before + translate(key) + after;
    }
    for (const { element, attribute, key } of attributeBindings) {
      element.setAttribute(attribute, translate(key));
    }
    select.value = language;
    // Security attributes, destinations, media elements and expanded states stay untouched.
    if (persist && !failed) {
      try { localStorage.setItem(storageKey, language); } catch { /* Private browsing can deny storage. */ }
    }
    status.classList.toggle('language-feedback--error', failed);
    status.textContent = failed ? english['accessibility.languageFailure'] : announce ? translate('accessibility.languageStatus').replace('{language}', names[language]) : '';
    window.scrollTo(0, scrollY);
    requestAnimationFrame(() => {
      if (currentRevision !== revision) return;
      window.scrollTo(0, scrollY);
      root.style.scrollBehavior = originalScrollBehavior;
      document.dispatchEvent(new CustomEvent('alignment:languagechange', { detail: { language } }));
    });
    return language;
  }
  let preferred = 'en';
  try {
    const stored = localStorage.getItem(storageKey);
    if (Object.hasOwn(names, stored)) preferred = stored;
  } catch { /* English remains the default when storage is unavailable. */ }
  select.addEventListener('change', () => setLanguage(select.value));
  setLanguage(preferred, { persist: false, announce: false });
  select.disabled = false;
  window.AlignmentI18n = Object.freeze({ setLanguage, languages: Object.freeze(Object.keys(names)) });
})();
