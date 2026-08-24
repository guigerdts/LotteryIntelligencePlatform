import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLotteryStore } from "./useLotteryStore";

describe("useLotteryStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useLotteryStore.setState({
      lotteries: [],
      selectedLotteryId: null,
      selectedLotteryCode: null,
      isLoading: false,
      error: null,
    });
  });

  it("starts with no selected lottery", () => {
    const { result } = renderHook(() => useLotteryStore());
    expect(result.current.selectedLotteryId).toBeNull();
    expect(result.current.selectedLotteryCode).toBeNull();
    expect(result.current.lotteries).toEqual([]);
  });

  it("setSelected sets both id and code atomically", () => {
    const { result } = renderHook(() => useLotteryStore());

    act(() => {
      result.current.setSelected(5, "L1");
    });

    expect(result.current.selectedLotteryId).toBe(5);
    expect(result.current.selectedLotteryCode).toBe("L1");
  });

  it("setSelected clears selection when called with null", () => {
    const { result } = renderHook(() => useLotteryStore());

    act(() => {
      result.current.setSelected(5, "L1");
    });
    act(() => {
      result.current.setSelected(null, null);
    });

    expect(result.current.selectedLotteryId).toBeNull();
    expect(result.current.selectedLotteryCode).toBeNull();
  });

  it("loadLotteries fetches and stores lottery list", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: [
          { id: 1, code: "L1", name: "Lottery 1", country: "AR" },
          { id: 2, code: "L2", name: "Lottery 2", country: "CL" },
        ],
        timestamp: "",
      }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useLotteryStore());

    await act(async () => {
      await result.current.loadLotteries();
    });

    expect(result.current.lotteries).toHaveLength(2);
    expect(result.current.lotteries[0]?.code).toBe("L1");
    expect(result.current.isLoading).toBe(false);
    vi.restoreAllMocks();
  });

  it("loadLotteries sets error on failure", async () => {
    const mockFetch = vi.fn().mockRejectedValue(new Error("Network error"));
    vi.stubGlobal("fetch", mockFetch);

    const { result } = renderHook(() => useLotteryStore());

    await act(async () => {
      await result.current.loadLotteries();
    });

    expect(result.current.error).toBe("Network error");
    expect(result.current.isLoading).toBe(false);
    vi.restoreAllMocks();
  });

  it("persists selectedLotteryId and selectedLotteryCode to localStorage", () => {
    const { result } = renderHook(() => useLotteryStore());

    act(() => {
      result.current.setSelected(3, "L3");
    });

    const stored = JSON.parse(localStorage.getItem("lip:selectedLottery") ?? "{}");
    expect(stored.state.selectedLotteryId).toBe(3);
    expect(stored.state.selectedLotteryCode).toBe("L3");
  });

  it("does not persist lotteries list in localStorage", () => {
    const { result } = renderHook(() => useLotteryStore());

    act(() => {
      result.current.setSelected(1, "L1");
    });

    const stored = JSON.parse(localStorage.getItem("lip:selectedLottery") ?? "{}");
    expect(stored.state.lotteries).toBeUndefined();
  });
});
