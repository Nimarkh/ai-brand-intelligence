import { Component, computed, inject, input } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

export type IconName =
  | 'dashboard'
  | 'brands'
  | 'audits'
  | 'visibility'
  | 'query'
  | 'entity'
  | 'recommendations'
  | 'reports'
  | 'chat'
  | 'settings'
  | 'menu'
  | 'close'
  | 'sun'
  | 'moon'
  | 'bell'
  | 'panel'
  | 'alert'
  | 'trend-up'
  | 'trend-down'
  | 'inbox'
  | 'user';

const ICON_PATHS: Record<IconName, string> = {
  dashboard:
    '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  brands:
    '<path d="M4 20V6.5A1.5 1.5 0 0 1 5.5 5h7A1.5 1.5 0 0 1 14 6.5V20"/><path d="M14 9.5h4.5A1.5 1.5 0 0 1 20 11V20"/><path d="M3 20h18"/><path d="M7.5 8.5h2M7.5 12h2M7.5 15.5h2"/>',
  audits: '<rect x="6" y="3.5" width="12" height="17" rx="2"/><path d="M9 3.5h6V6H9z"/><path d="M9 11h6M9 15h4"/>',
  visibility:
    '<path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.5"/>',
  query: '<circle cx="11" cy="11" r="6"/><path d="M16 16.5 20 20.5"/>',
  entity:
    '<circle cx="6" cy="7" r="2.2"/><circle cx="17.5" cy="6.5" r="2.2"/><circle cx="12" cy="17" r="2.2"/><path d="M8 8.3 10.4 15M15.5 8.2 13.3 15"/>',
  recommendations:
    '<path d="M9 7h10M9 12h10M9 17h10"/><path d="m4.5 7 1.2 1.2L8 5.9M4.5 12l1.2 1.2L8 10.9M4.5 17l1.2 1.2L8 15.9"/>',
  reports:
    '<path d="M7 3.5h6.5L19 9v11a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 6 20V5A1.5 1.5 0 0 1 7.5 3.5z"/><path d="M13.5 3.8V9H19"/><path d="M8.5 13h7M8.5 16.5h4.5"/>',
  chat: '<path d="M6.5 17.5 4 20V6.8A1.8 1.8 0 0 1 5.8 5h12.4A1.8 1.8 0 0 1 20 6.8v8.9a1.8 1.8 0 0 1-1.8 1.8z"/>',
  settings:
    '<circle cx="12" cy="12" r="3"/><path d="M12 3v2.2M12 18.8V21M4.9 4.9l1.6 1.6M17.5 17.5l1.6 1.6M3 12h2.2M18.8 12H21M4.9 19.1l1.6-1.6M17.5 6.5l1.6-1.6"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  sun: '<circle cx="12" cy="12" r="3.25"/><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M5.4 5.4l1.4 1.4M17.2 17.2l1.4 1.4M18.6 5.4l-1.4 1.4M6.8 17.2l-1.4 1.4"/>',
  moon: '<path d="M15.5 3.6A7.8 7.8 0 1 0 20.4 15 6.2 6.2 0 0 1 15.5 3.6z"/>',
  bell: '<path d="M6 16.2V11a6 6 0 1 1 12 0v5.2l1.2 1.8H4.8z"/><path d="M10 19.2a2 2 0 0 0 4 0"/>',
  panel: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9 4.5v15"/>',
  alert: '<circle cx="12" cy="12" r="8.25"/><path d="M12 8v4.5"/><path d="M12 16h.01"/>',
  'trend-up': '<path d="m4 16 5.2-5.2 3.1 3.1L20 7"/><path d="M14.5 7H20v5.5"/>',
  'trend-down': '<path d="m4 8 5.2 5.2 3.1-3.1L20 17"/><path d="M14.5 17H20v-5.5"/>',
  inbox: '<path d="M4 13.5 6.2 5.8A1.5 1.5 0 0 1 7.6 4.8h8.8a1.5 1.5 0 0 1 1.4 1l2.2 7.7"/><path d="M4 13.5h4.2l1.2 2h5.2l1.2-2H20V18a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18z"/>',
  user: '<circle cx="12" cy="8" r="3"/><path d="M5.5 19.2a6.5 6.5 0 0 1 13 0"/>',
};

function iconSvg(path: string): string {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
}

@Component({
  selector: 'app-icon',
  template: `<span class="icon" [style.width.px]="size()" [style.height.px]="size()" [innerHTML]="markup()"></span>`,
})
export class IconComponent {
  private readonly sanitizer = inject(DomSanitizer);

  readonly name = input.required<IconName>();
  readonly size = input(18);
  readonly markup = computed<SafeHtml>(() =>
    this.sanitizer.bypassSecurityTrustHtml(iconSvg(ICON_PATHS[this.name()])),
  );
}
