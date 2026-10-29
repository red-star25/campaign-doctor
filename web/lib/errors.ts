export class ApiError extends Error {
  readonly status?: number;
  readonly unreachable: boolean;

  constructor(message: string, options?: { status?: number; unreachable?: boolean }) {
    super(message);
    this.name = "ApiError";
    this.status = options?.status;
    this.unreachable = options?.unreachable ?? false;
  }
}

export function asApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof Error && error.message) return new ApiError(error.message);
  return new ApiError("Something went wrong while talking to the API.");
}
