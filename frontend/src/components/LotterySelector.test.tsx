import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";
import { useLotteryStore } from "../store/useLotteryStore";
import type { Lottery } from "../types/lottery";
import LotterySelector from "./LotterySelector";

const lotteries: Lottery[] = [
  {
    id: 1,
    code: "L1",
    name: "Quini 6",
    country: "AR",
    description: null,
    min_number: 0,
    max_number: 45,
    numbers_to_select: 6,
    super_number_min: null,
    super_number_max: null,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    code: "L2",
    name: "Loto",
    country: "AR",
    description: null,
    min_number: 0,
    max_number: 36,
    numbers_to_select: 6,
    super_number_min: null,
    super_number_max: null,
    created_at: "2026-01-01T00:00:00Z",
  },
];

const server = setupServer(
  http.get("*/api/v1/lotteries", () =>
    HttpResponse.json({
      success: true,
      data: lotteries,
      timestamp: "2026-01-01T00:00:00Z",
    })
  )
);

beforeAll(() => server.listen());

afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
  useLotteryStore.setState({
    lotteries: [],
    selectedLotteryId: null,
    selectedLotteryCode: null,
    isLoading: false,
    error: null,
  });
});

afterAll(() => server.close());

describe("LotterySelector", () => {
  it("loads lotteries from GET /lotteries on mount", async () => {
    render(<LotterySelector />);

    const option = await screen.findByRole("option", { name: /Quini 6/ });
    expect(option).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Loto/ })).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(3);
  });

  it("shows a loading indicator while the request is pending", async () => {
    server.use(
      http.get("*/api/v1/lotteries", async () => {
        await delay(50);
        return HttpResponse.json({
          success: true,
          data: lotteries,
          timestamp: "2026-01-01T00:00:00Z",
        });
      })
    );

    render(<LotterySelector />);

    expect(screen.getByText(/cargando loter/i)).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: /Quini 6/ })).toBeInTheDocument();
  });

  it("calls setSelected with id and code when an option is chosen", async () => {
    render(<LotterySelector />);

    const select = await screen.findByRole("combobox", { name: /lotería/i });
    fireEvent.change(select, { target: { value: "2" } });

    await waitFor(() => {
      expect(useLotteryStore.getState().selectedLotteryId).toBe(2);
      expect(useLotteryStore.getState().selectedLotteryCode).toBe("L2");
    });
  });

  it("shows an error state with retry when the request fails", async () => {
    server.use(
      http.get("*/api/v1/lotteries", () =>
        HttpResponse.json(
          {
            success: false,
            error: { code: "INTERNAL_ERROR", message: "Server error" },
            timestamp: "",
          },
          { status: 500 }
        )
      )
    );

    render(<LotterySelector />);

    expect(await screen.findByText(/no se pudieron cargar las loter/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reintentar/i })).toBeInTheDocument();
  });

  it("retries loading lotteries when the retry button is clicked", async () => {
    server.use(
      http.get("*/api/v1/lotteries", () =>
        HttpResponse.json(
          {
            success: false,
            error: { code: "INTERNAL_ERROR", message: "Server error" },
            timestamp: "",
          },
          { status: 500 }
        )
      )
    );

    render(<LotterySelector />);
    await screen.findByText(/no se pudieron cargar las loter/i);

    server.use(
      http.get("*/api/v1/lotteries", () =>
        HttpResponse.json({
          success: true,
          data: lotteries,
          timestamp: "2026-01-01T00:00:00Z",
        })
      )
    );
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    expect(await screen.findByRole("option", { name: /Quini 6/ })).toBeInTheDocument();
  });

  it("renders a disabled empty select when no lotteries exist", async () => {
    server.use(
      http.get("*/api/v1/lotteries", () =>
        HttpResponse.json({
          success: true,
          data: [],
          timestamp: "2026-01-01T00:00:00Z",
        })
      )
    );

    render(<LotterySelector />);

    const select = await screen.findByRole("combobox", { name: /lotería/i });
    expect(select).toBeDisabled();
    expect(screen.getByRole("option", { name: /no hay loterías disponibles/i })).toBeInTheDocument();
  });
});
