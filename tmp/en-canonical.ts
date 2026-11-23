import type { Locale } from '../appInfo'

/* Translation resources for English, Hindi and Telugu.
   Rules:
   - Flat dot-separated keys; `en` is the source of truth for the key set.
   - `hi` and `te` are typed against `en`, so a missing key is a TYPE ERROR.
   - No string here may present fake prices, fake buyers, fake forecasts or
     fake statistics. Placeholders are labelled as placeholders.
   - {placeholders} are substituted by `t(key, params)`. */

const en = {
  'common.brandName': 'AgriPredict AI',
  'common.brandTagline': 'Market intelligence that helps you decide when, where and who to sell to',
  'common.skipToContent': 'Skip to main content',
  'common.languageLabel': 'Language',
  'common.menuOpen': 'Menu',
  'common.menuClose': 'Close menu',
  'common.footerText':
    'AgriPredict AI - foundation phase - no live market prices, forecasts or listings are shown yet',

  'nav.home': 'Home',
  'nav.dashboard': 'Dashboard',

  'landing.hero.eyebrow': 'A farmer-first intelligence platform',
  'landing.hero.title': 'Sell smarter, with honest numbers',
  'landing.hero.subtitle':
    'AgriPredict AI helps farmers answer four questions: when to sell, where to sell, who to sell to, and what you will actually keep after transport, storage and handling costs.',
  'landing.hero.ctaDashboard': 'Open dashboard',
  'landing.hero.ctaLearnMore': 'See how it helps',

  'landing.how.title': 'Four decisions, one platform',
  'landing.how.subtitle': 'Every feature is built around a decision a farmer actually faces.',

  'landing.tile.market.title': 'Market Intelligence',
  'landing.tile.market.body': 'Understand prices, trends and potential selling opportunities across multiple mandis.',
  'landing.tile.marketplace.title': 'Marketplace',
  'landing.tile.marketplace.body': 'Connect directly with buyers and negotiate the best prices for your produce.',
  'landing.tile.logistics.title': 'Logistics',
  'landing.tile.logistics.body': 'Find reliable transport providers and get your produce to market efficiently.',
  'landing.tile.storage.title': 'Storage',
  'landing.tile.storage.body': 'Discover storage facilities near you to preserve your produce until the right time.',
  'landing.tile.schemes.title': 'Government Schemes',
  'landing.tile.schemes.body': 'Find agricultural schemes that may apply to your farm with explainable eligibility.',
  'landing.tile.ai.title': 'AI Assistant',
  'landing.tile.ai.body': 'Get personalized guidance with AgriMitra AI, your intelligent farming assistant.',

  'landing.how.when.title': 'When to sell',
  'landing.how.when.body':
    'Compare observed market prices over time, with the source and date of every figure. Forecasts appear only after they are validated.',
  'landing.how.where.title': 'Where to sell',
  'landing.how.where.body':
    'Compare mandis by what you actually keep after transport and other costs - not just the headline price.',
  'landing.how.who.title': 'Who to sell to',
  'landing.how.who.body':
    'Discover buyers whose requirements match your produce, with every match explained in plain language.',
  'landing.how.net.title': 'What you will keep',
  'landing.how.net.body':
    'A transparent net-realization calculator shows the full formula, every cost, and whether a number is a confirmed quote or your own estimate.',

  'landing.roles.eyebrow': 'One platform, every role in the chain',
  'landing.roles.title': 'Built for everyone in the chain',
  'landing.roles.farmer.name': 'Farmer',
  'landing.roles.farmer.body':
    'Create produce lots, receive offers, and see what you will actually keep.',
  'landing.roles.buyer.name': 'Buyer / trader',
  'landing.roles.buyer.body':
    'Post purchase requirements, find supply, and negotiate with a clear record.',
  'landing.roles.transport.name': 'Transport provider',
  'landing.roles.transport.body':
    'List vehicles and rates, send quotes, and manage bookings.',
  'landing.roles.storage.name': 'Storage provider',
  'landing.roles.storage.body':
    'Register warehouse capacity, quote storage requests, and manage bookings.',
  'landing.roles.admin.name': 'Administrator',
  'landing.roles.admin.body':
    'Review listings, manage reference data, and view audit logs.',
  'landing.roles.explore': 'View dashboard',

  'landing.status.title': 'System status',
  'landing.status.checking': 'Checking the backend...',
  'landing.status.ok': 'Connected - version {version}, environment {environment}',
  'landing.status.error': 'Not connected: {message}',
  'landing.status.retry': 'Check again',

  'landing.honesty.eyebrow': 'Honest by design',
  'landing.honesty.title': 'Honest by design',
  'landing.honesty.body':
    'This platform never shows simulated prices, fake buyers or invented forecasts as if they were real. Every figure will carry its source, date and freshness. Data integrations arrive in later phases.',

  'dash.title': 'Dashboard',
  'dash.subtitle': 'Role-aware workspace',
  'dash.selectRole.title': 'Choose a role to preview',
  'dash.selectRole.body':
    'Roles are assigned during sign-up. This preview exists so each shell can be reviewed before authentication is built.',
  'dash.role.farmer.title': 'Farmer dashboard',
  'dash.role.farmer.body':
    'Your produce lots, offers received and net-realization tools will appear here (built in Phase 6).',
  'dash.role.buyer.title': 'Buyer dashboard',
  'dash.role.buyer.body':
    'Your purchase requirements, matched lots and offers you have sent will appear here (built in Phase 7).',
  'dash.role.transport.title': 'Transport dashboard',
  'dash.role.transport.body':
    'Your vehicles, pricing and incoming quote requests will appear here (built in Phase 9).',
  'dash.role.storage.title': 'Storage dashboard',
  'dash.role.storage.body':
    'Your facilities, capacity and storage requests will appear here (built in Phase 10).',
  'dash.role.admin.title': 'Admin dashboard',
  'dash.role.admin.body':
    'Moderation queues, data imports and audit logs will appear here (built in Phase 15).',
  'dash.placeholderBadge': 'Coming in a later phase',
  'dash.empty.title': 'Nothing here yet',
  'dash.empty.body':
    'This screen has no data. It fills up when the phase listed above is implemented and tested - we never show placeholder numbers as real.',
  'dash.backToHome': 'Back to home',

  'state.loading': 'Loading...',
  'state.error.title': 'Something went wrong',
  'state.error.body': 'The action could not be completed. Please try again.',
  'state.error.retry': 'Try again',
  'state.empty.title': 'Nothing to show',
  'state.empty.body': 'There is no data to display yet.',
  'state.success.title': 'Done',

  'error.notFound.title': 'Page not found',
  'error.notFound.body': 'The address you opened does not exist in this version of the app.',
  'error.notFound.home': 'Go to home',
}
