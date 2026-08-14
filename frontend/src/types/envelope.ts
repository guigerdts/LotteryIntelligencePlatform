/** Standard success envelope: {success, data, timestamp}. */
export interface Envelope<T> {
  success: true;
  data: T;
  timestamp: string;
}

/** Standard error envelope: {success, error, timestamp}. */
export interface ErrorEnvelope {
  success: false;
  error: { code: string; message: string };
  timestamp: string;
}

/** Union type for any API response. */
export type ApiResponse<T> = Envelope<T> | ErrorEnvelope;
