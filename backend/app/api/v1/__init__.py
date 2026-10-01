"""
app/api/v1/__init__.py — API v1 package

CONCEPT: API Versioning
========================
We prefix all routes with /api/v1/.
WHY? Because when we make breaking changes to the API in the future,
we can release /api/v2/ without breaking existing clients using /api/v1/.

This is standard practice in production APIs (Stripe, Twilio, etc. all do this).
"""
