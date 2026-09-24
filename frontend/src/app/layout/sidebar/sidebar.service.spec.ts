import { TestBed } from '@angular/core/testing';

import { SIDEBAR_STORAGE_KEY, SidebarService } from './sidebar.service';

describe('SidebarService', () => {
  beforeEach(() => {
    localStorage.removeItem(SIDEBAR_STORAGE_KEY);
    TestBed.configureTestingModule({});
  });

  afterEach(() => {
    localStorage.removeItem(SIDEBAR_STORAGE_KEY);
  });

  it('starts expanded', () => {
    const service = TestBed.inject(SidebarService);

    expect(service.isCollapsed()).toBeFalse();
    expect(service.collapsed()).toBeFalse();
  });

  it('toggles and persists the collapsed state', () => {
    const service = TestBed.inject(SidebarService);

    service.toggleCollapsed();

    expect(service.isCollapsed()).toBeTrue();
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe('true');

    service.toggleCollapsed();

    expect(service.isCollapsed()).toBeFalse();
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe('false');
  });

  it('restores a collapsed preference', () => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, 'true');

    const service = TestBed.inject(SidebarService);

    expect(service.isCollapsed()).toBeTrue();
  });

  it('opens and closes the mobile drawer', () => {
    const service = TestBed.inject(SidebarService);

    service.openMobile();
    expect(service.mobileOpen()).toBeTrue();

    service.closeMobile();
    expect(service.mobileOpen()).toBeFalse();

    service.toggleMobile();
    expect(service.mobileOpen()).toBeTrue();
  });
});
