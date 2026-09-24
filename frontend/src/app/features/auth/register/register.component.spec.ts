import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import { AuthService } from '../../../core/auth/auth.service';
import { RegisterComponent } from './register.component';

describe('RegisterComponent', () => {
  let fixture: ComponentFixture<RegisterComponent>;
  let authService: jasmine.SpyObj<AuthService>;
  let router: Router;

  beforeEach(async () => {
    authService = jasmine.createSpyObj('AuthService', ['register']);

    await TestBed.configureTestingModule({
      imports: [RegisterComponent],
      providers: [
        provideRouter([{ path: 'login', children: [] }]),
        { provide: AuthService, useValue: authService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(RegisterComponent);
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  it('disables submit until the form is valid', () => {
    const button = fixture.nativeElement.querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(button.disabled).toBeTrue();

    fixture.componentInstance.form.setValue({
      full_name: 'Example User',
      email: 'user@example.com',
      password: 'password123',
    });
    fixture.detectChanges();
    expect(button.disabled).toBeFalse();
  });

  it('shows an API error after a failed registration', () => {
    authService.register.and.returnValue(
      throwError(() => ({ error: { detail: 'An account with this email already exists.' } })),
    );

    fixture.componentInstance.form.setValue({
      full_name: 'Example User',
      email: 'user@example.com',
      password: 'password123',
    });
    fixture.componentInstance.onSubmit();
    fixture.detectChanges();

    expect(authService.register).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('An account with this email already exists.');
    expect(fixture.componentInstance.submitting()).toBeFalse();
  });

  it('navigates to login on success', () => {
    const navigateSpy = spyOn(router, 'navigate');
    authService.register.and.returnValue(
      of({ id: '1', email: 'user@example.com', full_name: 'Example User' }),
    );

    fixture.componentInstance.form.setValue({
      full_name: 'Example User',
      email: 'user@example.com',
      password: 'password123',
    });
    fixture.componentInstance.onSubmit();

    expect(navigateSpy).toHaveBeenCalledWith(['/login']);
  });
});
