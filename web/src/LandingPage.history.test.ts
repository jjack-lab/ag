import { fireEvent } from "@testing-library/dom";
import { expect, it, vi } from "vitest";
import html from "../index.html?raw";

it("does not overwrite a newer browser history navigation during an animated transition", () => {
  vi.useFakeTimers();
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  vi.stubGlobal("scrollTo", vi.fn());
  const chain = { to: () => chain, from: () => chain, fromTo: () => chain, kill: vi.fn() };
  const delayed = (_target: unknown, options: {duration?: number; onComplete?: () => void}) => {
    if (options.onComplete) setTimeout(options.onComplete, (options.duration || 0) * 1000);
  };
  Object.defineProperty(window, "gsap", { configurable: true, value: {
    timeline: () => chain, set: vi.fn(), from: vi.fn(), to: delayed,
    fromTo: (target: unknown, _from: unknown, options: Parameters<typeof delayed>[1]) => delayed(target, options),
    context: (callback: () => void) => { callback(); return { revert: vi.fn() }; },
  } });
  const page = new DOMParser().parseFromString(html, "text/html");
  document.body.innerHTML = page.body.innerHTML;
  history.replaceState({}, "", "#/home");
  window.eval(Array.from(page.querySelectorAll("script")).find((script) => !script.src)!.textContent!);
  fireEvent.click(document.querySelector('.nav [data-route="capabilities"]')!);
  vi.advanceTimersByTime(700);
  fireEvent.click(document.querySelector('.nav [data-route="evidence"]')!);
  history.replaceState({}, "", "#/home");
  window.dispatchEvent(new PopStateEvent("popstate"));
  const push = vi.spyOn(history, "pushState");
  vi.advanceTimersByTime(2000);
  expect(push).not.toHaveBeenCalled();
  expect(location.hash).toBe("#/home");
  expect(document.querySelectorAll(".view.is-active")).toHaveLength(1);
  expect(document.querySelector(".view.is-active")).toHaveAttribute("id", "view-home");
  vi.useRealTimers(); vi.unstubAllGlobals();
});
