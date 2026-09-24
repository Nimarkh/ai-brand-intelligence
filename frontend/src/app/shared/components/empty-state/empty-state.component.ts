import { Component, input } from '@angular/core';

import { IconComponent, IconName } from '../icon/icon.component';

@Component({
  selector: 'app-empty-state',
  imports: [IconComponent],
  host: {
    class: 'empty',
    '[class.empty--compact]': 'compact()',
  },
  template: `
    <span class="empty__icon">
      <app-icon [name]="icon()" [size]="18" />
    </span>
    @if (headingLevel() === 3) {
      <h3 class="empty__title">{{ title() }}</h3>
    } @else {
      <h2 class="empty__title">{{ title() }}</h2>
    }
    <p>{{ description() }}</p>
    <div class="empty__actions">
      <ng-content />
    </div>
  `,
})
export class EmptyStateComponent {
  readonly title = input.required<string>();
  readonly description = input.required<string>();
  readonly icon = input<IconName>('inbox');
  readonly compact = input(false);
  /** Use 3 when nested under an existing section heading. */
  readonly headingLevel = input<2 | 3>(2);
}
