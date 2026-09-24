import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    httpTesting = TestBed.inject(HttpTestingController);
    spyOn(localStorage, 'setItem');
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('registers without storing a token in localStorage', () => {
    const user = { id: '1', email: 'user@example.com', full_name: 'Example User' };

    service.register({
      email: 'user@example.com',
      password: 'password123',
      full_name: 'Example User',
    }).subscribe((result) => {
      expect(result).toEqual(user);
    });

    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/auth/register`);
    expect(request.request.method).toBe('POST');
    request.flush(user);
    expect(localStorage.setItem).not.toHaveBeenCalled();
    expect(service.isAuthenticated()).toBeFalse();
  });

  it('logs in, keeps the user in memory, and does not store a JWT', () => {
    const user = { id: '1', email: 'user@example.com', full_name: 'Example User' };

    service.login({ email: 'user@example.com', password: 'password123' }).subscribe();

    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/auth/login`);
    expect(request.request.method).toBe('POST');
    request.flush(user);

    expect(service.isAuthenticated()).toBeTrue();
    expect(service.currentUser()).toEqual(user);
    expect(localStorage.setItem).not.toHaveBeenCalled();
  });

  it('times out a hung login request', fakeAsync(() => {
    let failed = false;
    service.login({ email: 'user@example.com', password: 'password123' }).subscribe({
      error: () => {
        failed = true;
      },
    });

    httpTesting.expectOne(`${environment.apiBaseUrl}/auth/login`);
    tick(10_000);
    expect(failed).toBeTrue();
  }));

  it('loads the current user from the session endpoint', () => {
    const user = { id: '1', email: 'user@example.com', full_name: 'Example User' };

    service.getCurrentUser().subscribe();

    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/auth/me`);
    expect(request.request.method).toBe('GET');
    request.flush(user);
    expect(service.isAuthenticated()).toBeTrue();
  });

  it('treats a 401 from /me as unauthenticated', () => {
    service.ensureSession().subscribe((user) => {
      expect(user).toBeNull();
    });

    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/auth/me`);
    request.flush({ detail: 'Not authenticated' }, { status: 401, statusText: 'Unauthorized' });
    expect(service.isAuthenticated()).toBeFalse();
  });

  it('clears in-memory auth state on logout', () => {
    service.login({ email: 'user@example.com', password: 'password123' }).subscribe();
    httpTesting.expectOne(`${environment.apiBaseUrl}/auth/login`).flush({
      id: '1',
      email: 'user@example.com',
      full_name: 'Example User',
    });

    service.logout().subscribe();
    httpTesting.expectOne(`${environment.apiBaseUrl}/auth/logout`).flush({ status: 'ok' });
    expect(service.isAuthenticated()).toBeFalse();
  });
});
