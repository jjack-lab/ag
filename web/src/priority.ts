/**
 * 核查优先级：由规则命中的严重程度换算，用来说明"先看哪一头"，
 * 不是疾病概率，也不要当成跨视频可比的健康分。
 */

export type CheckPriority = "high" | "medium" | "low" | "none" | "unavailable";

export const priorityLabel: Record<CheckPriority, string> = {
  high: "高 · 优先核查",
  medium: "中 · 优先核查",
  low: "低 · 例行观察",
  none: "无 · 未触发规则",
  unavailable: "无评分",
};

export const priorityShort: Record<CheckPriority, string> = {
  high: "高",
  medium: "中",
  low: "低",
  none: "无",
  unavailable: "—",
};

export function priorityFromRiskLevel(level?: string | null): CheckPriority {
  if (level === "high" || level === "medium" || level === "low" || level === "none") return level;
  if (level === "normal") return "none";
  return "unavailable";
}

export function priorityOf(row: { priority?: string | null; risk_level?: string | null }): CheckPriority {
  const value = row.priority;
  if (value === "high" || value === "medium" || value === "low" || value === "none" || value === "unavailable") {
    return value;
  }
  return priorityFromRiskLevel(row.risk_level);
}
