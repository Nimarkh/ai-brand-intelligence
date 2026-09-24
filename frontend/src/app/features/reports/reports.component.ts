import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { ModalComponent } from '../../shared/components/modal/modal.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import {
  CompletedAuditOption,
  ReportList,
  ReportListItem,
  ReportStatus,
  auditOptionLabel,
  formatReportDate,
  statusLabel,
  statusTone,
} from './reports.models';
import { ReportsService } from './reports.service';

@Component({
  selector: 'app-reports',
  imports: [
    RouterLink,
    BadgeComponent,
    ButtonComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    ModalComponent,
    PageHeaderComponent,
  ],
  templateUrl: './reports.component.html',
  styleUrl: './reports.component.scss',
})
export class ReportsComponent {
  private readonly api = inject(ReportsService);
  private readonly destroyRef = inject(DestroyRef);

  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly page = signal<ReportList | null>(null);
  readonly modalOpen = signal(false);
  readonly modalError = signal<string | null>(null);
  readonly generating = signal(false);
  readonly selectedAuditId = signal('');
  readonly retryingId = signal<string | null>(null);
  readonly downloadingId = signal<string | null>(null);

  constructor() {
    this.load();
  }

  reports(): ReportListItem[] {
    return this.page()?.items ?? [];
  }

  completedAudits(): CompletedAuditOption[] {
    return this.page()?.completed_audits ?? [];
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.api
      .list()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.page.set(page);
          this.loading.set(false);
        },
        error: () => {
          this.loading.set(false);
          this.loadError.set('Reports could not be loaded. Please try again.');
        },
      });
  }

  openModal(): void {
    const first = this.completedAudits()[0];
    this.selectedAuditId.set(first?.id ?? '');
    this.modalError.set(null);
    this.modalOpen.set(true);
  }

  closeModal(): void {
    this.modalOpen.set(false);
  }

  onAuditChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.selectedAuditId.set(select.value);
  }

  generate(): void {
    const auditId = this.selectedAuditId();
    if (!auditId || this.generating()) {
      return;
    }
    this.generating.set(true);
    this.modalError.set(null);
    this.api
      .create(auditId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (report) => {
          this.generating.set(false);
          this.modalOpen.set(false);
          this.actionError.set(
            report.status === 'FAILED'
              ? (report.message ?? 'The report could not be generated. Please try again.')
              : null,
          );
          this.load();
        },
        error: (error: HttpErrorResponse) => {
          this.generating.set(false);
          this.modalError.set(httpMessage(error, 'The report could not be generated. Please try again.'));
        },
      });
  }

  retry(report: ReportListItem): void {
    this.retryingId.set(report.id);
    this.actionError.set(null);
    this.api
      .create(report.audit_id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.retryingId.set(null);
          this.load();
        },
        error: (error: HttpErrorResponse) => {
          this.retryingId.set(null);
          this.actionError.set(httpMessage(error, 'The report could not be generated. Please try again.'));
        },
      });
  }

  download(report: ReportListItem): void {
    if (report.status !== 'READY') {
      return;
    }
    this.downloadingId.set(report.id);
    this.actionError.set(null);
    this.api
      .download(report.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          this.downloadingId.set(null);
          saveReportFile(blob, report.brand_name);
        },
        error: () => {
          this.downloadingId.set(null);
          this.actionError.set('The report could not be downloaded.');
        },
      });
  }

  optionLabel(audit: CompletedAuditOption): string {
    return auditOptionLabel(audit);
  }

  date(value: string | null): string {
    return formatReportDate(value);
  }

  label(status: ReportStatus): string {
    return statusLabel(status);
  }

  tone(status: ReportStatus): 'success' | 'danger' | 'info' {
    return statusTone(status);
  }
}

function httpMessage(error: HttpErrorResponse, fallback: string): string {
  const detail = error.error?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}

function saveReportFile(blob: Blob, brandName: string): void {
  const slug = brandName.replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'audit';
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${slug}-audit-intelligence-report.pdf`;
  anchor.click();
  URL.revokeObjectURL(url);
}
