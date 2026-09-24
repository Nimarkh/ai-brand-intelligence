import { Component } from '@angular/core';

import { ComingSoonComponent } from '../../shared/components/coming-soon/coming-soon.component';

@Component({
  selector: 'app-website-audit',
  imports: [ComingSoonComponent],
  template: `
    <app-coming-soon
      title="Website audit"
      description="Inspect website health and technical signals."
    />
  `,
})
export class WebsiteAuditComponent {}
