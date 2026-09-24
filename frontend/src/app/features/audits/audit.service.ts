import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AuditListResponse,
  AuditScoreResponse,
  AuditSummary,
  CrawlResponse,
  SeoAnalyzeResponse,
  SeoFindingListResponse,
} from './audit.models';

@Injectable({ providedIn: 'root' })
export class AuditService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  listAudits(brandId: string): Observable<AuditListResponse> {
    return this.http.get<AuditListResponse>(`${this.apiBaseUrl}/brands/${brandId}/audits`);
  }

  getAudit(auditId: string): Observable<AuditSummary> {
    return this.http.get<AuditSummary>(`${this.apiBaseUrl}/audits/${auditId}`);
  }

  createAudit(brandId: string): Observable<AuditSummary> {
    return this.http.post<AuditSummary>(`${this.apiBaseUrl}/brands/${brandId}/audits`, {});
  }

  crawl(auditId: string): Observable<CrawlResponse> {
    return this.http.post<CrawlResponse>(`${this.apiBaseUrl}/audits/${auditId}/crawl`, {});
  }

  analyzeSeo(auditId: string): Observable<SeoAnalyzeResponse> {
    return this.http.post<SeoAnalyzeResponse>(`${this.apiBaseUrl}/audits/${auditId}/analyze-seo`, {});
  }

  listSeoFindings(auditId: string): Observable<SeoFindingListResponse> {
    return this.http.get<SeoFindingListResponse>(`${this.apiBaseUrl}/audits/${auditId}/seo-findings`);
  }

  calculateScore(auditId: string): Observable<AuditScoreResponse> {
    return this.http.post<AuditScoreResponse>(`${this.apiBaseUrl}/audits/${auditId}/calculate-score`, {});
  }

  getScore(auditId: string): Observable<AuditScoreResponse> {
    return this.http.get<AuditScoreResponse>(`${this.apiBaseUrl}/audits/${auditId}/score`);
  }
}
