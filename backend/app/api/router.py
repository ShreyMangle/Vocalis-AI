"""
app/api/router.py — Main API Router

CONCEPT: Router Composition
============================
Instead of registering ALL routes in main.py (messy),
we create separate routers for each feature and include them here.

main.py includes this router once.
This router includes feature routers.

Structure:
  main.py
    └── api_router (prefix=/api/v1)
          ├── auth.router    → /api/v1/auth/...
          ├── agents.router  → /api/v1/agents/...   (Week 4)
          ├── calls.router   → /api/v1/calls/...    (Week 9)
          └── ...

Adding a new feature:
  1. Create app/api/v1/feature.py with a router
  2. Import and include it here
  3. Done — main.py doesn't need to change
"""

from fastapi import APIRouter

from app.api.v1 import auth

api_router = APIRouter(prefix="/api/v1")

# Auth routes: /api/v1/auth/register, /api/v1/auth/login, etc.
api_router.include_router(auth.router)

# Future routers (uncomment as we build them):
# from app.api.v1 import business
# api_router.include_router(business.router)   # Week 3

# from app.api.v1 import agents
# api_router.include_router(agents.router)     # Week 4

# from app.api.v1 import knowledge
# api_router.include_router(knowledge.router)  # Week 5

# from app.api.v1 import calls
# api_router.include_router(calls.router)      # Week 9
