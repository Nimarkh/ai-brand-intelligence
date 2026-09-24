import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of } from 'rxjs';

import { routes } from './app.routes';
import { authGuard } from './core/auth/auth.guard';
import { AuthService } from './core/auth/auth.service';
import { AuthUser } from './core/auth/auth.models';
import { LoginComponent } from './features/auth/login/login.component';
import { RegisterComponent } from './features/auth/register/register.component';
import { ShellComponent } from './layout/shell/shell.component';

const user: AuthUser = {
  id: '1',
  email: 'ada@example.com',
  full_name: 'Ada Lovelace',
};

const placeholderPaths = ['/website-audit'];

describe('application routes', () => {
  const shell = routes.find((route) => route.component === ShellComponent);

  it('keeps login and register outside the application shell', () => {
    expect(routes.find((route) => route.path === 'login')?.component).toBe(LoginComponent);
    expect(routes.find((route) => route.path === 'register')?.component).toBe(RegisterComponent);
    expect(shell?.children?.some((route) => route.path === 'login')).toBeFalse();
  });

  it('protects the application shell and registers future pages', () => {
    expect(shell?.canActivate).toContain(authGuard);
    const paths = shell?.children?.map((route) => route.path) ?? [];
    expect(paths).toEqual(
      jasmine.arrayContaining([
        'dashboard',
        'brands',
        'brands/new',
        'brands/:id',
        'brands/:id/edit',
        'audits',
        'audits/:id',
        'website-audit',
        'ai-visibility',
        'query-explorer',
        'entity',
        'recommendations',
        'reports',
        'reports/:id',
        'intelligence-chat',
        'settings',
      ]),
    );
  });

  it('redirects unauthenticated visitors away from protected pages', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        {
          provide: AuthService,
          useValue: {
            ensureSession: () => of(null),
            currentUser: signal(null),
          },
        },
      ],
    });

    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/reports');

    expect(TestBed.inject(Router).url).toBe('/login');
    const root = harness.fixture.nativeElement as HTMLElement;
    expect(root.querySelector('app-sidebar')).toBeNull();
    expect(root.textContent).toContain('Sign in');
  });

  it('renders future routes as placeholders inside the shell', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        {
          provide: AuthService,
          useValue: {
            ensureSession: () => of(user),
            currentUser: signal(user),
            logout: () => of({ status: 'ok' }),
          },
        },
      ],
    });

    const harness = await RouterTestingHarness.create('/website-audit');

    for (const path of placeholderPaths) {
      await harness.navigateByUrl(path);
      expect(harness.fixture.nativeElement.textContent).toContain('Coming in a future phase');
    }
  });

  it('keeps /brands/new ahead of the brand id route and protects brand pages', async () => {
    const paths = shell?.children?.map((route) => route.path) ?? [];
    const newIndex = paths.indexOf('brands/new');
    const editIndex = paths.indexOf('brands/:id/edit');
    const detailIndex = paths.indexOf('brands/:id');
    expect(newIndex).toBeGreaterThan(-1);
    expect(editIndex).toBeGreaterThan(newIndex);
    expect(detailIndex).toBeGreaterThan(editIndex);

    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        {
          provide: AuthService,
          useValue: {
            ensureSession: () => of(null),
            currentUser: signal(null),
          },
        },
      ],
    });

    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/brands/new');
    expect(TestBed.inject(Router).url).toBe('/login');

    await harness.navigateByUrl('/brands/11111111-1111-4111-8111-111111111111');
    expect(TestBed.inject(Router).url).toBe('/login');
  });
});
