import { Component, DestroyRef, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { AuthService } from '../../core/auth/auth.service';
import { Theme, ThemeService } from '../../core/theme/theme.service';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { CardComponent } from '../../shared/components/card/card.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { InputComponent } from '../../shared/components/input/input.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { SelectComponent, SelectOption } from '../../shared/components/select/select.component';
import { TabsComponent, TabItem } from '../../shared/components/tabs/tabs.component';
import { ToastService } from '../../shared/components/toast/toast.service';

@Component({
  selector: 'app-settings',
  imports: [
    ReactiveFormsModule,
    PageHeaderComponent,
    TabsComponent,
    CardComponent,
    BadgeComponent,
    InputComponent,
    SelectComponent,
    EmptyStateComponent,
  ],
  templateUrl: './settings.component.html',
})
export class SettingsComponent {
  private readonly auth = inject(AuthService);
  private readonly themeService = inject(ThemeService);
  private readonly toast = inject(ToastService);
  private readonly formBuilder = inject(FormBuilder);
  private readonly destroyRef = inject(DestroyRef);

  readonly tabs: readonly TabItem[] = [
    { id: 'profile', label: 'Profile' },
    { id: 'appearance', label: 'Appearance' },
    { id: 'security', label: 'Security' },
  ];

  readonly themeOptions: readonly SelectOption[] = [
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
  ];

  readonly activeTab = signal('profile');
  readonly currentUser = this.auth.currentUser;
  readonly theme = this.themeService.theme;

  readonly profileForm = this.formBuilder.nonNullable.group({
    full_name: '',
    email: '',
  });

  readonly appearanceForm = this.formBuilder.nonNullable.group({
    theme: this.themeService.getTheme(),
  });

  constructor() {
    this.profileForm.disable({ emitEvent: false });

    effect(() => {
      const user = this.currentUser();
      this.profileForm.setValue(
        {
          full_name: user?.full_name?.trim() || user?.email || '',
          email: user?.email ?? '',
        },
        { emitEvent: false },
      );
    });

    effect(() => {
      const theme = this.themeService.theme();
      if (this.appearanceForm.controls.theme.value !== theme) {
        this.appearanceForm.controls.theme.setValue(theme, { emitEvent: false });
      }
    });

    this.appearanceForm.controls.theme.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => {
        if (value !== this.themeService.getTheme()) {
          this.themeService.setTheme(value);
          this.toast.show('info', value === 'dark' ? 'Dark mode enabled.' : 'Light mode enabled.');
        }
      });
  }

  themeLabel(theme: Theme): string {
    return theme === 'dark' ? 'Dark' : 'Light';
  }
}
