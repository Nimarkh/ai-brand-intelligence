import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../../core/auth/auth.service';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';
import { InputComponent } from '../../../shared/components/input/input.component';
import { MarkComponent } from '../../../shared/components/mark/mark.component';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink, InputComponent, ButtonComponent, ErrorStateComponent, MarkComponent],
  templateUrl: './login.component.html',
})
export class LoginComponent implements OnDestroy {
  private readonly auth = inject(AuthService);
  private readonly formBuilder = inject(FormBuilder);
  private failsafeTimer: number | null = null;

  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly form = this.formBuilder.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  ngOnDestroy(): void {
    this.clearFailsafe();
  }

  get submitDisabled(): boolean {
    return this.form.invalid || this.submitting();
  }

  fieldError(name: 'email' | 'password', message: string): string | null {
    const control = this.form.controls[name];
    return control.touched && control.invalid ? message : null;
  }

  onSubmit(event?: Event): void {
    event?.preventDefault();
    event?.stopPropagation();

    if (this.submitDisabled) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);
    this.armFailsafe();

    this.auth.login(this.form.getRawValue()).subscribe({
      next: () => {
        this.clearFailsafe();
        // Full page navigation — avoids SPA guard/login reuse freezes.
        this.redirectToDashboard();
      },
      error: (error: HttpErrorResponse) => {
        this.clearFailsafe();
        this.submitting.set(false);
        this.errorMessage.set(this.readError(error));
      },
    });
  }

  /** Exposed for tests; keeps a hard navigation path after session cookie is set. */
  redirectToDashboard(): void {
    window.location.href = '/dashboard';
  }

  private armFailsafe(): void {
    this.clearFailsafe();
    this.failsafeTimer = window.setTimeout(() => {
      if (!this.submitting()) {
        return;
      }
      this.submitting.set(false);
      this.errorMessage.set('Sign-in stuck. Please try again.');
    }, 12_000);
  }

  private clearFailsafe(): void {
    if (this.failsafeTimer !== null) {
      window.clearTimeout(this.failsafeTimer);
      this.failsafeTimer = null;
    }
  }

  private readError(error: HttpErrorResponse | { error?: { detail?: unknown } }): string {
    const detail = error?.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    return 'Unable to sign in. Please try again.';
  }
}
