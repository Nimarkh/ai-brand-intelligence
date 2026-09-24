import { Component } from '@angular/core';

import { ComingSoonComponent } from '../../shared/components/coming-soon/coming-soon.component';

@Component({
  selector: 'app-entity',
  imports: [ComingSoonComponent],
  template: `
    <app-coming-soon
      title="Entity Intelligence"
      description="Understand entity strength and semantic consistency."
    />
  `,
})
export class EntityComponent {}
