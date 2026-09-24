import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { authGuard } from './auth.guard';
import { AuthService } from './auth.service';
import { AuthUser } from './auth.models';

@Component({ template: 'login' })
class LoginStubComponent {}

@Component({ template: 'dashboard' })
class DashboardStubComponent {}

describe('authGuard', () => {
  async function setup(user: AuthUser | null) {
    const authService = {
      ensureSession: () => of(user),
    };

    TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: 'login', component: LoginStubComponent },
          { path: 'dashboard', component: DashboardStubComponent, canActivate: [authGuard] },
        ]),
        { provide: AuthService, useValue: authService },
      ],
    });

    return TestBed.inject(Router);
  }

  it('allows authenticated users to reach the dashboard', async () => {
    const router = await setup({
      id: '1',
      email: 'user@example.com',
      full_name: 'Example User',
    });

    await router.navigateByUrl('/dashboard');
    expect(router.url).toBe('/dashboard');
  });

  it('redirects unauthenticated users to login', async () => {
    const router = await setup(null);

    await router.navigateByUrl('/dashboard');
    expect(router.url).toBe('/login');
  });
});
