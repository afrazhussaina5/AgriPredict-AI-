export const DASHBOARD_ROLES = ['farmer', 'buyer', 'transport', 'storage', 'admin'] as const

export type DashboardRole = (typeof DASHBOARD_ROLES)[number]

export function isDashboardRole(value: string): value is DashboardRole {
  return (DASHBOARD_ROLES as readonly string[]).includes(value)
}
