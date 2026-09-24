import { Component, ElementRef, computed, inject, input } from '@angular/core';

import { LoadingStateComponent } from '../loading-state/loading-state.component';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

@Component({
  selector: 'button[appButton], a[appButton]',
  imports: [LoadingStateComponent],
  host: {
    class: 'btn',
    '[class.btn--primary]': 'variant() === "primary"',
    '[class.btn--secondary]': 'variant() === "secondary"',
    '[class.btn--ghost]': 'variant() === "ghost"',
    '[class.btn--danger]': 'variant() === "danger"',
    '[class.btn--block]': 'block()',
    '[class.btn--loading]': 'loading()',
    '[attr.aria-busy]': 'loading() ? "true" : null',
    '[attr.disabled]': 'nativeDisabled()',
  },
  template: `
    @if (loading()) {
      <app-loading-state variant="inline" [label]="null" />
    }
    <ng-content />
  `,
})
export class ButtonComponent {
  private readonly host = inject(ElementRef<HTMLElement>);

  readonly variant = input<ButtonVariant>('primary');
  readonly loading = input(false);
  readonly disabled = input(false);
  readonly block = input(false);

  /** Signal-based so the host binding stays reactive (getter host binds can stick). */
  readonly nativeDisabled = computed(() => {
    if (this.host.nativeElement.tagName !== 'BUTTON') {
      return null;
    }
    return this.disabled() || this.loading() ? '' : null;
  });
}
