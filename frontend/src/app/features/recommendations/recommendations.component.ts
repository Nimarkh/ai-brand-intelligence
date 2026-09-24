import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, map, of, switchMap } from 'rxjs';

import { selectedOwnedAudit } from '../../shared/audit-selection';
import { AuditSelectComponent } from '../../shared/components/audit-select/audit-select.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { StatCardComponent } from '../../shared/components/stat-card/stat-card.component';
import { UNAVAILABLE } from '../../shared/format';
import { pageErrorMessage } from '../../shared/http-error';
import {
  RecommendationItem,
  RecommendationListResponse,
  categoryLabel,
  formatScoreValue,
  priorityLabel,
  priorityTone,
} from '../audits/recommendation.models';
import { RecommendationService } from '../audits/recommendation.service';
import { IntelligenceAudit } from '../intelligence-chat/intelligence.models';
import { IntelligenceService } from '../intelligence-chat/intelligence.service';
import { formatAuditDate } from '../query-explorer/query-explorer.models';

type PageStatus = 'loading' | 'ready' | 'error';

interface RecommendationsPage {
  audits: IntelligenceAudit[];
  audit: IntelligenceAudit;
  list: RecommendationListResponse;
}

@Component({
  selector: 'app-recommendations',
  imports: [
    RouterLink,
    PageHeaderComponent,
    ButtonComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    BadgeComponent,
    StatCardComponent,
    AuditSelectComponent,
  ],
  templateUrl: './recommendations.component.html',
})
export class RecommendationsComponent {
  private readonly intelligence = inject(IntelligenceService);
  private readonly recommendationsApi = inject(RecommendationService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly requests = new Subject<string>();

  readonly status = signal<PageStatus>('loading');
  readonly page = signal<RecommendationsPage | null>(null);
  readonly errorMessage = signal("We couldn't load recommendations. Please try again.");
  readonly httpStatus = signal(0);
  readonly selectedAuditId = signal('');

  readonly counts = computed(() => {
    const items = this.page()?.list.items ?? [];
    return {
      total: this.page()?.list.total ?? 0,
      high: items.filter((item) => item.priority === 'HIGH').length,
      medium: items.filter((item) => item.priority === 'MEDIUM').length,
      low: items.filter((item) => item.priority === 'LOW').length,
    };
  });

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
    void this.router.navigate(['/recommendations'], { queryParams: { audit_id: auditId } });
  }

  priorityName(priority: RecommendationItem['priority']): string {
    return priorityLabel(priority);
  }

  priorityBadge(priority: RecommendationItem['priority']): 'danger' | 'warning' | 'info' | 'neutral' {
    return priorityTone(priority);
  }

  categoryName(category: string): string {
    return categoryLabel(category);
  }

  score(value: number | null): string {
    return formatScoreValue(value);
  }

  auditDate(audit: IntelligenceAudit): string {
    return formatAuditDate(audit.completed_at ?? audit.created_at) ?? UNAVAILABLE;
  }

  private fetch(requestedId: string) {
    return this.intelligence.getAudits(requestedId || null).pipe(
      switchMap((catalog) => {
        const audit = selectedOwnedAudit(catalog, requestedId);
        if (!audit) {
          return of({ kind: 'empty' as const });
        }
        return this.recommendationsApi.getRecommendations(audit.id).pipe(
          map((list) => ({
            kind: 'ready' as const,
            page: { audits: catalog.audits, audit, list },
          })),
        );
      }),
      catchError((error: HttpErrorResponse) =>
        of({
          kind: 'error' as const,
          httpStatus: error.status ?? 0,
          message: pageErrorMessage(error, "We couldn't load recommendations. Please try again."),
        }),
      ),
    );
  }

  private apply(
    result:
      | { kind: 'empty' }
      | { kind: 'ready'; page: RecommendationsPage }
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
      void this.router.navigate(['/recommendations'], {
        queryParams: { audit_id: result.page.audit.id },
        replaceUrl: true,
      });
    }
  }
}
