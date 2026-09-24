import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { StatCardComponent } from '../../shared/components/stat-card/stat-card.component';
import {
  ReportDetail,
  ReportStatus,
  formatReportDate,
  formatScore,
  statusLabel,
  statusTone,
} from './reports.models';
import { ReportsService } from './reports.service';

@Component({
  selector: 'app-report-detail',
  imports: [
    RouterLink,
    BadgeComponent,
    ButtonComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    PageHeaderComponent,
    StatCardComponent,
  ],
  templateUrl: './report-detail.component.html',
  styleUrl: './report-detail.component.scss',
})
export class ReportDetailComponent {
  private readonly api = inject(ReportsService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly report = signal<ReportDetail | null>(null);
  readonly downloading = signal(false);
  readonly retrying = signal(false);

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const id = params.get('id');
      if (id) {
        this.load(id);
      }
    });
  }

  load(id = this.report()?.id): void {
    if (!id) {
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.api
      .get(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (report) => {
          this.report.set(report);
          this.loading.set(false);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.report.set(null);
          this.error.set(
            error.status === 404 ? 'This report could not be found.' : 'The report could not be loaded. Please try again.',
          );
        },
      });
  }

  download(): void {
    const report = this.report();
    if (!report || report.status !== 'READY' || this.downloading()) {
      return;
    }
    this.downloading.set(true);
    this.actionError.set(null);
    this.api
      .download(report.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          this.downloading.set(false);
          const slug = report.brand_name.replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'audit';
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement('a');
          anchor.href = url;
          anchor.download = `${slug}-audit-intelligence-report.pdf`;
          anchor.click();
          URL.revokeObjectURL(url);
        },
        error: () => {
          this.downloading.set(false);
          this.actionError.set('The report could not be downloaded.');
        },
      });
  }

  retry(): void {
    const report = this.report();
    if (!report || this.retrying()) {
      return;
    }
    this.retrying.set(true);
    this.actionError.set(null);
    this.api
      .create(report.audit_id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (created) => {
          this.retrying.set(false);
          void this.router.navigate(['/reports', created.id]);
        },
        error: (error: HttpErrorResponse) => {
          this.retrying.set(false);
          const detail = error.error?.detail;
          this.actionError.set(
            typeof detail === 'string' && detail.trim()
              ? detail
              : 'The report could not be generated. Please try again.',
          );
        },
      });
  }

  date(value: string | null): string {
    return formatReportDate(value);
  }

  score(value: number | null): string {
    return formatScore(value);
  }

  label(status: ReportStatus): string {
    return statusLabel(status);
  }

  tone(status: ReportStatus): 'success' | 'danger' | 'info' {
    return statusTone(status);
  }

  availability(status: string): string {
    if (status === 'PROVISIONAL') {
      return 'Provisional';
    }
    if (status === 'AVAILABLE') {
      return 'Available';
    }
    return 'Not available';
  }
}
