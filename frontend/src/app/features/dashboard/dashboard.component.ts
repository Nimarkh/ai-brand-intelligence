import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, map, of, switchMap } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { CardComponent } from '../../shared/components/card/card.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { DashboardAuditSummaryComponent } from './components/audit-summary.component';
import { DashboardInsightListComponent } from './components/insight-list.component';
import { DashboardMetricRowComponent } from './components/metric-row.component';
import { DashboardOverallScoreComponent } from './components/overall-score.component';
import { DashboardRecommendationPreviewComponent } from './components/recommendation-preview.component';
import { DashboardScoreCardComponent } from './components/score-card.component';
import {
  DashboardOverview,
  DashboardScoreCard,
  formatCoverage,
} from './dashboard.models';
import { DashboardService } from './dashboard.service';
import { formatDisplayDate } from '../../shared/format';

type PageStatus = 'loading' | 'ready' | 'error';

@Component({
  selector: 'app-dashboard',
  imports: [
    FormsModule,
    RouterLink,
    PageHeaderComponent,
    ButtonComponent,
    CardComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    DashboardOverallScoreComponent,
    DashboardScoreCardComponent,
    DashboardInsightListComponent,
    DashboardRecommendationPreviewComponent,
    DashboardAuditSummaryComponent,
    DashboardMetricRowComponent,
  ],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly dashboardApi = inject(DashboardService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly reload = new Subject<boolean>();

  readonly status = signal<PageStatus>('loading');
  readonly refreshing = signal(false);
  readonly overview = signal<DashboardOverview | null>(null);
  readonly selectedBrandId = signal<string>('');

  readonly greeting = computed(() => {
    const fullName = this.auth.currentUser()?.full_name?.trim() ?? '';
    if (!fullName) {
      return 'Good morning';
    }
    const firstName = fullName.split(/\s+/)[0];
    return `Good morning, ${firstName}`;
  });

  readonly isEmptyWorkspace = computed(() => {
    const data = this.overview();
    return !!data && data.workspace.brand_count === 0 && data.workspace.audit_count === 0;
  });

  readonly hasBrandNoAudit = computed(() => {
    const data = this.overview();
    return !!data && data.workspace.brand_count > 0 && data.selected_audit === null;
  });

  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      this.selectedBrandId.set(params.get('brand_id') ?? '');
    });

    this.reload
      .pipe(
        switchMap((isRefresh) => {
          if (isRefresh) {
            this.refreshing.set(true);
          } else {
            this.refreshing.set(false);
            this.status.set('loading');
          }
          const brandId = this.selectedBrandId() || null;
          return this.dashboardApi.getOverview(brandId).pipe(
            map((overview) => ({ overview, failed: false, httpStatus: 0 })),
            catchError((error: HttpErrorResponse) =>
              of({ overview: null, failed: true, httpStatus: error.status ?? 0 }),
            ),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((result) => {
        this.refreshing.set(false);
        if (result.failed || result.overview === null) {
          if (result.httpStatus === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.status.set('error');
          return;
        }
        this.overview.set(result.overview);
        this.status.set('ready');
      });
  }

  ngOnInit(): void {
    const brandId = this.route.snapshot.queryParamMap.get('brand_id') ?? '';
    this.selectedBrandId.set(brandId);
    this.load();
  }

  load(): void {
    this.reload.next(this.status() === 'ready');
  }

  onBrandChange(brandId: string): void {
    this.selectedBrandId.set(brandId);
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { brand_id: brandId || null },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
    this.reload.next(this.status() === 'ready');
  }

  formatCardDate(card: DashboardScoreCard): string | null {
    return formatDisplayDate(card.audit_date);
  }

  coverage(value: number | null | undefined): string {
    return formatCoverage(value);
  }

  hasSnapshotMetrics(data: DashboardOverview): boolean {
    const snap = data.snapshot;
    return [
      snap.pages_crawled,
      snap.seo_findings,
      snap.high_severity_findings,
      snap.ai_queries,
      snap.ai_successful_responses,
      snap.ai_response_coverage,
      snap.ai_mention_rate,
      snap.entity_pages_analyzed,
      snap.pages_with_schema,
      snap.structured_identity_coverage,
      snap.recommendations_total,
      snap.recommendations_high,
      snap.recommendations_medium,
    ].some((value) => value !== null && value !== undefined);
  }
}
