import { Component, inject } from '@angular/core';
import { IsActiveMatchOptions, RouterLink, RouterLinkActive } from '@angular/router';

import { IconComponent } from '../../shared/components/icon/icon.component';
import { MarkComponent } from '../../shared/components/mark/mark.component';
import { NAV_SECTIONS } from './nav.config';
import { SidebarService } from './sidebar.service';

/** Stable references — never allocate new options objects during change detection. */
const EXACT_ACTIVE: IsActiveMatchOptions = {
  paths: 'exact',
  queryParams: 'ignored',
  fragment: 'ignored',
  matrixParams: 'ignored',
};

const SUBSET_ACTIVE: IsActiveMatchOptions = {
  paths: 'subset',
  queryParams: 'ignored',
  fragment: 'ignored',
  matrixParams: 'ignored',
};

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive, IconComponent, MarkComponent],
  templateUrl: './sidebar.component.html',
})
export class SidebarComponent {
  readonly sections = NAV_SECTIONS;
  readonly sidebar = inject(SidebarService);

  linkActiveOptions(item: { exact?: boolean }): IsActiveMatchOptions {
    return item.exact === false ? SUBSET_ACTIVE : EXACT_ACTIVE;
  }
}
