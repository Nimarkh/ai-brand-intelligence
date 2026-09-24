import { HttpErrorResponse } from '@angular/common/http';

/** User-facing API errors. Never surfaces response bodies or stack traces. */
export function pageErrorMessage(error: HttpErrorResponse, fallback: string): string {
  if (error.status === 401) {
    return 'Your session has expired. Sign in again.';
  }
  if (error.status === 404) {
    return 'That audit could not be found.';
  }
  if (error.status === 0 || error.status >= 500) {
    return 'Something went wrong. Please try again.';
  }
  return fallback;
}
