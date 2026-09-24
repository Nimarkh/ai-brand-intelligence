import { Component, input } from '@angular/core';

import { EmptyStateComponent } from '../empty-state/empty-state.component';
import { PageHeaderComponent } from '../page-header/page-header.component';

@Component({
  selector: 'app-coming-soon',
  imports: [PageHeaderComponent, EmptyStateComponent],
  template: `
    <app-page-header [title]="title()" [description]="description()" />
    <app-empty-state
      title="Coming in a future phase"
      description="This workspace area is reserved for a later release. No analysis runs from this screen."
    />
  `,
})
export class ComingSoonComponent {
  readonly title = input.required<string>();
  readonly description = input.required<string>();
}
