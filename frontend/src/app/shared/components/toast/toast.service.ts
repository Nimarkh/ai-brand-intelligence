import { Injectable, signal } from '@angular/core';

export type ToastTone = 'success' | 'error' | 'warning' | 'info';

export interface ToastMessage {
  id: number;
  tone: ToastTone;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class ToastService {
  private readonly toastState = signal<readonly ToastMessage[]>([]);
  private nextId = 0;

  readonly toasts = this.toastState.asReadonly();

  show(tone: ToastTone, message: string): void {
    const id = ++this.nextId;
    this.toastState.update((current) => [...current, { id, tone, message }]);
    window.setTimeout(() => this.dismiss(id), 4000);
  }

  dismiss(id: number): void {
    this.toastState.update((current) => current.filter((toast) => toast.id !== id));
  }
}
