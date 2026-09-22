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


# Local development origins are always allowed. For a deployed
# frontend (for example on Vercel), set CORS_ORIGINS on the backend
# host to a comma-separated list, such as:
#   CORS_ORIGINS=https://your-app.vercel.app
DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

EXTRA_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=DEFAULT_ORIGINS + EXTRA_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# GLOBAL EXCEPTION HANDLER
#
# Any exception raised inside a route that ISN'T caught and turned
# into an HTTPException would otherwise be handled by Starlette's
# outermost error middleware, which sits OUTSIDE CORSMiddleware.
# That response never gets an Access-Control-Allow-Origin header,
# so the browser reports it as a CORS failure and hides the real
# error entirely.
#
# Registering a handler here runs INSIDE the middleware stack
# instead, so CORSMiddleware still gets to add its headers, and the
# frontend sees an honest "Request failed with status 500" instead
# of a misleading CORS error. The real exception is always logged
# here so it's visible in this server's logs (the terminal locally,
# or the Render service logs once deployed).
# ============================================================

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