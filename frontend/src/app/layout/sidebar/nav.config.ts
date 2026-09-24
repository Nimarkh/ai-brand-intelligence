import { IconName } from '../../shared/components/icon/icon.component';

export interface NavItem {
  label: string;
  path: string;
  icon: IconName;
  exact?: boolean;
}

export interface NavSection {
  label: string;
  items: readonly NavItem[];
}

export const NAV_SECTIONS: readonly NavSection[] = [
  {
    label: 'Overview',
    items: [{ label: 'Dashboard', path: '/dashboard', icon: 'dashboard' }],
  },
  {
    label: 'Intelligence',
    items: [
      { label: 'Brands', path: '/brands', icon: 'brands', exact: false },
      { label: 'Audits', path: '/audits', icon: 'audits', exact: false },
      { label: 'AI Visibility', path: '/ai-visibility', icon: 'visibility' },
      { label: 'Query Explorer', path: '/query-explorer', icon: 'query' },
      { label: 'Entity Intelligence', path: '/entity', icon: 'entity' },
    ],
  },
  {
    label: 'Optimization',
    items: [
      { label: 'Recommendations', path: '/recommendations', icon: 'recommendations' },
      { label: 'Reports', path: '/reports', icon: 'reports', exact: false },
    ],
  },
  {
    label: 'Workspace',
    items: [{ label: 'Ask Intelligence', path: '/intelligence-chat', icon: 'chat' }],
  },
  {
    label: 'System',
    items: [{ label: 'Settings', path: '/settings', icon: 'settings' }],
  },
];
