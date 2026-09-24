import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { Brand } from '../brands/brand.models';
import { BrandService } from '../brands/brand.service';
import { apiErrorMessage } from '../brands/api-error';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { CardComponent } from '../../shared/components/card/card.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ScoreComponent } from '../../shared/components/score/score.component';
import {
  AiQueryDetail,
  AiQueryListItem,
  aiQueryRunSummary,
  formatSemanticAlignment,
} from './ai-query.models';
import { AiQueryService } from './ai-query.service';
import {
  AIVisibilityResponse,
  formatRateAsPercent,
  formatVisibilityValue,
  visibilityStatusLabel,
  visibilityStatusTone,
} from './ai-visibility.models';
import { AiVisibilityService } from './ai-visibility.service';
import {
  EntityStrengthResponse,
  entityComponentLabel,
  entityStatusLabel,
  entityStatusTone,
  formatEntityValue,
} from './entity.models';
import { EntityService } from './entity.service';
import {
  RecommendationItem,
  RecommendationListResponse,
  RecommendationRunResponse,
  categoryLabel,
  formatScoreValue,
  priorityLabel,
  priorityTone,
} from './recommendation.models';
import { RecommendationService } from './recommendation.service';
import { AuditService } from './audit.service';
import {
  AuditScoreResponse,
  AuditSummary,
  SeoFinding,
  auditStatusLabel,
  componentLabel,
  scoreImpactSummary,
  seoAnalysisCompletedMessage,
  severityBadgeTone,
  severityLabel,
  truncateUrl,
} from './audit.models';

type PageStatus = 'loading' | 'ready' | 'not-found' | 'error';

@Component({
  selector: 'app-audit-detail',
  imports: [
    RouterLink,
    PageHeaderComponent,
    ButtonComponent,
    BadgeComponent,
    CardComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    ScoreComponent,
  ],
  templateUrl: './audit-detail.component.html',
})
export class AuditDetailComponent {
  private readonly auditsApi = inject(AuditService);
  private readonly aiQueriesApi = inject(AiQueryService);
  private readonly aiVisibilityApi = inject(AiVisibilityService);
  private readonly entityApi = inject(EntityService);
  private readonly recommendationsApi = inject(RecommendationService);
  private readonly brandsApi = inject(BrandService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly status = signal<PageStatus>('loading');
  readonly audit = signal<AuditSummary | null>(null);
  readonly brand = signal<Brand | null>(null);
  readonly findings = signal<SeoFinding[]>([]);
  readonly findingsTotal = signal(0);
  readonly findingsLoaded = signal(false);
  readonly score = signal<AuditScoreResponse | null>(null);
  readonly scoreLoaded = signal(false);
  readonly aiQueries = signal<AiQueryListItem[]>([]);
  readonly aiQueriesTotal = signal(0);
  readonly aiQueriesLoaded = signal(false);
  readonly expandedQueryId = signal<string | null>(null);
  readonly expandedDetail = signal<AiQueryDetail | null>(null);
  readonly expandingQuery = signal(false);
  readonly errorMessage = signal('Something went wrong. Please try again.');
  readonly analyzing = signal(false);
  readonly analyzeError = signal<string | null>(null);
  readonly analyzeMessage = signal<string | null>(null);
  readonly scoring = signal(false);
  readonly scoreError = signal<string | null>(null);
  readonly runningAiQueries = signal(false);
  readonly aiQueryError = signal<string | null>(null);
  readonly aiQueryMessage = signal<string | null>(null);
  readonly visibility = signal<AIVisibilityResponse | null>(null);
  readonly visibilityLoaded = signal(false);
  readonly calculatingVisibility = signal(false);
  readonly visibilityError = signal<string | null>(null);
  readonly entity = signal<EntityStrengthResponse | null>(null);
  readonly entityLoaded = signal(false);
  readonly calculatingEntity = signal(false);
  readonly entityError = signal<string | null>(null);
  readonly recommendations = signal<RecommendationItem[]>([]);
  readonly recommendationsTotal = signal(0);
  readonly recommendationsLoaded = signal(false);
  readonly calculatingRecommendations = signal(false);
  readonly recommendationsError = signal<string | null>(null);
  readonly recommendationsMessage = signal<string | null>(null);

  readonly statusLabel = auditStatusLabel;
  readonly severityTone = severityBadgeTone;
  readonly severityLabel = severityLabel;
  readonly shortUrl = truncateUrl;
  readonly componentLabel = componentLabel;
  readonly impactSummary = scoreImpactSummary;
  readonly semanticLabel = formatSemanticAlignment;
  readonly visibilityLabel = visibilityStatusLabel;
  readonly visibilityTone = visibilityStatusTone;
  readonly visibilityValue = formatVisibilityValue;
  readonly ratePercent = formatRateAsPercent;
  readonly entityLabel = entityStatusLabel;
  readonly entityTone = entityStatusTone;
  readonly entityComponentLabel = entityComponentLabel;
  readonly entityValue = formatEntityValue;
  readonly priorityLabel = priorityLabel;
  readonly priorityTone = priorityTone;
  readonly categoryLabel = categoryLabel;
  readonly scoreValue = formatScoreValue;

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

  canAnalyze(): boolean {
    const audit = this.audit();
    return !!audit && !this.analyzing() && audit.status !== 'RUNNING';
  }

  canScore(): boolean {
    const audit = this.audit();
    return !!audit && !this.scoring() && audit.status !== 'RUNNING';
  }

  canRunAiQueries(): boolean {
    const audit = this.audit();
    return !!audit && !this.runningAiQueries();
  }

  canCalculateVisibility(): boolean {
    const audit = this.audit();
    return !!audit && !this.calculatingVisibility();
  }

  visibilityIsAvailable(): boolean {
    const visibility = this.visibility();
    return !!visibility && visibility.status !== 'UNAVAILABLE' && visibility.overall_score !== null;
  }

  canCalculateEntity(): boolean {
    const audit = this.audit();
    return !!audit && !this.calculatingEntity();
  }

  canCalculateRecommendations(): boolean {
    const audit = this.audit();
    return !!audit && !this.calculatingRecommendations();
  }

  entityIsAvailable(): boolean {
    const entity = this.entity();
    return !!entity && entity.status !== 'UNAVAILABLE' && entity.overall_score !== null;
  }

  scoreIsAvailable(): boolean {
    const score = this.score();
    return !!score && score.status !== 'UNAVAILABLE' && score.overall.score !== null;
  }

  analyzeSeo(): void {
    const audit = this.audit();
    if (!audit || this.analyzing()) {
      return;
    }
    this.analyzing.set(true);
    this.analyzeError.set(null);
    this.analyzeMessage.set(null);
    this.auditsApi
      .analyzeSeo(audit.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.analyzing.set(false);
          this.analyzeMessage.set(seoAnalysisCompletedMessage(result.findings_count));
          this.loadFindings(audit.id);
          this.clearRecommendationsLocal();
        },
        error: (error: HttpErrorResponse) => {
          this.analyzing.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.analyzeError.set(apiErrorMessage(error, 'SEO analysis failed. Please try again.'));
        },
      });
  }

  calculateScore(): void {
    const audit = this.audit();
    if (!audit || this.scoring()) {
      return;
    }
    this.scoring.set(true);
    this.scoreError.set(null);
    this.auditsApi
      .calculateScore(audit.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.scoring.set(false);
          this.score.set(result);
          this.scoreLoaded.set(true);
          this.audit.update((current) =>
            current
              ? {
                  ...current,
                  overall_score: result.overall.score,
                  website_score: result.website_health.score,
                  seo_score: result.seo.score,
                }
              : current,
          );
        },
        error: (error: HttpErrorResponse) => {
          this.scoring.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.scoreError.set(apiErrorMessage(error, 'Score calculation failed. Please try again.'));
        },
      });
  }

  runAiAnalysis(): void {
    const audit = this.audit();
    if (!audit || this.runningAiQueries()) {
      return;
    }
    this.runningAiQueries.set(true);
    this.aiQueryError.set(null);
    this.aiQueryMessage.set(null);
    this.expandedQueryId.set(null);
    this.expandedDetail.set(null);
    this.aiQueriesApi
      .run(audit.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.runningAiQueries.set(false);
          this.aiQueryMessage.set(aiQueryRunSummary(result));
          this.loadAiQueries(audit.id);
          this.loadVisibility(audit.id);
          this.audit.update((current) =>
            current
              ? {
                  ...current,
                  ai_visibility_score: null,
                  semantic_score: null,
                  entity_score: null,
                }
              : current,
          );
          this.loadEntity(audit.id);
          this.clearRecommendationsLocal();
        },
        error: (error: HttpErrorResponse) => {
          this.runningAiQueries.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.aiQueryError.set(
            apiErrorMessage(error, 'AI query analysis failed. Please try again.'),
          );
        },
      });
  }



  calculateEntity(): void {
    const audit = this.audit();
    if (!audit || this.calculatingEntity()) {
      return;
    }
    this.calculatingEntity.set(true);
    this.entityError.set(null);
    this.entityApi
      .calculateEntity(audit.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.calculatingEntity.set(false);
          this.entity.set(result);
          this.entityLoaded.set(true);
          this.audit.update((current) =>
            current ? { ...current, entity_score: result.overall_score } : current,
          );
          this.clearRecommendationsLocal();
        },
        error: (error: HttpErrorResponse) => {
          this.calculatingEntity.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.entityError.set(
            apiErrorMessage(error, 'Entity Intelligence calculation failed. Please try again.'),
          );
        },
      });
  }

  calculateRecommendations(): void {
    const audit = this.audit();
    if (!audit || this.calculatingRecommendations()) {
      return;
    }
    this.calculatingRecommendations.set(true);
    this.recommendationsError.set(null);
    this.recommendationsMessage.set(null);
    this.recommendationsApi
      .calculateRecommendations(audit.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result: RecommendationRunResponse) => {
          this.calculatingRecommendations.set(false);
          this.recommendationsMessage.set(
            `Generated ${result.recommendations_generated} recommendation${
              result.recommendations_generated === 1 ? '' : 's'
            } (${result.high} high, ${result.medium} medium, ${result.low} low).`,
          );
          this.loadRecommendations(audit.id);
        },
        error: (error: HttpErrorResponse) => {
          this.calculatingRecommendations.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.recommendationsError.set(
            apiErrorMessage(error, 'Recommendation calculation failed. Please try again.'),
          );
        },
      });
  }

  calculateVisibility(): void {
    const audit = this.audit();
    if (!audit || this.calculatingVisibility()) {
      return;
    }
    this.calculatingVisibility.set(true);
    this.visibilityError.set(null);
    this.aiVisibilityApi
      .calculateVisibility(audit.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.calculatingVisibility.set(false);
          this.visibility.set(result);
          this.visibilityLoaded.set(true);
          this.audit.update((current) =>
            current
              ? {
                  ...current,
                  ai_visibility_score: result.overall_score,
                  semantic_score: result.metrics.semantic_score,
                }
              : current,
          );
          this.clearRecommendationsLocal();
        },
        error: (error: HttpErrorResponse) => {
          this.calculatingVisibility.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.visibilityError.set(
            apiErrorMessage(error, 'AI Visibility calculation failed. Please try again.'),
          );
        },
      });
  }

  toggleQuery(query: AiQueryListItem): void {
    const audit = this.audit();
    if (!audit) {
      return;
    }
    if (this.expandedQueryId() === query.id) {
      this.expandedQueryId.set(null);
      this.expandedDetail.set(null);
      return;
    }
    this.expandedQueryId.set(query.id);
    this.expandedDetail.set(null);
    if (!query.has_response) {
      return;
    }
    this.expandingQuery.set(true);
    this.aiQueriesApi
      .get(audit.id, query.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (detail) => {
          this.expandingQuery.set(false);
          this.expandedDetail.set(detail);
        },
        error: (error: HttpErrorResponse) => {
          this.expandingQuery.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.aiQueryError.set(apiErrorMessage(error, 'Could not load AI response.'));
        },
      });
  }

  load(id = this.audit()?.id ?? this.route.snapshot.paramMap.get('id')): void {
    if (!id) {
      this.status.set('not-found');
      return;
    }
    this.status.set('loading');
    this.analyzeError.set(null);
    this.scoreError.set(null);
    this.aiQueryError.set(null);
    this.visibilityError.set(null);
    this.entityError.set(null);
    this.recommendationsError.set(null);
    this.recommendationsMessage.set(null);
    this.scoreLoaded.set(false);
    this.aiQueriesLoaded.set(false);
    this.visibilityLoaded.set(false);
    this.entityLoaded.set(false);
    this.recommendationsLoaded.set(false);
    this.recommendations.set([]);
    this.recommendationsTotal.set(0);
    this.expandedQueryId.set(null);
    this.expandedDetail.set(null);
    this.auditsApi.getAudit(id).subscribe({
      next: (audit) => {
        this.audit.set(audit);
        this.loadBrand(audit.brand_id);
        this.loadFindings(audit.id);
        this.loadScore(audit.id);
        this.loadAiQueries(audit.id);
        this.loadVisibility(audit.id);
        this.loadEntity(audit.id);
        this.loadRecommendations(audit.id);
        this.status.set('ready');
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 401) {
          void this.router.navigate(['/login']);
          return;
        }
        if (error.status === 404 || error.status === 422) {
          this.audit.set(null);
          this.status.set('not-found');
          return;
        }
        this.errorMessage.set(apiErrorMessage(error, 'Could not load this audit.'));
        this.status.set('error');
      },
    });
  }

  private loadBrand(brandId: string): void {
    this.brandsApi
      .getBrand(brandId)
      .pipe(
        catchError(() => of(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((brand) => this.brand.set(brand));
  }

  private loadFindings(auditId: string): void {
    this.auditsApi
      .listSeoFindings(auditId)
      .pipe(
        catchError(() => of({ items: [], total: 0 })),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        this.findings.set(response.items);
        this.findingsTotal.set(response.total);
        this.findingsLoaded.set(true);
      });
  }

  private loadScore(auditId: string): void {
    this.auditsApi
      .getScore(auditId)
      .pipe(
        catchError(() => of(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        this.score.set(response);
        this.scoreLoaded.set(true);
      });
  }

  private loadAiQueries(auditId: string): void {
    this.aiQueriesApi
      .list(auditId)
      .pipe(
        catchError(() => of({ items: [], total: 0 })),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        this.aiQueries.set(response.items);
        this.aiQueriesTotal.set(response.total);
        this.aiQueriesLoaded.set(true);
      });
  }
  private loadVisibility(auditId: string): void {
    this.aiVisibilityApi
      .getVisibility(auditId)
      .pipe(
        catchError(() => of(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        this.visibility.set(response);
        this.visibilityLoaded.set(true);
      });
  }
  private loadEntity(auditId: string): void {
    this.entityApi
      .getEntity(auditId)
      .pipe(
        catchError(() => of(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        this.entity.set(response);
        this.entityLoaded.set(true);
      });
  }

  private loadRecommendations(auditId: string): void {
    this.recommendationsApi
      .getRecommendations(auditId)
      .pipe(
        catchError(() => of({ items: [], total: 0 } satisfies RecommendationListResponse)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        this.recommendations.set(response.items);
        this.recommendationsTotal.set(response.total);
        this.recommendationsLoaded.set(true);
      });
  }

  private clearRecommendationsLocal(): void {
    this.recommendations.set([]);
    this.recommendationsTotal.set(0);
    this.recommendationsLoaded.set(true);
    this.recommendationsMessage.set(null);
    this.recommendationsError.set(null);
  }
}
