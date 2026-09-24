import { Component, input } from '@angular/core';

export type LoadingVariant = 'inline' | 'block' | 'skeleton';

@Component({
  selector: 'app-loading-state',
  host: {
    class: 'loading',
    '[class.loading--inline]': 'variant() === "inline"',
    '[class.loading--block]': 'variant() === "block"',
    '[attr.role]': 'variant() === "inline" ? null : "status"',
    '[attr.aria-hidden]': 'variant() === "inline" ? "true" : null',
    '[attr.aria-label]': 'variant() !== "inline" && label() ? label() : null',
  },
  template: `
    @if (variant() === 'skeleton') {
      <div class="skeleton" aria-hidden="true">
        <span class="skeleton__line skeleton__line--lg"></span>
        <span class="skeleton__line"></span>
        <span class="skeleton__line skeleton__line--sm"></span>
      </div>
      @if (label()) {
        <span class="visually-hidden">{{ label() }}</span>
      }
    } @else {
      <span class="spinner" [class.spinner--inline]="variant() === 'inline'"></span>
      @if (label() && variant() === 'block') {
        <span class="loading__label">{{ label() }}</span>
      }
    }
  `,
})
export class LoadingStateComponent {
  readonly variant = input<LoadingVariant>('block');
  readonly label = input<string | null>('Loading');
}
