import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, map, of, switchMap } from 'rxjs';

import { selectedOwnedAudit } from '../../shared/audit-selection';
import { AuditSelectComponent } from '../../shared/components/audit-select/audit-select.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ScoreComponent } from '../../shared/components/score/score.component';
import { StatCardComponent } from '../../shared/components/stat-card/stat-card.component';
import { UNAVAILABLE, formatPercent } from '../../shared/format';
import { pageErrorMessage } from '../../shared/http-error';
import {
  EntityComponentDetail,
  EntityStrengthResponse,
  entityComponentLabel,
  entityStatusLabel,
  entityStatusTone,
  formatEntityValue,
} from '../audits/entity.models';
import { EntityService } from '../audits/entity.service';
import { IntelligenceAudit } from '../intelligence-chat/intelligence.models';
import { IntelligenceService } from '../intelligence-chat/intelligence.service';
import { formatAuditDate } from '../query-explorer/query-explorer.models';

type PageStatus = 'loading' | 'ready' | 'error';

interface EntityPage {
  audits: IntelligenceAudit[];
  audit: IntelligenceAudit;
  entity: EntityStrengthResponse;
}

@Component({
  selector: 'app-entity',
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
  templateUrl: './entity.component.html',
})
export class EntityComponent {
  private readonly intelligence = inject(IntelligenceService);
  private readonly entityApi = inject(EntityService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly requests = new Subject<string>();

  readonly status = signal<PageStatus>('loading');
  readonly page = signal<EntityPage | null>(null);
  readonly errorMessage = signal("We couldn't load Entity Intelligence. Please try again.");
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
    void this.router.navigate(['/entity'], { queryParams: { audit_id: auditId } });
  }

  statusLabel(value: EntityStrengthResponse['status']): string {
    return entityStatusLabel(value);
  }

  statusTone(value: EntityStrengthResponse['status']): 'info' | 'warning' | 'neutral' {
    return entityStatusTone(value);
  }

  componentName(name: string): string {
    return entityComponentLabel(name);
  }

  componentValue(component: EntityComponentDetail): number | null {
    return component.score;
  }

  rate(value: number | null | undefined): string {
    return formatPercent(value);
  }

  scoreText(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return UNAVAILABLE;
    }
    return formatEntityValue(value);
  }

  numberValue(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return UNAVAILABLE;
    }
    return formatEntityValue(value);
  }

  auditDate(audit: IntelligenceAudit): string {
    return formatAuditDate(audit.completed_at ?? audit.created_at) ?? UNAVAILABLE;
  }

  lacksEvidence(entity: EntityStrengthResponse): boolean {
    return entity.evidence.analyzable_pages < 1 && entity.evidence.successful_ai_responses < 1;
  }

  private fetch(requestedId: string) {
    return this.intelligence.getAudits(requestedId || null).pipe(
      switchMap((catalog) => {
        const audit = selectedOwnedAudit(catalog, requestedId);
        if (!audit) {
          return of({ kind: 'empty' as const });
        }
        return this.entityApi.getEntity(audit.id).pipe(
          map((entity) => ({
            kind: 'ready' as const,
            page: { audits: catalog.audits, audit, entity },
          })),
        );
      }),
      catchError((error: HttpErrorResponse) =>
        of({
          kind: 'error' as const,
          httpStatus: error.status ?? 0,
          message: pageErrorMessage(error, "We couldn't load Entity Intelligence. Please try again."),
        }),
      ),
    );
  }

  private apply(
    result:
      | { kind: 'empty' }
      | { kind: 'ready'; page: EntityPage }
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
      void this.router.navigate(['/entity'], {
        queryParams: { audit_id: result.page.audit.id },
        replaceUrl: true,
      });
    }
  }
}
