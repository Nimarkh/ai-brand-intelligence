import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ReportDetail, ReportList } from './reports.models';

@Injectable({ providedIn: 'root' })
export class ReportsService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  list(auditId?: string | null): Observable<ReportList> {
    let params = new HttpParams();
    if (auditId) {
      params = params.set('audit_id', auditId);
    }
    return this.http.get<ReportList>(`${this.apiBaseUrl}/reports`, { params });
  }

  create(auditId: string): Observable<ReportDetail> {
    return this.http.post<ReportDetail>(`${this.apiBaseUrl}/reports`, { audit_id: auditId });
  }

  get(reportId: string): Observable<ReportDetail> {
    return this.http.get<ReportDetail>(`${this.apiBaseUrl}/reports/${reportId}`);
  }

  download(reportId: string): Observable<Blob> {
    return this.http.get(`${this.apiBaseUrl}/reports/${reportId}/download`, { responseType: 'blob' });
  }
}
