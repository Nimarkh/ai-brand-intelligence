import { HttpErrorResponse } from '@angular/common/http';

export function apiErrorMessage(error: HttpErrorResponse, fallback: string): string {
  if (error.status === 401) {
    return 'Your session has expired. Sign in again.';
  }
  if (error.status === 404) {
    return 'Brand not found.';
  }
  if (error.status === 0 || error.status >= 500) {
    return 'Something went wrong. Please try again.';
  }

  const detail: unknown = error.error?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: unknown) => {
        if (item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string') {
          return item.msg;
        }
        return '';
      })
      .filter((message) => message.length > 0);
    if (messages.length > 0) {
      return messages.join(' ');
    }
  }
  return fallback;
}
