import { Component } from '@angular/core';

import { ComingSoonComponent } from '../../shared/components/coming-soon/coming-soon.component';

@Component({
  selector: 'app-ai-visibility',
  imports: [ComingSoonComponent],
  template: `
    <app-coming-soon
      title="AI Visibility"
      description="See how AI systems surface your brand."
    />
  `,
})
export class AiVisibilityComponent {}
