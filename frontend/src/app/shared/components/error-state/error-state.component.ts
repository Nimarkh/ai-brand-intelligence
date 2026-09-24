import { Component, input, output } from '@angular/core';

import { ButtonComponent } from '../button/button.component';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-error-state',
  imports: [ButtonComponent, IconComponent],
  host: {
    class: 'error-state',
    role: 'alert',
  },
  template: `
    <app-icon name="alert" [size]="18" />
    <div class="error-state__copy">
      @if (title()) {
        <p class="error-state__title">{{ title() }}</p>
      }
      <p>{{ message() }}</p>
    </div>
    @if (retryLabel()) {
      <button appButton type="button" variant="secondary" (click)="retry.emit()">{{ retryLabel() }}</button>
    }
  `,
})
export class ErrorStateComponent {
  readonly message = input.required<string>();
  readonly title = input<string | null>(null);
  readonly retryLabel = input<string | null>(null);
  readonly retry = output<void>();
}
