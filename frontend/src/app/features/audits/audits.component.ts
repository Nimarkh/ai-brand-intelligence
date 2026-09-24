import { Component } from '@angular/core';

import { ComingSoonComponent } from '../../shared/components/coming-soon/coming-soon.component';

@Component({
  selector: 'app-audits',
  imports: [ComingSoonComponent],
  template: `
    <app-coming-soon
      title="Audits"
      description="Review audit history and status."
    />
  `,
})
export class AuditsComponent {}
