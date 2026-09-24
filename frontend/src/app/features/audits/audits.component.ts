import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';

import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ScoreComponent } from '../../shared/components/score/score.component';
import { formatDateTimeOrDash } from '../../shared/format';
import { pageErrorMessage } from '../../shared/http-error';
import { BrandService } from '../brands/brand.service';
import { AuditService } from './audit.service';
import {
  AuditStatus,
  AuditSummary,
  ScoreStatus,
  auditHistoryStatusLabel,
  auditHistoryStatusTone,
  overallScoreAvailability,
} from './audit.models';

type PageStatus = 'loading' | 'ready' | 'error';

export interface AuditHistoryRow {
  audit: AuditSummary;
  brandName: string;
}

const HISTORY_LIMIT = 50;

@Component({
  selector: 'app-audits',
  imports: [
    RouterLink,
    PageHeaderComponent,
    ButtonComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    BadgeComponent,
    ScoreComponent,
  ],
  templateUrl: './audits.component.html',
})
export class AuditsComponent {
  private readonly brandsApi = inject(BrandService);
  private readonly auditsApi = inject(AuditService);
  private readonly router = inject(Router);

  readonly status = signal<PageStatus>('loading');
  readonly rows = signal<AuditHistoryRow[]>([]);
  readonly errorMessage = signal("We couldn't load your audits. Please try again.");
  readonly truncated = signal(false);

  constructor() {
    this.load();
  }

  load(): void {
    this.status.set('loading');
    this.brandsApi
      .listBrands()
      .pipe(
        switchMap((brands) => {
          if (brands.items.length === 0) {
            return of({ rows: [] as AuditHistoryRow[], truncated: false, failed: false as const, httpStatus: 0, message: '' });
          }
          return forkJoin(
            brands.items.map((brand) =>
              this.auditsApi.listAudits(brand.id, HISTORY_LIMIT).pipe(
                map((list) => ({
                  brandName: brand.name,
                  items: list.items,
                  hitLimit: list.items.length >= HISTORY_LIMIT,
                })),
              ),
            ),
          ).pipe(
            map((groups) => {
              const rows = groups
                .flatMap((group) =>
                  group.items.map((audit) => ({ audit, brandName: group.brandName })),
                )
                .sort((left, right) => this.byNewest(left.audit, right.audit));
              return {
                rows,
                truncated: groups.some((group) => group.hitLimit),
                failed: false as const,
                httpStatus: 0,
                message: '',
              };
            }),
          );
        }),
        catchError((error: HttpErrorResponse) =>
          of({
            rows: [] as AuditHistoryRow[],
            truncated: false,
            failed: true as const,
            httpStatus: error.status ?? 0,
            message: pageErrorMessage(error, "We couldn't load your audits. Please try again."),
          }),
        ),
      )
      .subscribe((result) => {
        if (result.failed) {
          if (result.httpStatus === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.errorMessage.set(result.message);
          this.status.set('error');
          return;
        }
        this.rows.set(result.rows);
        this.truncated.set(result.truncated);
        this.status.set('ready');
      });
  }

  statusLabel(status: AuditStatus): string {
    return auditHistoryStatusLabel(status);
  }

  statusTone(status: AuditStatus): 'success' | 'info' | 'warning' | 'danger' {
    return auditHistoryStatusTone(status);
  }

  overallState(audit: AuditSummary): ScoreStatus {
    return overallScoreAvailability(audit);
  }

  when(value: string | null): string {
    return formatDateTimeOrDash(value);
  }

  private byNewest(left: AuditSummary, right: AuditSummary): number {
    const created = right.created_at.localeCompare(left.created_at);
    if (created !== 0) {
      return created;
    }
    return right.id.localeCompare(left.id);
  }
}
