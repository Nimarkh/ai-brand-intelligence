import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, forkJoin, map, of, switchMap } from 'rxjs';

import { AuditSelectComponent } from '../../shared/components/audit-select/audit-select.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ScoreComponent } from '../../shared/components/score/score.component';
import { StatCardComponent } from '../../shared/components/stat-card/stat-card.component';
import { selectedOwnedAudit } from '../../shared/audit-selection';
import { formatScoreOutOf100, UNAVAILABLE } from '../../shared/format';
import { pageErrorMessage } from '../../shared/http-error';
import {
  AIVisibilityResponse,
  formatRateAsPercent,
  formatVisibilityValue,
  visibilityStatusLabel,
  visibilityStatusTone,
} from '../audits/ai-visibility.models';
import { AiVisibilityService } from '../audits/ai-visibility.service';
import { IntelligenceAudit } from '../intelligence-chat/intelligence.models';
import { IntelligenceService } from '../intelligence-chat/intelligence.service';
import {
  QueryExplorerItem,
  categoryLabel,
  formatAlignment,
  formatAuditDate,
  formatPosition,
  yesNo,
} from '../query-explorer/query-explorer.models';
import { QueryExplorerService } from '../query-explorer/query-explorer.service';

type PageStatus = 'loading' | 'ready' | 'error';

interface VisibilityPage {
  audits: IntelligenceAudit[];
  audit: IntelligenceAudit;
  visibility: AIVisibilityResponse;
  queries: QueryExplorerItem[];
  queryTotal: number;
}

@Component({
  selector: 'app-ai-visibility',
  imports: [
    RouterLink,
    PageHeaderComponent,
    ButtonComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    BadgeComponent,
    StatCardComponent,
    ScoreComponent,
    AuditSelectComponent,
  ],
  templateUrl: './ai-visibility.component.html',
})
export class AiVisibilityComponent {
  private readonly intelligence = inject(IntelligenceService);
  private readonly visibilityApi = inject(AiVisibilityService);
  private readonly explorer = inject(QueryExplorerService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly requests = new Subject<string>();

  readonly status = signal<PageStatus>('loading');
  readonly page = signal<VisibilityPage | null>(null);
  readonly errorMessage = signal("We couldn't load AI Visibility. Please try again.");
  readonly httpStatus = signal(0);
  readonly selectedAuditId = signal('');
  readonly unavailable = UNAVAILABLE;

  constructor() {
    this.requests
      .pipe(
        switchMap((auditId) => this.fetch(auditId)),
        takeUntilDestroyed(),
      )
      .subscribe((result) => this.apply(result));

    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const auditId = params.get('audit_id') ?? '';
      this.selectedAuditId.set(auditId);
      this.status.set('loading');
      this.requests.next(auditId);
    });
  }

  load(): void {
    this.status.set('loading');
    this.requests.next(this.selectedAuditId());
  }

  onAuditChange(auditId: string): void {
    if (!auditId || auditId === this.selectedAuditId()) {
      return;
    }
    void this.router.navigate(['/ai-visibility'], { queryParams: { audit_id: auditId } });
  }

  statusLabel(value: AIVisibilityResponse['status']): string {
    return visibilityStatusLabel(value);
  }

  statusTone(value: AIVisibilityResponse['status']): 'info' | 'warning' | 'neutral' {
    return visibilityStatusTone(value);
  }

  rate(value: number | null | undefined): string {
    return formatRateAsPercent(value);
  }

  position(value: number | null | undefined): string {
    return formatPosition(value);
  }

  alignment(value: number | null | undefined): string {
    return formatAlignment(value);
  }

  score(value: number | null | undefined): string {
    return formatScoreOutOf100(value ?? null);
  }

  metricScore(value: number | null | undefined): string {
    return formatVisibilityValue(value);
  }

  categoryName(category: QueryExplorerItem['category']): string {
    return categoryLabel(category);
  }

  yesNoLabel(value: boolean | null | undefined): string {
    return yesNo(value);
  }

  auditDate(audit: IntelligenceAudit): string {
    return formatAuditDate(audit.completed_at ?? audit.created_at) ?? UNAVAILABLE;
  }

  hasQueries(data: VisibilityPage): boolean {
    return data.visibility.total_queries > 0 || data.queryTotal > 0;
  }

  private fetch(requestedId: string) {
    return this.intelligence.getAudits(requestedId || null).pipe(
      switchMap((catalog) => {
        const audit = selectedOwnedAudit(catalog, requestedId);
        if (!audit) {
          return of({
            kind: 'empty' as const,
            audits: catalog.audits,
          });
        }
        return forkJoin({
          visibility: this.visibilityApi.getVisibility(audit.id),
          explorer: this.explorer.getExplorerData({ auditId: audit.id, page: 1, pageSize: 10 }),
        }).pipe(
          map(({ visibility, explorer }) => ({
            kind: 'ready' as const,
            page: {
              audits: catalog.audits,
              audit,
              visibility,
              queries: explorer.items,
              queryTotal: explorer.pagination.total,
            },
          })),
        );
      }),
      catchError((error: HttpErrorResponse) =>
        of({
          kind: 'error' as const,
          httpStatus: error.status ?? 0,
          message: pageErrorMessage(error, "We couldn't load AI Visibility. Please try again."),
        }),
      ),
    );
  }

  private apply(
    result:
      | { kind: 'empty'; audits: IntelligenceAudit[] }
      | { kind: 'ready'; page: VisibilityPage }
      | { kind: 'error'; httpStatus: number; message: string },
  ): void {
    if (result.kind === 'error') {
      if (result.httpStatus === 401) {
        void this.router.navigate(['/login']);
        return;
      }
      this.httpStatus.set(result.httpStatus);
      this.errorMessage.set(result.message);
      this.page.set(null);
      this.status.set('error');
      return;
    }
    if (result.kind === 'empty') {
      this.page.set(null);
      this.status.set('ready');
      return;
    }
    this.page.set(result.page);
    this.selectedAuditId.set(result.page.audit.id);
    this.status.set('ready');
    const current = this.route.snapshot.queryParamMap.get('audit_id') ?? '';
    if (current !== result.page.audit.id) {
      void this.router.navigate(['/ai-visibility'], {
        queryParams: { audit_id: result.page.audit.id },
        replaceUrl: true,
      });
    }
  }
}
