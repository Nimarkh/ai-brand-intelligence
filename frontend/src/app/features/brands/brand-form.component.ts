import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { combineLatest } from 'rxjs';

import { ButtonComponent } from '../../shared/components/button/button.component';
import { CardComponent } from '../../shared/components/card/card.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { InputComponent } from '../../shared/components/input/input.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { TextareaComponent } from '../../shared/components/textarea/textarea.component';
import { ToastService } from '../../shared/components/toast/toast.service';
import { apiErrorMessage } from './api-error';
import { BrandWritePayload } from './brand.models';
import { BrandService } from './brand.service';

type FormStatus = 'editing' | 'loading' | 'not-found' | 'error';

function trimmedRequired(control: AbstractControl): ValidationErrors | null {
  return String(control.value ?? '').trim() ? null : { required: true };
}

function httpUrl(control: AbstractControl): ValidationErrors | null {
  const candidate = String(control.value ?? '').trim();
  if (!candidate) {
    return { required: true };
  }
  if (candidate.length > 2048 || /\s/.test(candidate)) {
    return { url: true };
  }
  try {
    const parsed = new URL(candidate);
    if ((parsed.protocol === 'http:' || parsed.protocol === 'https:') && parsed.hostname.length > 0) {
      return null;
    }
  } catch {
    return { url: true };
  }
  return { url: true };
}

@Component({
  selector: 'app-brand-form',
  imports: [
    ReactiveFormsModule,
    PageHeaderComponent,
    CardComponent,
    InputComponent,
    TextareaComponent,
    ButtonComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: './brand-form.component.html',
})
export class BrandFormComponent {
  private readonly brandsApi = inject(BrandService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly formBuilder = inject(FormBuilder);
  private readonly toast = inject(ToastService);
  private readonly destroyRef = inject(DestroyRef);
  private loadedId: string | null = null;

  readonly status = signal<FormStatus>('editing');
  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly brandId = signal<string | null>(null);
  readonly mode = signal<'create' | 'edit'>('create');

  readonly form = this.formBuilder.nonNullable.group({
    name: ['', [trimmedRequired, Validators.maxLength(255)]],
    website_url: ['', [httpUrl, Validators.maxLength(2048)]],
    industry: ['', [trimmedRequired, Validators.maxLength(255)]],
    country: ['', [trimmedRequired, Validators.maxLength(255)]],
    target_market: ['', [trimmedRequired, Validators.maxLength(255)]],
    description: ['', [Validators.maxLength(5000)]],
  });

  constructor() {
    combineLatest([this.route.data, this.route.paramMap])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(([data, params]) => {
        const mode = data['mode'] === 'edit' ? 'edit' : 'create';
        this.mode.set(mode);
        if (mode !== 'edit') {
          this.brandId.set(null);
          this.status.set('editing');
          return;
        }
        const id = params.get('id');
        if (!id) {
          this.status.set('not-found');
          return;
        }
        this.load(id);
      });
  }

  get submitDisabled(): boolean {
    return this.form.invalid || this.submitting();
  }

  fieldError(name: 'name' | 'website_url' | 'industry' | 'country' | 'target_market' | 'description'): string | null {
    const control = this.form.controls[name];
    if (!control.touched || control.valid) {
      return null;
    }
    if (name === 'description') {
      return 'Description must be 5,000 characters or fewer.';
    }
    if (control.hasError('maxlength')) {
      return name === 'website_url'
        ? 'Website URL must be 2,048 characters or fewer.'
        : 'Use 255 characters or fewer.';
    }
    if (name === 'website_url') {
      return 'Enter a valid http or https URL.';
    }
    if (name === 'name') {
      return 'Enter a brand name.';
    }
    if (name === 'industry') {
      return 'Enter an industry.';
    }
    if (name === 'country') {
      return 'Enter a country.';
    }
    return 'Enter a target market.';
  }

  onSubmit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.submitting()) {
      return;
    }

    const payload = this.payload();
    this.submitting.set(true);
    this.errorMessage.set(null);
    const id = this.brandId();
    const request =
      this.mode() === 'edit' && id
        ? this.brandsApi.updateBrand(id, payload)
        : this.brandsApi.createBrand(payload);

    request.subscribe({
      next: (brand) => {
        this.toast.show('success', this.mode() === 'edit' ? 'Brand updated.' : 'Brand created.');
        void this.router.navigate(['/brands', brand.id]);
      },
      error: (error: HttpErrorResponse) => {
        this.submitting.set(false);
        if (error.status === 401) {
          void this.router.navigate(['/login']);
          return;
        }
        if (error.status === 404) {
          this.status.set('not-found');
          return;
        }
        this.errorMessage.set(apiErrorMessage(error, 'Could not save this brand. Please try again.'));
      },
    });
  }

  backToBrands(): void {
    void this.router.navigate(['/brands']);
  }

  cancel(): void {
    const id = this.brandId();
    if (this.mode() === 'edit' && id) {
      void this.router.navigate(['/brands', id]);
      return;
    }
    void this.router.navigate(['/brands']);
  }

  private load(id: string): void {
    if (this.loadedId === id) {
      return;
    }
    this.loadedId = id;
    this.brandId.set(id);
    this.status.set('loading');
    this.errorMessage.set(null);
    this.brandsApi.getBrand(id).subscribe({
      next: (brand) => {
        this.form.reset({
          name: brand.name,
          website_url: brand.website_url ?? '',
          industry: brand.industry ?? '',
          country: brand.country ?? '',
          target_market: brand.target_market ?? '',
          description: brand.description ?? '',
        });
        this.status.set('editing');
      },
      error: (error: HttpErrorResponse) => {
        this.loadedId = null;
        if (error.status === 401) {
          void this.router.navigate(['/login']);
          return;
        }
        if (error.status === 404 || error.status === 422) {
          this.status.set('not-found');
          return;
        }
        this.errorMessage.set(apiErrorMessage(error, 'Could not load this brand.'));
        this.status.set('error');
      },
    });
  }

  private payload(): BrandWritePayload {
    const value = this.form.getRawValue();
    const description = value.description.trim();
    return {
      name: value.name.trim(),
      website_url: value.website_url.trim(),
      industry: value.industry.trim(),
      country: value.country.trim(),
      target_market: value.target_market.trim(),
      description: description ? description : null,
    };
  }
}
