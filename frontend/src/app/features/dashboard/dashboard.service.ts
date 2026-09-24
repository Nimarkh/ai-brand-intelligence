import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { DashboardOverview } from './dashboard.models';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  getOverview(brandId?: string | null): Observable<DashboardOverview> {
    let params = new HttpParams();
    if (brandId) {
      params = params.set('brand_id', brandId);
    }
    return this.http.get<DashboardOverview>(`${this.apiBaseUrl}/dashboard/overview`, {
      params,
    });
  }
}
