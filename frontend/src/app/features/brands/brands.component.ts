import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { apiErrorMessage } from './api-error';
import { Brand, formatBrandDate } from './brand.models';
import { BrandService } from './brand.service';

type PageStatus = 'loading' | 'ready' | 'error';

@Component({
  selector: 'app-brands',
  imports: [
    RouterLink,
    BadgeComponent,
    PageHeaderComponent,
    ButtonComponent,
    LoadingStateComponent,
    EmptyStateComponent,
    ErrorStateComponent,
  ],
  templateUrl: './brands.component.html',
})
export class BrandsComponent implements OnInit {
  private readonly brandsApi = inject(BrandService);
  private readonly router = inject(Router);

  readonly status = signal<PageStatus>('loading');
  readonly brands = signal<Brand[]>([]);
  readonly errorMessage = signal('Something went wrong. Please try again.');
  readonly formatDate = formatBrandDate;

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.status.set('loading');
    this.brandsApi.listBrands().subscribe({
      next: (response) => {
        this.brands.set(response.items);
        this.status.set('ready');
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 401) {
          void this.router.navigate(['/login']);
          return;
        }
        this.errorMessage.set(apiErrorMessage(error, 'Something went wrong. Please try again.'));
        this.status.set('error');
      },
    });
  }
}
