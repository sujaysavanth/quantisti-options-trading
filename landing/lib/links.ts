export const GITHUB_URL = 'https://github.com/sujaysavanth/quantisti-options-trading'
export const AUTHOR_URL = 'https://github.com/sujaysavanth'

/** Set NEXT_PUBLIC_DASHBOARD_URL to the deployed strategy dashboard; falls back to the repo. */
export const DASHBOARD_URL = process.env.NEXT_PUBLIC_DASHBOARD_URL || GITHUB_URL
export const HAS_DASHBOARD = Boolean(process.env.NEXT_PUBLIC_DASHBOARD_URL)
