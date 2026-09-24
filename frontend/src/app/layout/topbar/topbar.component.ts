import { Component, inject, signal } from '@angular/core';

import { ThemeService } from '../../core/theme/theme.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import { PageContextService } from '../page-context.service';
import { ProfileMenuComponent } from '../profile-menu/profile-menu.component';
import { SidebarService } from '../sidebar/sidebar.service';
import { ButtonComponent } from '../../shared/components/button/button.component';

@Component({
  selector: 'app-topbar',
  imports: [
    IconComponent,
    ProfileMenuComponent,
    ModalComponent,
    EmptyStateComponent,
    ButtonComponent,
  ],
  templateUrl: './topbar.component.html',
})
export class TopbarComponent {
  readonly sidebar = inject(SidebarService);
  readonly theme = inject(ThemeService);
  readonly page = inject(PageContextService);
  readonly notificationsOpen = signal(false);
}
