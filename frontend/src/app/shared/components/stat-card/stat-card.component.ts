import { Component, input } from '@angular/core';

import { IconComponent, IconName } from '../icon/icon.component';

export type StatTrend = 'up' | 'down' | 'neutral';

@Component({
  selector: 'app-stat-card',
  imports: [IconComponent],
  host: { class: 'stat' },
  template: `
    <div class="stat__top">
      <p class="stat__label">{{ label() }}</p>
      @if (icon(); as iconName) {
        <app-icon [name]="iconName" [size]="16" />
      }
    </div>
    <p class="stat__value">{{ value() }}</p>
    @if (change()) {
      <p class="stat__change" [class.stat__change--up]="trend() === 'up'" [class.stat__change--down]="trend() === 'down'">
        {{ change() }}
      </p>
    }
  `,
})
export class StatCardComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string>();
  readonly change = input<string | null>(null);
  readonly trend = input<StatTrend | null>(null);
  readonly icon = input<IconName | null>(null);
}
