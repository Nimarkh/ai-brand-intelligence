import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';
import { LoginComponent } from './features/auth/login/login.component';
import { RegisterComponent } from './features/auth/register/register.component';
import { ShellComponent } from './layout/shell/shell.component';

export const routes: Routes = [
  {
    path: 'login',
    component: LoginComponent,
    data: { title: 'Sign in' },
  },
  {
    path: 'register',
    component: RegisterComponent,
    data: { title: 'Create account' },
  },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
        data: { title: 'Dashboard', section: 'Overview' },
      },
      {
        path: 'brands',
        loadComponent: () =>
          import('./features/brands/brands.component').then((m) => m.BrandsComponent),
        data: { title: 'Brands', section: 'Intelligence' },
      },
      {
        path: 'brands/new',
        loadComponent: () =>
          import('./features/brands/brand-form.component').then((m) => m.BrandFormComponent),
        data: { title: 'Add brand', section: 'Intelligence', mode: 'create' },
      },
      {
        path: 'brands/:id/edit',
        loadComponent: () =>
          import('./features/brands/brand-form.component').then((m) => m.BrandFormComponent),
        data: { title: 'Edit brand', section: 'Intelligence', mode: 'edit' },
      },
      {
        path: 'brands/:id',
        loadComponent: () =>
          import('./features/brands/brand-detail.component').then((m) => m.BrandDetailComponent),
        data: { title: 'Brand', section: 'Intelligence' },
      },
      {
        path: 'audits',
        loadComponent: () =>
          import('./features/audits/audits.component').then((m) => m.AuditsComponent),
        data: { title: 'Audits', section: 'Intelligence' },
      },
      {
        path: 'audits/:id',
        loadComponent: () =>
          import('./features/audits/audit-detail.component').then((m) => m.AuditDetailComponent),
        data: { title: 'Audit', section: 'Intelligence' },
      },
      {
        path: 'website-audit',
        loadComponent: () =>
          import('./features/website-audit/website-audit.component').then(
            (m) => m.WebsiteAuditComponent,
          ),
        data: { title: 'Website audit', section: 'Intelligence' },
      },
      {
        path: 'ai-visibility',
        loadComponent: () =>
          import('./features/ai-visibility/ai-visibility.component').then(
            (m) => m.AiVisibilityComponent,
          ),
        data: { title: 'AI Visibility', section: 'Intelligence' },
      },
      {
        path: 'query-explorer',
        loadComponent: () =>
          import('./features/query-explorer/query-explorer.component').then(
            (m) => m.QueryExplorerComponent,
          ),
        data: { title: 'Query Explorer', section: 'Intelligence' },
      },
      {
        path: 'entity',
        loadComponent: () =>
          import('./features/entity/entity.component').then((m) => m.EntityComponent),
        data: { title: 'Entity Intelligence', section: 'Intelligence' },
      },
      {
        path: 'recommendations',
        loadComponent: () =>
          import('./features/recommendations/recommendations.component').then(
            (m) => m.RecommendationsComponent,
          ),
        data: { title: 'Recommendations', section: 'Optimization' },
      },
      {
        path: 'reports',
        loadComponent: () =>
          import('./features/reports/reports.component').then((m) => m.ReportsComponent),
        data: { title: 'Reports', section: 'Optimization' },
      },
      {
        path: 'reports/:id',
        loadComponent: () =>
          import('./features/reports/report-detail.component').then((m) => m.ReportDetailComponent),
        data: { title: 'Report', section: 'Optimization' },
      },
      {
        path: 'intelligence-chat',
        loadComponent: () =>
          import('./features/intelligence-chat/intelligence-chat.component').then(
            (m) => m.IntelligenceChatComponent,
          ),
        data: { title: 'Ask Intelligence', section: 'Workspace' },
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./features/settings/settings.component').then((m) => m.SettingsComponent),
        data: { title: 'Settings', section: 'System' },
      },
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
    ],
  },
  {
    path: '**',
    redirectTo: 'dashboard',
  },
];
