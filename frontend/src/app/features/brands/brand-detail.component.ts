import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { switchMap } from 'rxjs';

import { AuditService } from '../audits/audit.service';
import { AuditSummary, auditStatusLabel, crawlCompletedMessage } from '../audits/audit.models';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { CardComponent } from '../../shared/components/card/card.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ScoreComponent } from '../../shared/components/score/score.component';
import { ToastService } from '../../shared/components/toast/toast.service';
import { apiErrorMessage } from './api-error';
import { Brand, formatBrandDate, safeWebsiteHref } from './brand.models';
import { BrandService } from './brand.service';

type PageStatus = 'loading' | 'ready' | 'not-found' | 'error';

@Component({
  selector: 'app-brand-detail',
  imports: [
    RouterLink,
    PageHeaderComponent,
    ButtonComponent,
    BadgeComponent,
    CardComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    ModalComponent,
    ScoreComponent,
  ],
  templateUrl: './brand-detail.component.html',
})
export class BrandDetailComponent {
  private readonly brandsApi = inject(BrandService);
  private readonly auditsApi = inject(AuditService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);
  private readonly destroyRef = inject(DestroyRef);

  readonly status = signal<PageStatus>('loading');
  readonly brand = signal<Brand | null>(null);
  readonly errorMessage = signal('Something went wrong. Please try again.');
  readonly confirmOpen = signal(false);
  readonly deleting = signal(false);
  readonly deleteError = signal<string | null>(null);
  readonly crawling = signal(false);
  readonly crawlError = signal<string | null>(null);
  readonly latestAudit = signal<AuditSummary | null>(null);
  readonly formatDate = formatBrandDate;
  readonly websiteHref = safeWebsiteHref;

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const id = params.get('id');
      if (!id) {
        this.status.set('not-found');
        return;
      }
      this.load(id);
    });
  }

  statusLabel(): string {
    if (this.crawling()) {
      return auditStatusLabel('RUNNING');
    }
    return auditStatusLabel(this.latestAudit()?.status ?? null);
  }

  resultMessage(): string | null {
    if (this.crawlError()) {
      return this.crawlError();
    }
    const latest = this.latestAudit();
    if (!this.crawling() && latest?.status === 'COMPLETED') {
      return crawlCompletedMessage(latest.pages_crawled);
    }
    return null;
  }

  startCrawl(): void {
    const brand = this.brand();
    if (!brand?.website_url || this.crawling()) {
      return;
    }
    this.crawling.set(true);
    this.crawlError.set(null);
    this.auditsApi
      .createAudit(brand.id)
      .pipe(
        switchMap((audit) => {
          this.latestAudit.set(audit);
          return this.auditsApi.crawl(audit.id);
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (result) => {
          this.crawling.set(false);
          this.latestAudit.update((current) =>
            current
              ? {
                  ...current,
                  id: result.audit_id,
                  status: result.status,
                  pages_crawled: result.pages_crawled,
                }
              : current,
          );
          if (result.status !== 'COMPLETED') {
            this.crawlError.set('Website crawl failed. Please try again.');
          }
        },
        error: (error: HttpErrorResponse) => {
          this.crawling.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.crawlError.set('Website crawl failed. Please try again.');
          this.latestAudit.update((current) => (current ? { ...current, status: 'FAILED' } : current));
        },
      });
  }

  load(id = this.brand()?.id ?? this.route.snapshot.paramMap.get('id')): void {
    if (!id) {
      this.status.set('not-found');
      return;
    }
    this.status.set('loading');
    this.crawlError.set(null);
    this.loadAudits(id);
    this.brandsApi.getBrand(id).subscribe({
      next: (brand) => {
        this.brand.set(brand);
        this.status.set('ready');
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 401) {
          void this.router.navigate(['/login']);
          return;
        }
        if (error.status === 404 || error.status === 422) {
          this.brand.set(null);
          this.status.set('not-found');
          return;
        }
        this.errorMessage.set(apiErrorMessage(error, 'Could not load this brand.'));
        this.status.set('error');
      },
    });
  }

  private loadAudits(brandId: string): void {
    this.auditsApi
      .listAudits(brandId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          if (!this.crawling()) {
            this.latestAudit.set(response.items[0] ?? null);
          }
        },
        error: (error: HttpErrorResponse) => {
          if (error.status === 401) {
            void this.router.navigate(['/login']);
          }
        },
      });
  }

  openDelete(): void {
    this.deleteError.set(null);
    this.confirmOpen.set(true);
  }

  confirmDelete(): void {
    const brand = this.brand();
    if (!brand || this.deleting()) {
      return;
    }
    this.deleting.set(true);
    this.deleteError.set(null);
    this.brandsApi.deleteBrand(brand.id).subscribe({
      next: () => {
        this.confirmOpen.set(false);
        this.toast.show('success', `${brand.name} was deleted.`);
        void this.router.navigate(['/brands']);
      },
      error: (error: HttpErrorResponse) => {
        this.deleting.set(false);
        if (error.status === 401) {
          void this.router.navigate(['/login']);
          return;
        }
        this.deleteError.set(apiErrorMessage(error, 'Could not delete this brand. Please try again.'));
      },
    });
  }
}
