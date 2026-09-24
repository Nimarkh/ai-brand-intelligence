import { Component, computed, input } from '@angular/core';

import { formatScoreOutOf100 } from '../../format';

@Component({
  selector: 'app-score',
  host: { class: 'score' },
  template: `
    @if (loading()) {
      <span class="score__loading" aria-hidden="true"></span>
      <span class="visually-hidden">Loading score</span>
    } @else if (value() === null) {
      <span class="score__empty">{{ emptyLabel() }}</span>
    } @else {
      <span class="score__value">{{ formatted() }}</span>
    }
  `,
})
export class ScoreComponent {
  readonly value = input<number | null>(null);
  readonly loading = input(false);
  readonly emptyLabel = input('—');

  readonly formatted = computed(() => formatScore(this.value()));
}

export function formatScore(value: number | null): string {
  return formatScoreOutOf100(value);
}
