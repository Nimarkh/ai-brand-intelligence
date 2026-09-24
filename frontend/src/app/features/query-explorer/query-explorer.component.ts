import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, map, of, switchMap } from 'rxjs';

import { BadgeComponent, BadgeTone } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { SelectOption } from '../../shared/components/select/select.component';
import { StatCardComponent } from '../../shared/components/stat-card/stat-card.component';
import {
  QueryCategory,
  QueryExplorerAudit,
  QueryExplorerItem,
  QueryExplorerView,
  UNAVAILABLE,
  categoryLabel,
  formatAlignment,
  formatAuditDate,
  formatLatency,
  formatPosition,
  formatRate,
  formatTimestamp,
  yesNo,
} from './query-explorer.models';
import { QueryExplorerService } from './query-explorer.service';

type PageStatus = 'loading' | 'ready' | 'error';
type TriState = '' | 'true' | 'false';

const PAGE_SIZES = [10, 20, 50, 100] as const;

@Component({
  selector: 'app-query-explorer',
  imports: [
    RouterLink,
    PageHeaderComponent,
    ButtonComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    BadgeComponent,
    StatCardComponent,
  ],
  templateUrl: './query-explorer.component.html',
  styleUrl: './query-explorer.component.scss',
})
export class QueryExplorerComponent {
  private readonly api = inject(QueryExplorerService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly requests = new Subject<boolean>();

  readonly status = signal<PageStatus>('loading');
  readonly listBusy = signal(false);
  readonly data = signal<QueryExplorerView | null>(null);
  readonly errorMessage = signal("We couldn't load Query Explorer. Please try again.");
  readonly httpStatus = signal(0);
  readonly selectedAuditId = signal<string | undefined>(undefined);
  readonly search = signal('');
  readonly category = signal<'' | QueryCategory>('');
  readonly responseStatus = signal<TriState>('');
  readonly mention = signal<TriState>('');
  readonly citation = signal<TriState>('');
  readonly page = signal(1);
  readonly pageSize = signal<(typeof PAGE_SIZES)[number]>(20);
  readonly expandedId = signal<string | null>(null);

  readonly unavailable = UNAVAILABLE;
  readonly pageSizes = PAGE_SIZES;
  readonly categoryOptions: readonly SelectOption[] = [
    { value: '', label: 'All categories' },
    { value: 'BRAND', label: 'Brand' },
    { value: 'PRODUCT', label: 'Product' },
    { value: 'INDUSTRY', label: 'Industry' },
    { value: 'COMPETITOR', label: 'Competitor' },
    { value: 'COMMERCIAL', label: 'Commercial' },
    { value: 'INFORMATIONAL', label: 'Informational' },
  ];
  readonly responseOptions: readonly SelectOption[] = [
    { value: '', label: 'Any status' },
    { value: 'true', label: 'Has response' },
    { value: 'false', label: 'No response' },
  ];
  readonly mentionOptions: readonly SelectOption[] = [
    { value: '', label: 'Any mention' },
    { value: 'true', label: 'Mentioned' },
    { value: 'false', label: 'Not mentioned' },
  ];
  readonly citationOptions: readonly SelectOption[] = [
    { value: '', label: 'Any citation' },
    { value: 'true', label: 'Citation found' },
    { value: 'false', label: 'No citation' },
  ];

  readonly filtersActive = computed(
    () =>
      this.search().trim().length > 0 ||
      this.category() !== '' ||
      this.responseStatus() !== '' ||
      this.mention() !== '' ||
      this.citation() !== '',
  );

  readonly pageSizeValue = computed(() => String(this.pageSize()));

  constructor() {
    this.requests
      .pipe(
        switchMap((keepVisible) => this.fetch(keepVisible)),
        takeUntilDestroyed(),
      )
      .subscribe((result) => this.applyResult(result));

    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const auditId = params.get('audit_id') ?? '';
      if (this.selectedAuditId() === auditId) {
        return;
      }
      const switching = this.selectedAuditId() !== undefined;
      this.selectedAuditId.set(auditId);
      if (switching) {
        this.resetFilterState();
        this.page.set(1);
        this.expandedId.set(null);
        this.data.set(null);
      }
      this.load(false);
    });
  }

  load(keepVisible = this.status() === 'ready' && this.data() !== null): void {
    this.requests.next(keepVisible);
  }

  selectValue(event: Event): string {
    return (event.target as HTMLSelectElement).value;
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  onAuditChange(auditId: string): void {
    if (!auditId || auditId === this.selectedAuditId()) {
      return;
    }
    this.selectedAuditId.set(auditId);
    this.resetFilterState();
    this.page.set(1);
    this.expandedId.set(null);
    this.data.set(null);
    void this.router.navigate(['/query-explorer'], {
      queryParams: { audit_id: auditId },
    });
    this.load(false);
  }

  onSearchChange(value: string): void {
    this.search.set(value);
    this.applyFilters();
  }

  onCategoryChange(value: string): void {
    this.category.set((value || '') as '' | QueryCategory);
    this.applyFilters();
  }

  onResponseStatusChange(value: string): void {
    this.responseStatus.set(this.asTriState(value));
    this.applyFilters();
  }

  onMentionChange(value: string): void {
    this.mention.set(this.asTriState(value));
    this.applyFilters();
  }

  onCitationChange(value: string): void {
    this.citation.set(this.asTriState(value));
    this.applyFilters();
  }

  clearFilters(): void {
    this.resetFilterState();
    this.page.set(1);
    this.expandedId.set(null);
    this.load(true);
  }

  onPageSizeChange(value: string): void {
    const size = Number(value);
    if (!PAGE_SIZES.includes(size as (typeof PAGE_SIZES)[number])) {
      return;
    }
    this.pageSize.set(size as (typeof PAGE_SIZES)[number]);
    this.page.set(1);
    this.expandedId.set(null);
    this.load(true);
  }

  goToPage(next: number): void {
    const view = this.data();
    if (!view || next < 1 || next > view.pagination.pages || next === this.page()) {
      return;
    }
    this.page.set(next);
    this.expandedId.set(null);
    this.load(true);
  }

  toggleQuery(queryId: string): void {
    this.expandedId.update((current) => (current === queryId ? null : queryId));
  }

  isOpen(item: QueryExplorerItem): boolean {
    return this.expandedId() === item.query_id;
  }

  auditLabel(audit: QueryExplorerAudit): string {
    const date = formatAuditDate(audit.completed_at ?? audit.created_at);
    return date ? `${date} — ${audit.brand_name}` : audit.brand_name;
  }

  categoryName(category: QueryCategory): string {
    return categoryLabel(category);
  }

  categoryTone(category: QueryCategory): BadgeTone {
    switch (category) {
      case 'BRAND':
        return 'info';
      case 'PRODUCT':
        return 'success';
      case 'COMPETITOR':
        return 'warning';
      case 'COMMERCIAL':
        return 'danger';
      default:
        return 'neutral';
    }
  }

  rate(value: number | null | undefined): string {
    return formatRate(value);
  }

  timestamp(value: string): string {
    return formatTimestamp(value);
  }

  mentionLabel(value: boolean | null | undefined): string {
    return yesNo(value);
  }

  positionLabel(value: number | null | undefined): string {
    return formatPosition(value);
  }

  alignmentLabel(value: number | null | undefined): string {
    return formatAlignment(value);
  }

  latencyLabel(value: number | null | undefined): string {
    return formatLatency(value);
  }

  summaryHasQueries(view: QueryExplorerView): boolean {
    return (view.summary?.total_queries ?? 0) > 0;
  }

  summaryResponsesMissing(view: QueryExplorerView): boolean {
    const summary = view.summary;
    return !!summary && summary.total_queries > 0 && summary.responses === 0;
  }

  noFilterMatches(view: QueryExplorerView): boolean {
    return this.filtersActive() && view.pagination.total === 0 && this.summaryHasQueries(view);
  }

  responseCoverage(view: QueryExplorerView): string {
    const summary = view.summary;
    if (!summary || summary.total_queries === 0) {
      return UNAVAILABLE;
    }
    return `${summary.responses} / ${summary.total_queries}`;
  }

  rangeLabel(view: QueryExplorerView): string {
    if (view.pagination.total === 0) {
      return '0 queries';
    }
    const start = (view.pagination.page - 1) * view.pagination.page_size + 1;
    const end = Math.min(view.pagination.page * view.pagination.page_size, view.pagination.total);
    return `Showing ${start}–${end} of ${view.pagination.total}`;
  }

  private applyFilters(): void {
    this.page.set(1);
    this.expandedId.set(null);
    this.load(true);
  }

  private resetFilterState(): void {
    this.search.set('');
    this.category.set('');
    this.responseStatus.set('');
    this.mention.set('');
    this.citation.set('');
  }

  private asTriState(value: string): TriState {
    if (value === 'true' || value === 'false') {
      return value;
    }
    return '';
  }

  private fetch(keepVisible: boolean) {
    const showSkeleton = !keepVisible || this.data() === null;
    if (showSkeleton) {
      this.status.set('loading');
      this.listBusy.set(false);
    } else {
      this.listBusy.set(true);
    }
    return this.api.getExplorerData(this.currentParams()).pipe(
      map((data) => ({ data, failed: false, httpStatus: 0 })),
      catchError((error: HttpErrorResponse) =>
        of({ data: null, failed: true, httpStatus: error.status ?? 0 }),
      ),
    );
  }

  private currentParams() {
    return {
      auditId: this.selectedAuditId() || null,
      category: this.category() || null,
      search: this.search().trim() || null,
      hasResponse: this.triStateParam(this.responseStatus()),
      brandMentioned: this.triStateParam(this.mention()),
      citationFound: this.triStateParam(this.citation()),
      page: this.page(),
      pageSize: this.pageSize(),
    };
  }

  private triStateParam(value: TriState): boolean | null {
    if (value === 'true') {
      return true;
    }
    if (value === 'false') {
      return false;
    }
    return null;
  }

  private applyResult(result: {
    data: QueryExplorerView | null;
    failed: boolean;
    httpStatus: number;
  }): void {
    this.listBusy.set(false);
    if (result.failed || result.data === null) {
      if (result.httpStatus === 401) {
        void this.router.navigate(['/login']);
        return;
      }
      this.httpStatus.set(result.httpStatus);
      this.errorMessage.set(
        result.httpStatus === 404
          ? 'That audit could not be found.'
          : "We couldn't load Query Explorer. Please try again.",
      );
      this.status.set('error');
      return;
    }
    this.data.set(result.data);
    this.status.set('ready');
    this.syncAuditUrl(result.data);
  }

  private syncAuditUrl(view: QueryExplorerView): void {
    const auditId = view.audit?.id;
    if (!auditId) {
      return;
    }
    const current = this.route.snapshot.queryParamMap.get('audit_id') ?? '';
    this.selectedAuditId.set(auditId);
    if (current === auditId) {
      return;
    }
    void this.router.navigate(['/query-explorer'], {
      queryParams: { audit_id: auditId },
      replaceUrl: true,
    });
  }
}
