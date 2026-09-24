import { Component, input } from '@angular/core';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

@Component({
  selector: 'app-badge',
  host: {
    class: 'badge',
    '[class.badge--neutral]': 'tone() === "neutral"',
    '[class.badge--success]': 'tone() === "success"',
    '[class.badge--warning]': 'tone() === "warning"',
    '[class.badge--danger]': 'tone() === "danger"',
    '[class.badge--info]': 'tone() === "info"',
  },
  template: '<ng-content />',
})
export class BadgeComponent {
  readonly tone = input<BadgeTone>('neutral');
}
