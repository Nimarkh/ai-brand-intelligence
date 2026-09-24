import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/auth/auth.service';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { ErrorStateComponent } from '../../../shared/components/error-state/error-state.component';
import { InputComponent } from '../../../shared/components/input/input.component';
import { MarkComponent } from '../../../shared/components/mark/mark.component';

@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule, RouterLink, InputComponent, ButtonComponent, ErrorStateComponent, MarkComponent],
  templateUrl: './register.component.html',
})
export class RegisterComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly formBuilder = inject(FormBuilder);

  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly form = this.formBuilder.nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(1)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  get submitDisabled(): boolean {
    return this.form.invalid || this.submitting();
  }

  fieldError(name: 'full_name' | 'email' | 'password', message: string): string | null {
    const control = this.form.controls[name];
    return control.touched && control.invalid ? message : null;
  }

  onSubmit(): void {
    if (this.submitDisabled) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    this.auth.register(this.form.getRawValue()).subscribe({
      next: () => {
        void this.router.navigate(['/login']);
      },
      error: (error: HttpErrorResponse) => {
        this.submitting.set(false);
        this.errorMessage.set(this.readError(error));
      },
    });
  }

  private readError(error: HttpErrorResponse): string {
    const detail = error.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    return 'Unable to create an account. Please try again.';
  }
}
