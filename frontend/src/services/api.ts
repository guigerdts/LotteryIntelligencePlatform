import type { ApiResponse } from "../types/envelope";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

/** Base application error with HTTP status code. */
export class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "AppError";
  }
}

/** 404 — resource not found. */
export class NotFoundError extends AppError {
  constructor(message: string, code = "RESOURCE_NOT_FOUND") {
    super(message, code, 404);
    this.name = "NotFoundError";
  }
}

/** 409 — conflict / duplicate. */
export class ConflictError extends AppError {
  constructor(message: string, code = "DUPLICATE_RESOURCE") {
    super(message, code, 409);
    this.name = "ConflictError";
  }
}

/** 422 — validation error. */
export class ValidationError extends AppError {
  constructor(message: string, code = "VALIDATION_ERROR") {
    super(message, code, 422);
    this.name = "ValidationError";
  }
}

/** 500+ — server error. */
export class ServerError extends AppError {
  constructor(message: string, code = "INTERNAL_ERROR") {
    super(message, code, 500);
    this.name = "ServerError";
  }
}

/**
 * Parse an API response into unwrapped data or throw a typed error.
 * Handles both envelope success/error and HTTP status codes.
 */
async function parseResponse<T>(response: Response): Promise<T> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ServerError(
      `Invalid response from server (HTTP ${response.status})`,
    );
  }

  // Error envelope from backend
  if (
    typeof body === "object" &&
    body !== null &&
    "success" in body &&
    (body as { success: boolean }).success === false
  ) {
    const err = body as {
      success: false;
      error: { code: string; message: string };
      timestamp: string;
    };
    const { code, message } = err.error;
    return throwByStatus(response.status, message, code);
  }

  // HTTP error without envelope
  if (!response.ok) {
    const fallbackMessage = `HTTP ${response.status}`;
    return throwByStatus(response.status, fallbackMessage);
  }

  // Success envelope — unwrap data
  const envelope = body as ApiResponse<T>;
  if ("data" in envelope) {
    return envelope.data;
  }

  return body as T;
}

function throwByStatus(status: number, message: string, code?: string): never {
  switch (status) {
    case 404:
      throw new NotFoundError(message, code ?? "RESOURCE_NOT_FOUND");
    case 409:
      throw new ConflictError(message, code ?? "DUPLICATE_RESOURCE");
    case 422:
      throw new ValidationError(message, code ?? "VALIDATION_ERROR");
    default:
      if (status >= 500) {
        throw new ServerError(message, code ?? "INTERNAL_ERROR");
      }
      throw new AppError(message, code ?? "UNKNOWN_ERROR", status);
  }
}

/**
 * Typed HTTP client for the Lottery Intelligence Platform API.
 *
 * Reads VITE_API_BASE_URL from env (defaults to /api/v1).
 * Parses SuccessEnvelope / ErrorEnvelope and maps HTTP errors to typed classes.
 */
export async function apiClient<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });
  return parseResponse<T>(response);
}
