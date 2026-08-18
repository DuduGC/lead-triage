import logging
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_settings, require_api_key
from app.api.errors import ApiError
from app.api.middleware import BodySizeLimitMiddleware
from app.config import Settings
from app.integrations.gemini import GeminiExtractor
from app.logging_config import configure_logging, log_event
from app.persistence.database import create_engine_from_settings, create_session_factory
from app.schemas.lead import (
    Classification,
    LeadCreateRequest,
    LeadListResponse,
    LeadResponse,
    ProcessingStatus,
)
from app.services.lead_service import LeadService

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": _request_id(request),
            }
        },
    )


def _build_service(application: FastAPI, settings: Settings) -> LeadService:
    engine = create_engine_from_settings(settings)
    application.state.engine = engine
    session_factory = create_session_factory(engine)
    extractor = GeminiExtractor.from_settings(settings)
    return LeadService(session_factory=session_factory, extractor=extractor)


def _get_service(request: Request) -> LeadService:
    service = request.app.state.lead_service
    if service is None:
        settings = request.app.state.settings or get_settings()
        service = _build_service(request.app, settings)
        request.app.state.lead_service = service
    return service


def create_app(*, service: LeadService | None = None, settings: Settings | None = None) -> FastAPI:
    configure_logging(settings.log_level if settings else "INFO")

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        engine = getattr(application.state, "engine", None)
        if engine is not None:
            engine.dispose()

    application = FastAPI(
        title="Lead Triage API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.lead_service = service
    application.state.settings = settings
    application.state.engine = None
    application.add_middleware(
        BodySizeLimitMiddleware,
        max_body_bytes=settings.max_body_bytes if settings else 16_384,
    )

    if settings is not None:
        application.dependency_overrides[get_settings] = lambda: settings

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return _error_response(request, exc.status_code, exc.code, exc.message)

    @application.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        del exc
        return _error_response(
            request,
            422,
            "VALIDATION_ERROR",
            "Invalid request",
        )

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return _error_response(
                request,
                status.HTTP_401_UNAUTHORIZED,
                "AUTHENTICATION_REQUIRED",
                "Authentication required",
            )
        return _error_response(
            request,
            exc.status_code,
            "HTTP_ERROR",
            "Request could not be processed",
        )

    @application.post(
        "/leads",
        response_model=LeadResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_lead(
        payload: LeadCreateRequest,
        request: Request,
        _: Annotated[None, Depends(require_api_key)],
    ) -> LeadResponse:
        try:
            return _get_service(request).create(payload, request_id=_request_id(request))
        except SQLAlchemyError as error:
            log_event(
                logger,
                "database_error",
                request_id=_request_id(request),
                error_type=type(error).__name__,
            )
            raise ApiError(503, "DATABASE_UNAVAILABLE", "Database unavailable") from error
        except Exception as error:
            log_event(
                logger,
                "unexpected_error",
                request_id=_request_id(request),
                error_type=type(error).__name__,
            )
            raise ApiError(500, "INTERNAL_ERROR", "Internal server error") from error

    @application.get("/leads", response_model=LeadListResponse)
    def list_leads(
        request: Request,
        _: Annotated[None, Depends(require_api_key)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        classificacao: Classification | None = None,
        status_filter: Annotated[ProcessingStatus | None, Query(alias="status")] = None,
    ) -> LeadListResponse:
        try:
            items, total = _get_service(request).list(
                limit=limit,
                offset=offset,
                classificacao=classificacao,
                status=status_filter,
            )
            return LeadListResponse(items=items, total=total, limit=limit, offset=offset)
        except SQLAlchemyError as error:
            log_event(
                logger,
                "database_error",
                request_id=_request_id(request),
                error_type=type(error).__name__,
            )
            raise ApiError(503, "DATABASE_UNAVAILABLE", "Database unavailable") from error
        except Exception as error:
            log_event(
                logger,
                "unexpected_error",
                request_id=_request_id(request),
                error_type=type(error).__name__,
            )
            raise ApiError(500, "INTERNAL_ERROR", "Internal server error") from error

    @application.get("/leads/{lead_id}", response_model=LeadResponse)
    def get_lead(
        lead_id: UUID,
        request: Request,
        _: Annotated[None, Depends(require_api_key)],
    ) -> LeadResponse:
        try:
            response = _get_service(request).get(lead_id)
            if response is None:
                raise ApiError(404, "LEAD_NOT_FOUND", "Lead not found")
            return response
        except ApiError:
            raise
        except SQLAlchemyError as error:
            log_event(
                logger,
                "database_error",
                request_id=_request_id(request),
                error_type=type(error).__name__,
            )
            raise ApiError(503, "DATABASE_UNAVAILABLE", "Database unavailable") from error
        except Exception as error:
            log_event(
                logger,
                "unexpected_error",
                request_id=_request_id(request),
                error_type=type(error).__name__,
            )
            raise ApiError(500, "INTERNAL_ERROR", "Internal server error") from error

    return application


app = create_app()
