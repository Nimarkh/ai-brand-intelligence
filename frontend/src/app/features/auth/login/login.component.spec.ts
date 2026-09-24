import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { AuthService } from '../../../core/auth/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let authService: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    authService = jasmine.createSpyObj('AuthService', ['login']);

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    fixture.detectChanges();
  });

  it('disables submit until the form is valid', () => {
    const button = fixture.nativeElement.querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(button.disabled).toBeTrue();

    fixture.componentInstance.form.setValue({
      email: 'user@example.com',
      password: 'password123',
    });
    fixture.detectChanges();
    expect(button.disabled).toBeFalse();
  });

  it('shows an API error and re-enables the form after a failed login', () => {
    authService.login.and.returnValue(
      throwError(() => ({ error: { detail: 'Invalid email or password.' } })),
    );

    fixture.componentInstance.form.setValue({
      email: 'user@example.com',
      password: 'password123',
    });
    fixture.componentInstance.onSubmit();
    fixture.detectChanges();

    expect(authService.login).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Invalid email or password.');
    expect(fixture.componentInstance.submitting()).toBeFalse();
  });

  it('hard-redirects on success', () => {
    const redirectSpy = spyOn(fixture.componentInstance, 'redirectToDashboard');
    authService.login.and.returnValue(
      of({ id: '1', email: 'user@example.com', full_name: 'Example User' }),
    );

    fixture.componentInstance.form.setValue({
      email: 'user@example.com',
      password: 'password123',
    });
    fixture.componentInstance.onSubmit();

    expect(redirectSpy).toHaveBeenCalled();
  });

  it('unlocks the form if sign-in hangs', fakeAsync(() => {
    authService.login.and.returnValue(new (class {
      subscribe() {
        // Never emits — simulates a hung request.
      }
    })() as ReturnType<AuthService['login']>);

    fixture.componentInstance.form.setValue({
      email: 'user@example.com',
      password: 'password123',
    });
    fixture.componentInstance.onSubmit();
    expect(fixture.componentInstance.submitting()).toBeTrue();

    tick(12_000);
    fixture.detectChanges();

    expect(fixture.componentInstance.submitting()).toBeFalse();
    expect(fixture.nativeElement.textContent).toContain('Sign-in stuck');
  }));
});
