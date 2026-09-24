import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.owner_setup import router as owner_setup_router
from app.api.routes.auth import router as auth_router
from app.api.routes.test_auth import router as test_auth_router
from app.api.routes.admin_setup import router as admin_setup_router
from app.api.routes.admin_management import router as admin_management_router
from app.api.routes.user_management import router as user_management_router
from app.api.routes.workspaces import router as workspace_router
from app.api.routes.file_group import router as file_group_router
from app.api.routes.permission import router as permission_router
from app.api.routes.access_request import router as access_request_router
from app.api.routes.data_source_credential import (
    router as data_source_credential_router,
)
from app.api.routes.connector import router as connector_router
from app.connectors.registration import register_all_connectors


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


register_all_connectors()


app = FastAPI(
    title="DataEase API",
    description="Backend API for DataEase",
    version="1.0.0",
)


# ============================================================
# TEMPORARY DIAGNOSTIC — allow_origins=["*"]
#
# This is deliberately wide open so we can find out, with one
# deploy, whether CORSMiddleware is working AT ALL on this
# service. If the CORS error disappears with this in place, the
# middleware is fine and the previous problem was specifically
# the CORS_ORIGINS value not matching the frontend's origin.
# If the CORS error is STILL there even with "*", something more
# fundamental is wrong (this file isn't actually what's deployed,
# the deploy didn't pick up the change, etc.) — tell Claude that
# result and do not keep guessing at CORS_ORIGINS values.
#
# ONCE CONFIRMED WORKING: replace allow_origins=["*"] below with
# the DEFAULT_ORIGINS + EXTRA_ORIGINS version (ask Claude to give
# you that file back) — a real deployment should never allow every
# origin in the world to call it with credentials enabled.
# ============================================================

DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

EXTRA_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

logger.info(
    "CORS_ORIGINS env var resolved to: %r",
    EXTRA_ORIGINS,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Something went wrong on the server. "
                "Please try again, or contact support if it continues."
            ),
        },
    )


app.include_router(owner_setup_router)
app.include_router(auth_router)
app.include_router(test_auth_router)
app.include_router(admin_setup_router)
app.include_router(admin_management_router)
app.include_router(user_management_router)
app.include_router(workspace_router)
app.include_router(file_group_router)
app.include_router(permission_router)
app.include_router(access_request_router)
app.include_router(data_source_credential_router)
app.include_router(connector_router)


@app.get("/")
def root():
    return {
        "message": "DataEase API is running"
    }