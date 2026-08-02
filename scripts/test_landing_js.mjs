/* Drives every interactive control on the landing page with a DOM stub.
 * Run from tests/test_landing.py so there is one command for the whole suite. */
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../public/landing.html', import.meta.url), 'utf8');
const js = html.split('<script>')[1].split('</script>')[0];

let fails = 0;
const ok = (n, c) => { console.log((c ? '  ok   ' : '  FAIL ') + n); if (!c) fails++; };

function mk(tag) {
  return {
    tag, className: '', dataset: {}, style: {}, _kids: [], _html: '', _attrs: {}, _on: {},
    classList: {
      _s: new Set(),
      add(...c) { c.forEach(x => this._s.add(x)); },
      remove(...c) { c.forEach(x => this._s.delete(x)); },
      toggle(c) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); return this._s.has(c); },
      contains(c) { return this._s.has(c); },
    },
    setAttribute(k, v) { this._attrs[k] = String(v); },
    getAttribute(k) { return this._attrs[k]; },
    addEventListener(e, fn) { (this._on[e] ||= []).push(fn); },
    appendChild(c) { this._kids.push(c); return c; },
    replaceChildren(...c) { this._kids = c; },
    get children() { return this._kids; },
    get innerHTML() { return this._html; }, set innerHTML(v) { this._html = v; this._kids = []; },
    fire(e, ev = {}) { (this._on[e] || []).forEach(fn => fn({ target: this, ...ev })); },
  };
}

const byId = {};
['menuBtn', 'mainNav', 'themeBtn', 'playBtn', 'video', 'embers'].forEach(i => (byId[i] = mk('div')));
const thumb = mk('img');
const root = mk('html');

global.document = {
  documentElement: root,
  getElementById: (id) => byId[id] ?? mk('div'),
  querySelector: (s) => (s === '.video img' ? thumb : mk('div')),
  querySelectorAll: () => [mk('div'), mk('div')],
  createElement: (t) => mk(t),
};
let mm = { matches: false };
global.matchMedia = () => mm;
global.IntersectionObserver = function () { this.observe = () => {}; this.unobserve = () => {}; };
global.window = { IntersectionObserver: global.IntersectionObserver };
global.setTimeout = (fn) => fn();
const ls = new Map();
global.localStorage = {
  getItem: (k) => ls.get(k) ?? null, setItem: (k, v) => ls.set(k, v), removeItem: (k) => ls.delete(k),
};

let threw = null;
try { eval(js); } catch (e) { threw = e; }
ok('script runs with no runtime error' + (threw ? ': ' + threw.message : ''), !threw);

console.log('\nmobile nav');
byId.menuBtn.fire('click');
ok('menu opens', byId.mainNav.classList.contains('open'));
ok('reports aria-expanded', byId.menuBtn.getAttribute('aria-expanded') === 'true');
byId.mainNav.fire('click', { target: { tagName: 'A' } });
ok('closes after choosing a link', !byId.mainNav.classList.contains('open'));

console.log('\ntheme toggle');
byId.themeBtn.fire('click');
ok('sets a theme', ['dark', 'light'].includes(root.dataset.theme));
ok('persists the choice', ls.get('aitb.theme') === root.dataset.theme);
const first = root.dataset.theme;
byId.themeBtn.fire('click');
ok('toggles back', root.dataset.theme !== first);

console.log('\nhero video — loads only on click');
ok('nothing embedded on arrival', byId.video.children.length === 0);
let prevented = false;
byId.playBtn.fire('click', { preventDefault: () => { prevented = true; } });
const f = byId.video.children[0];
ok('iframe appears on click', !!f && f.tag === 'iframe');
ok('uses the no-cookie domain', f.src.startsWith('https://www.youtube-nocookie.com/embed/'));
ok('carries the supplied video id', f.src.includes('uNLiQLISEOo'));
ok('autoplays once asked for', f.src.includes('autoplay=1'));
ok('allows fullscreen', f.allowFullscreen === true);
ok('iframe is titled', typeof f.title === 'string' && f.title.length > 0);
ok('navigation suppressed once the embed succeeds', prevented === true);

// If the embed cannot be built, the click must NOT be intercepted — the browser
// follows the href and the video still plays on YouTube.
const realCreate = document.createElement;
document.createElement = () => { throw new Error('iframe blocked'); };
let prevented2 = false;
byId.playBtn.fire('click', { preventDefault: () => { prevented2 = true; } });
document.createElement = realCreate;
ok('falls through to the YouTube link when the embed fails', prevented2 === false);

console.log('\nthumbnail fallback');
thumb.fire('error');
ok('falls back when maxres is missing', String(thumb.src).includes('hqdefault'));

console.log('\nmotion');
ok('embers rendered when motion is fine', byId.embers.children.length === 18);
byId.embers._kids = [];
mm = { matches: true };
try { eval(js); } catch (e) { ok('reduced-motion path runs', false); }
ok('no embers under prefers-reduced-motion', byId.embers.children.length === 0);

console.log(fails ? `\n${fails} FAILURE(S)` : '\nall interactive elements function');
process.exit(fails ? 1 : 0);
