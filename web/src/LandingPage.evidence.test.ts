import { expect, it, vi } from 'vitest';
import html from '../index.html?raw';

it('shows complete evidence values without scrolling when animation libraries are available', () => {
  vi.useFakeTimers();
  vi.stubGlobal('matchMedia', () => ({ matches: false }));
  vi.stubGlobal('scrollTo', vi.fn());
  vi.stubGlobal('ScrollTrigger', { refresh: vi.fn() });
  const pinRequests: unknown[] = [];
  const chain = { to: () => chain, from: () => chain, fromTo: () => chain };
  vi.stubGlobal('gsap', {
    registerPlugin: vi.fn(), set: vi.fn(), from: vi.fn(), to: vi.fn(), fromTo: vi.fn(),
    context: (fn: () => void) => { fn(); return { revert: vi.fn() }; },
    matchMedia: () => ({ add: (query: string, fn: () => void) => { if (query.includes('min-width')) fn(); } }),
    timeline: (options?: { onComplete?: () => void; scrollTrigger?: { pin?: boolean } }) => {
      if (options?.scrollTrigger?.pin) pinRequests.push(options);
      if (options?.onComplete) setTimeout(options.onComplete, 1);
      return chain;
    },
  });
  const page = new DOMParser().parseFromString(html, 'text/html');
  document.body.innerHTML = page.body.innerHTML;
  history.replaceState({}, '', '#/evidence');
  window.eval([...page.querySelectorAll('script')].find(s => !s.src)!.textContent!);
  vi.advanceTimersByTime(5);
  expect([...document.querySelectorAll('.stat-card b')].map(e => e.textContent)).toEqual(['4 类', '26 个', '210 帧', '26 条']);
  expect(pinRequests).toHaveLength(0);
  vi.useRealTimers(); vi.unstubAllGlobals();
});
