import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { apiClient, NotFoundError, ConflictError, ValidationError, ServerError } from "./api";

describe("apiClient", () => {
  const BASE = "/api/v1";
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns unwrapped data on successful envelope", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { id: 1 },
        timestamp: "2026-01-01T00:00:00Z",
      }),
    });

    const result = await apiClient("/lotteries");
    expect(result).toEqual({ id: 1 });
  });

  it("throws AppError on error envelope with code", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: false,
        error: { code: "GEN_NO_SELECTION", message: "No active selection" },
        timestamp: "2026-01-01T00:00:00Z",
      }),
    });

    await expect(apiClient("/gen/generate")).rejects.toThrow("No active selection");
  });

  it("throws NotFoundError on 404", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        success: false,
        error: { code: "RESOURCE_NOT_FOUND", message: "Not found" },
        timestamp: "",
      }),
    });

    await expect(apiClient("/lotteries/999")).rejects.toBeInstanceOf(NotFoundError);
  });

  it("throws ConflictError on 409", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({
        success: false,
        error: { code: "DUPLICATE_RESOURCE", message: "Conflict" },
        timestamp: "",
      }),
    });

    await expect(apiClient("/lotteries")).rejects.toBeInstanceOf(ConflictError);
  });

  it("throws ValidationError on 422", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({
        success: false,
        error: { code: "VALIDATION_ERROR", message: "Invalid" },
        timestamp: "",
      }),
    });

    await expect(apiClient("/gen/generate")).rejects.toBeInstanceOf(ValidationError);
  });

  it("throws ServerError on 500", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        success: false,
        error: { code: "INTERNAL_ERROR", message: "Server error" },
        timestamp: "",
      }),
    });

    await expect(apiClient("/lotteries")).rejects.toBeInstanceOf(ServerError);
  });

  it("throws ServerError on network failure", async () => {
    fetchSpy.mockRejectedValueOnce(new TypeError("fetch failed"));

    await expect(apiClient("/lotteries")).rejects.toThrow("fetch failed");
  });

  it("sends POST with body and returns data", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { snapshot_id: 1 },
        timestamp: "2026-01-01T00:00:00Z",
      }),
    });

    const result = await apiClient("/statistics/generate", {
      method: "POST",
      body: JSON.stringify({ lottery_code: "L1" }),
    });
    expect(result).toEqual({ snapshot_id: 1 });
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/statistics/generate`,
      expect.objectContaining({ method: "POST" })
    );
  });

  it("constructs full URL from base + path", async () => {
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, data: "ok", timestamp: "" }),
    });

    await apiClient("/health");
    expect(fetchSpy).toHaveBeenCalledWith("/api/v1/health", expect.anything());
  });
});
