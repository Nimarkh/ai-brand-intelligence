import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { BadgeComponent, BadgeTone } from '../../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { formatDateOrDash, formatDateTimeOrDash } from '../../../shared/format';
import {
  AuditStatus,
  DashboardFreshness,
  DashboardSelectedAudit,
  auditStatusLabel,
} from '../dashboard.models';

@Component({
  selector: 'app-dashboard-audit-summary',
  imports: [RouterLink, BadgeComponent, ButtonComponent],
  template: `
    @if (audit(); as selected) {
      <div class="dash-audit">
        <div class="dash-audit__row">
          <span class="dash-audit__label">Brand</span>
          <span>{{ selected.brand_name }}</span>
        </div>
        <div class="dash-audit__row">
          <span class="dash-audit__label">Status</span>
          <app-badge [tone]="statusTone(selected.status)">{{ statusLabel(selected.status) }}</app-badge>
        </div>
        <div class="dash-audit__row">
          <span class="dash-audit__label">Created</span>
          <span>{{ formatDate(selected.created_at) }}</span>
        </div>
        <div class="dash-audit__row">
          <span class="dash-audit__label">Completed</span>
          <span>{{ formatDate(selected.completed_at) }}</span>
        </div>
        <div class="dash-audit__row">
          <span class="dash-audit__label">Pages crawled</span>
          <span>{{ selected.pages_crawled }}</span>
        </div>
        <div class="dash-audit__row">
          <span class="dash-audit__label">SEO findings</span>
          <span>{{ selected.seo_findings }}</span>
        </div>
        <div class="dash-audit__availability">
          <span [class.is-on]="selected.website_score_available">Website score</span>
          <span [class.is-on]="selected.seo_score_available">SEO score</span>
          <span [class.is-on]="selected.ai_visibility_available">AI Visibility</span>
          <span [class.is-on]="selected.entity_available">Entity Intelligence</span>
          <span [class.is-on]="selected.overall_score_available">Overall</span>
        </div>

        @if (freshness(); as stamps) {
          <div class="dash-audit__freshness">
            <h3>Data freshness</h3>
            <ul>
              @if (stamps.last_website_crawl) {
                <li>Last website crawl · {{ formatDateTime(stamps.last_website_crawl) }}</li>
              }
              @if (stamps.last_seo_analysis) {
                <li>Last SEO analysis · {{ formatDateTime(stamps.last_seo_analysis) }}</li>
              }
              @if (stamps.last_ai_analysis) {
                <li>Last AI analysis · {{ formatDateTime(stamps.last_ai_analysis) }}</li>
              }
              @if (stamps.last_recommendations_calculation) {
                <li>
                  Last recommendations · {{ formatDateTime(stamps.last_recommendations_calculation) }}
                </li>
              }
            </ul>
          </div>
        }

        <div class="dash-audit__actions">
          <a appButton variant="primary" [routerLink]="['/audits', selected.id]">View audit</a>
        </div>
      </div>
    }
  `,
})
export class DashboardAuditSummaryComponent {
  readonly audit = input<DashboardSelectedAudit | null>(null);
  readonly freshness = input<DashboardFreshness | null>(null);

  statusLabel(status: AuditStatus): string {
    return auditStatusLabel(status);
  }

  statusTone(status: AuditStatus): BadgeTone {
    if (status === 'COMPLETED') {
      return 'success';
    }
    if (status === 'RUNNING') {
      return 'info';
    }
    if (status === 'FAILED') {
      return 'danger';
    }
    return 'neutral';
  }

  formatDate(value: string | null | undefined): string {
    return formatDateOrDash(value);
  }

  formatDateTime(value: string | null | undefined): string {
    return formatDateTimeOrDash(value);
  }
}
