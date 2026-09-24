import { Component, inject } from '@angular/core';

import { IconComponent } from '../icon/icon.component';
import { ToastService } from './toast.service';

@Component({
  selector: 'app-toast-container',
  imports: [IconComponent],
  template: `
    <div class="toasts" aria-live="polite" aria-relevant="additions">
      @for (toast of toastService.toasts(); track toast.id) {
        <div
          class="toast"
          role="status"
          [class.toast--success]="toast.tone === 'success'"
          [class.toast--error]="toast.tone === 'error'"
          [class.toast--warning]="toast.tone === 'warning'"
          [class.toast--info]="toast.tone === 'info'"
        >
          <p>{{ toast.message }}</p>
          <button type="button" class="icon-btn" aria-label="Dismiss notification" (click)="toastService.dismiss(toast.id)">
            <app-icon name="close" [size]="16" />
          </button>
        </div>
      }
    </div>
  `,
})
export class ToastContainerComponent {
  readonly toastService = inject(ToastService);
}
