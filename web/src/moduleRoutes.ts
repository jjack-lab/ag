export const moduleNames = [
  "overview", "monitor", "health", "alerts", "tasks", "cattle", "analytics", "inventory",
] as const;

export type ModuleName = (typeof moduleNames)[number];

export type SiteRoute =
  | { kind: "home" }
  | { kind: "modules" }
  | { kind: "module"; name: ModuleName };

export function moduleHref(name: ModuleName): string {
  return `#/module/${name}`;
}

export function parseSiteRoute(hash: string): SiteRoute {
  if (hash === "#/modules") return { kind: "modules" };
  const match = /^#\/module\/([a-z]+)$/.exec(hash);
  if (match && moduleNames.includes(match[1] as ModuleName)) {
    return { kind: "module", name: match[1] as ModuleName };
  }
  return { kind: "home" };
}
