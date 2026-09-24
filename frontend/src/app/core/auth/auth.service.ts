import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, TimeoutError, catchError, of, tap, throwError, timeout } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthUser, LoginRequest, RegisterRequest } from './auth.models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;
  private readonly currentUserState = signal<AuthUser | null>(null);
  private sessionLoaded = false;

  readonly currentUser = this.currentUserState.asReadonly();
  readonly isAuthenticated = computed(() => this.currentUserState() !== null);

  acceptSession(user: AuthUser): void {
    this.currentUserState.set(user);
    this.sessionLoaded = true;
  }

  clearSession(): void {
    this.currentUserState.set(null);
    this.sessionLoaded = true;
  }

  register(payload: RegisterRequest): Observable<AuthUser> {
    return this.http.post<AuthUser>(`${this.apiBaseUrl}/auth/register`, payload);
  }

  login(payload: LoginRequest): Observable<AuthUser> {
    return this.http.post<AuthUser>(`${this.apiBaseUrl}/auth/login`, payload).pipe(
      timeout({ first: 10_000 }),
      tap((user) => this.acceptSession(user)),
      catchError((error: unknown) => {
        if (error instanceof TimeoutError) {
          return throwError(
            () =>
              new HttpErrorResponse({
                status: 0,
                statusText: 'Timeout',
                url: `${this.apiBaseUrl}/auth/login`,
                error: { detail: 'Sign-in timed out. Please try again.' },
              }),
          );
        }
        return throwError(() => error);
      }),
    );
  }

  logout(): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${this.apiBaseUrl}/auth/logout`, {}).pipe(
      tap(() => this.clearSession()),
    );
  }

  getCurrentUser(): Observable<AuthUser> {
    return this.http.get<AuthUser>(`${this.apiBaseUrl}/auth/me`).pipe(
      timeout({ first: 5_000 }),
      tap((user) => this.acceptSession(user)),
    );
  }

  ensureSession(): Observable<AuthUser | null> {
    if (this.sessionLoaded) {
      return of(this.currentUserState());
    }

    return this.getCurrentUser().pipe(
      catchError(() => {
        this.sessionLoaded = true;
        return of(this.currentUserState());
      }),
    );
  }
}
