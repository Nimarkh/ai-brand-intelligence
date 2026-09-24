import { Component } from '@angular/core';

import { ComingSoonComponent } from '../../shared/components/coming-soon/coming-soon.component';

@Component({
  selector: 'app-recommendations',
  imports: [ComingSoonComponent],
  template: `
    <app-coming-soon
      title="Recommendations"
      description="Review prioritized actions for each brand."
    />
  `,
})
export class RecommendationsComponent {}
