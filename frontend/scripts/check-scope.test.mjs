import assert from 'node:assert/strict';
import { test } from 'node:test';
import { checkCss, checkTemplate } from './check-scope.mjs';

const SCOPE = '[data-addon] addon-server, [data-addon] addon-chestsort';

test('a rule under the scope, with nested rules, passes', () => {
  assert.deepEqual(checkCss(`${SCOPE} { display: block; & .err { color: var(--bad); } }`), []);
});

test('a rule that does not start with [data-addon] fails', () => {
  assert.equal(checkCss('button { color: red; }').length, 1);
  assert.equal(checkCss(`${SCOPE}, body { color: red; }`).length, 1);
  assert.equal(checkCss('.err { color: var(--bad); }').length, 1);
});

test('a hex colour fails, an id selector does not', () => {
  assert.equal(checkCss(`${SCOPE} { color: #ff0000; }`).length, 1);
  assert.equal(checkCss(`${SCOPE} { & #cs-list { min-width: 1rem; } }`).length, 0);
});

test('an at-rule at the top level fails', () => {
  assert.equal(checkCss('@import "x.css";').length, 1);
});

test('comments are ignored', () => {
  assert.deepEqual(checkCss(`/* button { } #fff */ ${SCOPE} { color: var(--text); }`), []);
});

test('an inline style in a template fails', () => {
  assert.equal(checkTemplate('<p style="color: red">x</p>').length, 1);
  assert.equal(checkTemplate('<p [style.width.px]="3">x</p>').length, 1);
  assert.deepEqual(checkTemplate('<p class="err">x</p>'), []);
});
