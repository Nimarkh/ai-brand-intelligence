import { Component, ElementRef, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { AuthUser } from '../../core/auth/auth.models';

@Component({
  selector: 'app-profile-menu',
  imports: [RouterLink],
  host: {
    class: 'profile',
    '(document:click)': 'onDocumentClick($event)',
    '(document:keydown.escape)': 'close()',
  },
  templateUrl: './profile-menu.component.html',
})
export class ProfileMenuComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly host = inject(ElementRef<HTMLElement>);

  readonly currentUser = this.auth.currentUser;
  readonly open = signal(false);

  toggle(): void {
    this.open.update((value) => !value);
  }

  close(): void {
    this.open.set(false);
  }

  displayName(user: AuthUser): string {
    const name = user.full_name?.trim();
    return name ? name : user.email;
  }

  initials(user: AuthUser): string {
    const name = user.full_name?.trim();
    if (name) {
      const parts = name.split(/\s+/).filter(Boolean);
      const first = parts[0]?.[0] ?? '';
      const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
      return `${first}${last}`.toUpperCase();
    }
    return user.email.slice(0, 1).toUpperCase();
  }

  signOut(): void {
    this.close();
    this.auth.logout().subscribe({
      next: () => {
        void this.router.navigate(['/login']);
      },
      error: () => {
        void this.router.navigate(['/login']);
      },
    });
  }

  onDocumentClick(event: MouseEvent): void {
    if (!this.open()) {
      return;
    }
    if (!this.host.nativeElement.contains(event.target as Node)) {
      this.close();
    }
  }
}
