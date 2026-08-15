/** Health probe payload — mirrors GET /health envelope data. */
export interface HealthInfo {
  status: string;
}

/** Version probe payload — mirrors GET /version envelope data. */
export interface VersionInfo {
  version: string;
  app: string;
}

/** Combined system info for the Home operational summary. */
export interface SystemInfo {
  health: HealthInfo;
  version: VersionInfo;
}
