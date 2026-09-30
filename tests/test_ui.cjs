const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// A minimal DOM isolates saved-result navigation from the detailed result renderer.
class Element {
  constructor() { this.children = []; this.textContent = ''; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
}

test('opening a saved result replaces the previous run status', async () => {
  const elements = Object.fromEntries(
    ['#result', '#history', '#status', '#more', '#form', '#submit', '#company']
      .map(selector => [selector, new Element()])
  );
  const saved = {
    id: 'saved', status: 'classified', request: { company_name: 'Saved Company' }
  };
  const context = {
    document: {
      querySelector: selector => elements[selector],
      createElement: () => new Element()
    },
    fetch: async url => ({
      ok: true,
      json: async () => url.includes('?')
        ? [{ id: saved.id, company_name: 'Saved Company', status: saved.status,
             created_at: '2026-09-29T12:00:00Z' }]
        : saved
    })
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  vm.runInContext('render = result => { globalThis.displayed = result; }', context);
  elements['#status'].textContent = 'Result saved · abstained';
  await elements['#history'].children[0].onclick();
  assert.equal(context.displayed.id, saved.id);
  assert.equal(elements['#status'].textContent, 'Saved result · Saved Company · classified');
});
