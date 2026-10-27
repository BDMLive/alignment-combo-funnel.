const { HtmlValidate } = require('html-validate');
const csstree = require('css-tree');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
(async () => {
  const html = fs.readFileSync(process.argv[2] || 'index.html', 'utf8');
  const validator = new HtmlValidate({
    extends: ['html-validate:recommended'],
    rules: {
      'void-style': ['error', { style: 'selfclose' }],
      'no-inline-style': 'off', // Preserve existing inline editorial sizing/background choices.
      'long-title': 'off', // Preserve the approved campaign title.
      'attr-quotes': ['error', { style: 'double' }],
    },
  });
  const result = await validator.validateString(html);
  const cssIssues = [];
  const css = [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
  const tree = csstree.parse(css, { positions: true, onParseError: e => cssIssues.push(e.message) });
  csstree.walk(tree, node => {
    if (node.type !== 'Declaration' || node.property.startsWith('--')) return;
    const match = csstree.lexer.matchProperty(node.property, node.value);
    if (match.error && !csstree.generate(node.value).includes('var(')) {
      cssIssues.push({ property: node.property, value: csstree.generate(node.value), error: match.error.message });
    }
  });
  // A separate Node syntax check validates all actual JavaScript (not video fallback text).
  const vm = require('node:vm');
  for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
  const xml = require('node:child_process').spawnSync('python3', ['-c',
    "import pathlib,xml.etree.ElementTree as ET;[ET.parse(p) for p in pathlib.Path('assets').glob('*.svg')];print('SVG XML valid')"], { encoding: 'utf8' });
  if (xml.status !== 0) throw new Error(xml.stderr);
  const out = process.env.QA_OUTPUT || path.join(os.tmpdir(), 'alignment-audit-results');
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, 'validation.json'), JSON.stringify({ html: result.results, css: cssIssues, svg: xml.stdout.trim(), javascript: 'Syntax valid' }, null, 2));
  console.log('HTML:', result.valid ? 'PASS' : JSON.stringify(result.results));
  console.log('CSS:', cssIssues.length === 0 ? 'PASS' : JSON.stringify(cssIssues));
  console.log('JavaScript: PASS'); console.log(xml.stdout.trim());
  if (!result.valid || cssIssues.length) process.exitCode = 1;
})().catch(error => { console.error(error); process.exit(1); });
