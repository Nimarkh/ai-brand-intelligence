import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { QueryExplorerParams, QueryExplorerView } from './query-explorer.models';

@Injectable({ providedIn: 'root' })
export class QueryExplorerService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  getExplorerData(params: QueryExplorerParams = {}): Observable<QueryExplorerView> {
    let httpParams = new HttpParams()
      .set('page', String(params.page ?? 1))
      .set('page_size', String(params.pageSize ?? 20));

    if (params.auditId) {
      httpParams = httpParams.set('audit_id', params.auditId);
    }
    if (params.category) {
      httpParams = httpParams.set('category', params.category);
    }
    const search = params.search?.trim();
    if (search) {
      httpParams = httpParams.set('search', search);
    }
    if (params.hasResponse !== null && params.hasResponse !== undefined) {
      httpParams = httpParams.set('has_response', String(params.hasResponse));
    }
    if (params.brandMentioned !== null && params.brandMentioned !== undefined) {
      httpParams = httpParams.set('brand_mentioned', String(params.brandMentioned));
    }
    if (params.citationFound !== null && params.citationFound !== undefined) {
      httpParams = httpParams.set('citation_found', String(params.citationFound));
    }

    return this.http.get<QueryExplorerView>(`${this.apiBaseUrl}/query-explorer`, {
      params: httpParams,
    });
  }
}
