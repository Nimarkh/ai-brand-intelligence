import { Component, input } from '@angular/core';

@Component({
  selector: 'app-mark',
  template: `
    <svg [attr.width]="size()" [attr.height]="size()" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="1" y="1" width="22" height="22" rx="6" fill="currentColor" opacity="0.16" />
      <path d="M7 16V9.2M12 16V6.5M17 16v-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </svg>
  `,
})
export class MarkComponent {
  readonly size = input(28);
}
