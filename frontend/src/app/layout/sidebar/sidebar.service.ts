import { Injectable, signal } from '@angular/core';

export const SIDEBAR_STORAGE_KEY = 'abi.sidebar-collapsed';

@Injectable({ providedIn: 'root' })
export class SidebarService {
  private readonly collapsedState = signal(this.readCollapsed());
  private readonly mobileOpenState = signal(false);

  readonly collapsed = this.collapsedState.asReadonly();
  readonly mobileOpen = this.mobileOpenState.asReadonly();

  isCollapsed(): boolean {
    return this.collapsedState();
  }

  setCollapsed(collapsed: boolean): void {
    this.collapsedState.set(collapsed);
    this.persist(collapsed);
  }

  toggleCollapsed(): void {
    this.setCollapsed(!this.collapsedState());
  }

  openMobile(): void {
    this.mobileOpenState.set(true);
  }

  closeMobile(): void {
    this.mobileOpenState.set(false);
  }

  toggleMobile(): void {
    this.mobileOpenState.update((open) => !open);
  }

  private persist(collapsed: boolean): void {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
    } catch {
      // Preference cannot be stored in this browser context.
    }
  }

  private readCollapsed(): boolean {
    try {
      return localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  }
}
