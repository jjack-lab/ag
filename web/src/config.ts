/**
 * 构建期可配置项。演示任务是"本机数据库里的一个任务 ID"，
 * 换机器或重建数据库后必须重新指定，否则演示入口会指向不存在的任务。
 */

export const FALLBACK_CATTLE_DEMO_JOB_ID = "202d89f9aaad433480d8570bd90c3d41";

export function resolveCattleDemoJobId(env: Record<string, string | undefined>): string {
  const configured = (env.VITE_CATTLE_DEMO_JOB_ID || "").trim();
  return configured || FALLBACK_CATTLE_DEMO_JOB_ID;
}

export const cattleDemoJobId = resolveCattleDemoJobId(
  import.meta.env as unknown as Record<string, string | undefined>,
);
