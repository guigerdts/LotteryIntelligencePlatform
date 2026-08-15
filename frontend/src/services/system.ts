import type { HealthInfo, SystemInfo, VersionInfo } from "../types/system";
import { apiClient } from "./api";

/** Fetch the API liveness probe (GET /health). */
export async function getHealth(): Promise<HealthInfo> {
  return apiClient<HealthInfo>("/health");
}

/** Fetch the running application name and version (GET /version). */
export async function getVersion(): Promise<VersionInfo> {
  return apiClient<VersionInfo>("/version");
}

/** Fetch health and version together for the Home page system block. */
export async function getSystemInfo(): Promise<SystemInfo> {
  const [health, version] = await Promise.all([getHealth(), getVersion()]);
  return { health, version };
}
