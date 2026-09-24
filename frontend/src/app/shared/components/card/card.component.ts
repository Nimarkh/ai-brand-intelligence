import { Component, input } from '@angular/core';

@Component({
  selector: 'app-card',
  host: {
    class: 'card',
    '[class.card--interactive]': 'interactive()',
  },
  template: '<ng-content />',
})
export class CardComponent {
  readonly interactive = input(false);
}
