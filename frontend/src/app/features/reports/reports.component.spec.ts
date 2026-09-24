import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { of, throwError } from 'rxjs';

import { ReportDetailComponent } from './report-detail.component';
import { ReportsComponent } from './reports.component';
import { ReportDetail, ReportList, ReportListItem, ReportStatus } from './reports.models';
import { ReportsService } from './reports.service';

const auditId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const reportId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';

const completedAudit = {
  id: auditId,
  brand_name: 'Acme',
  created_at: '2026-09-23T12:00:00Z',
  completed_at: '2026-09-23T12:00:00Z',
};

const emptyPage: ReportList = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  completed_audits: [completedAudit],
};

function item(status: ReportStatus, id = reportId): ReportListItem {
  return {
    id,
    audit_id: auditId,
    brand_name: 'Acme',
    title: 'Acme — Audit Intelligence Report',
    status,
    created_at: '2026-09-23T13:00:00Z',
    completed_at: status === 'GENERATING' ? null : '2026-09-23T13:05:00Z',
    audit_date: '2026-09-23T12:00:00Z',
  };
}

function pageWith(status: ReportStatus): ReportList {
  return { ...emptyPage, items: [item(status)], total: 1 };
}

const readyDetail: ReportDetail = {
  id: reportId,
  audit_id: auditId,
  brand_name: 'Acme',
  website: 'https://acme.example',
  title: 'Acme — Audit Intelligence Report',
  status: 'READY',
  created_at: '2026-09-23T13:00:00Z',
  completed_at: '2026-09-23T13:05:00Z',
  audit_date: '2026-09-23T12:00:00Z',
  generated_at: '2026-09-23T13:05:00Z',
  overall_score: 72,
  overall_status: 'PROVISIONAL',
  overall_note: 'Some scoring dimensions are not yet available, so the overall score uses the available components.',
  scores: [
    { key: 'overall', label: 'Overall', score: 72, status: 'PROVISIONAL' },
    { key: 'website_health', label: 'Website Health', score: 80, status: 'AVAILABLE' },
    { key: 'ai_visibility', label: 'AI Visibility', score: null, status: 'UNAVAILABLE' },
  ],
  sections: ['Executive Summary', 'Website Health', 'Methodology'],
  message: null,
};

describe('ReportsComponent', () => {
  let fixture: ComponentFixture<ReportsComponent>;
  let api: jasmine.SpyObj<ReportsService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj('ReportsService', ['list', 'create', 'get', 'download']);
    api.list.and.returnValue(of(emptyPage));
    await TestBed.configureTestingModule({
      imports: [ReportsComponent],
      providers: [provideRouter([]), { provide: ReportsService, useValue: api }],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(ReportsComponent);
    fixture.detectChanges();
  }

  it('shows the empty state and opens the audit selector', () => {
    create();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('No reports yet.');
    expect(text).toContain('Generate a report from a completed audit.');

    clickButton('Generate Report');
    fixture.detectChanges();

    const select = fixture.nativeElement.querySelector('select') as HTMLSelectElement;
    expect(select).not.toBeNull();
    expect(select.textContent).toContain('Acme');
    expect(select.textContent).toContain('Sep 23, 2026');
    expect(fixture.nativeElement.textContent).toContain('Cancel');
  });

  it('generates a report for the selected audit', () => {
    api.create.and.returnValue(of({ ...readyDetail, status: 'READY' }));
    api.list.and.returnValues(of(emptyPage), of(pageWith('READY')));
    create();
    clickButton('Generate Report');
    fixture.detectChanges();
    const generateButtons = buttons().filter((button) => button.textContent?.includes('Generate Report'));
    generateButtons[generateButtons.length - 1].click();
    fixture.detectChanges();

    expect(api.create).toHaveBeenCalledWith(auditId);
    expect(fixture.nativeElement.textContent).toContain('Ready');
    expect(fixture.nativeElement.textContent).toContain('Download');
  });

  it('explains when the audit cannot produce a report', () => {
    api.create.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 422, error: { detail: 'Complete the audit before generating a report.' } })),
    );
    create();
    clickButton('Generate Report');
    fixture.detectChanges();
    const generateButtons = buttons().filter((button) => button.textContent?.includes('Generate Report'));
    generateButtons[generateButtons.length - 1].click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Complete the audit before generating a report.');
  });

  it('shows a generating report without a download action', () => {
    api.list.and.returnValue(of(pageWith('GENERATING')));
    create();
    expect(fixture.nativeElement.textContent).toContain('Generating…');
    expect(buttons().some((button) => button.textContent?.includes('Download'))).toBeFalse();
  });

  it('shows a ready report with view and download', () => {
    api.list.and.returnValue(of(pageWith('READY')));
    api.download.and.returnValue(of(new Blob(['%PDF'], { type: 'application/pdf' })));
    create();
    expect(fixture.nativeElement.textContent).toContain('View');
    clickButton('Download');
    expect(api.download).toHaveBeenCalledWith(reportId);
  });

  it('retries a failed report as a new snapshot', () => {
    api.list.and.returnValue(of(pageWith('FAILED')));
    api.create.and.returnValue(of({ ...readyDetail, id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', status: 'READY' }));
    create();
    expect(fixture.nativeElement.textContent).toContain('Failed');
    clickButton('Try again');
    expect(api.create).toHaveBeenCalledWith(auditId);
  });

  it('shows an error state when the list cannot be loaded', () => {
    api.list.and.returnValue(throwError(() => new HttpErrorResponse({ status: 500 })));
    create();
    expect(fixture.nativeElement.textContent).toContain('Reports could not be loaded. Please try again.');
    api.list.and.returnValue(of(emptyPage));
    clickButton('Retry');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No reports yet.');
  });

  it('keeps the page readable in dark mode', () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    create();
    const page = fixture.nativeElement.querySelector('.reports-page') as HTMLElement;
    const background = getComputedStyle(page).backgroundColor;
    expect(background).not.toBe('');
    expect(background).not.toBe('rgba(0, 0, 0, 0)');
    document.documentElement.setAttribute('data-theme', 'light');
  });

  it('uses a responsive report layout', () => {
    api.list.and.returnValue(of(pageWith('READY')));
    create();
    const table = fixture.nativeElement.querySelector('.reports-table') as HTMLElement;
    expect(table).not.toBeNull();
    const css = Array.from(document.styleSheets)
      .flatMap((sheet) => {
        try {
          return Array.from(sheet.cssRules).map((rule) => rule.cssText);
        } catch {
          return [];
        }
      })
      .join('\n');
    expect(css).toContain('max-width: 720px');
    expect(css).toContain('.reports-table');
  });

  function buttons(): HTMLButtonElement[] {
    return Array.from(fixture.nativeElement.querySelectorAll('button'));
  }

  function clickButton(label: string): void {
    const button = buttons().find((candidate) => candidate.textContent?.includes(label));
    expect(button).withContext(label).toBeDefined();
    button?.click();
    fixture.detectChanges();
  }
});

describe('ReportDetailComponent', () => {
  let root: HTMLElement;
  let api: jasmine.SpyObj<ReportsService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj('ReportsService', ['list', 'create', 'get', 'download']);
    api.get.and.returnValue(of(readyDetail));
    await TestBed.configureTestingModule({
      providers: [
        provideRouter([
          { path: 'reports/:id', component: ReportDetailComponent },
          { path: 'reports', component: ReportsComponent },
        ]),
        { provide: ReportsService, useValue: api },
      ],
    }).compileComponents();
  });

  async function open(detail: ReportDetail = readyDetail): Promise<void> {
    api.get.and.returnValue(of(detail));
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/reports/${reportId}`, ReportDetailComponent);
    harness.detectChanges();
    root = harness.fixture.nativeElement as HTMLElement;
  }

  it('shows the report summary and download action', async () => {
    await open();
    const text = root.textContent ?? '';
    expect(text).toContain('Acme');
    expect(text).toContain('Sep 23, 2026');
    expect(text).toContain('Ready');
    expect(text).toContain('72 / 100');
    expect(text).toContain('Provisional');
    expect(text).toContain('Not available');
    expect(text).toContain('Executive Summary');
    expect(text).toContain('Download PDF');

    api.download.and.returnValue(of(new Blob(['%PDF'], { type: 'application/pdf' })));
    const button = Array.from(root.querySelectorAll('button')).find((candidate) =>
      candidate.textContent?.includes('Download PDF'),
    ) as HTMLButtonElement;
    button.click();
    expect(api.download).toHaveBeenCalledWith(reportId);
  });

  it('hides download while a report is generating', async () => {
    await open({ ...readyDetail, status: 'GENERATING', scores: [], sections: [] });
    expect(root.textContent).toContain('Generating…');
    expect(root.textContent).not.toContain('Download PDF');
  });

  it('retries a failed report without replacing the old record in place', async () => {
    await open({ ...readyDetail, status: 'FAILED', scores: [], sections: [], message: null });
    api.create.and.returnValue(of({ ...readyDetail, id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd' }));
    const button = Array.from(root.querySelectorAll('button')).find((candidate) =>
      candidate.textContent?.includes('Try again'),
    ) as HTMLButtonElement;
    button.click();
    expect(api.create).toHaveBeenCalledWith(auditId);
  });

  it('shows an error when the report cannot be loaded', async () => {
    api.get.and.returnValue(throwError(() => new HttpErrorResponse({ status: 404 })));
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl(`/reports/${reportId}`, ReportDetailComponent);
    harness.detectChanges();
    expect((harness.fixture.nativeElement as HTMLElement).textContent).toContain('This report could not be found.');
  });
});
