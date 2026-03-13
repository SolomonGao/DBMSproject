"""API error handlers."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from gdelt_api.core.exceptions import GDELTAPIError
from gdelt_api.core.logging import get_logger
from gdelt_api.models.common import APIResponse, ErrorDetail

logger = get_logger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers with FastAPI app."""
    
    @app.exception_handler(GDELTAPIError)
    async def handle_api_error(request: Request, exc: GDELTAPIError) -> JSONResponse:
        """Handle custom API errors."""
        logger.warning(
            "api_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
        )
        
        response = APIResponse(
            success=False,
            error=ErrorDetail(
                code=exc.error_code,
                message=exc.message,
                detail=exc.error_detail,
                status=exc.status_code,
            ),
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """Handle HTTP exceptions."""
        logger.warning(
            "http_exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
        )
        
        response = APIResponse(
            success=False,
            error=ErrorDetail(
                code="HTTP_ERROR",
                message=str(exc.detail),
                status=exc.status_code,
            ),
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
        )
    
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Handle request validation errors."""
        errors = exc.errors()
        
        logger.warning(
            "validation_error",
            errors=errors,
            path=request.url.path,
        )
        
        # Format validation errors
        error_details = []
        for error in errors:
            loc = ".".join(str(x) for x in error.get("loc", []))
            error_details.append({
                "field": loc,
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            })
        
        response = APIResponse(
            success=False,
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                detail={"errors": error_details},
                status=422,
            ),
        )
        
        return JSONResponse(
            status_code=422,
            content=response.model_dump(),
        )
    
    @app.exception_handler(PydanticValidationError)
    async def handle_pydantic_error(
        request: Request,
        exc: PydanticValidationError,
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        logger.error(
            "pydantic_error",
            errors=exc.errors(),
            path=request.url.path,
        )
        
        response = APIResponse(
            success=False,
            error=ErrorDetail(
                code="DATA_VALIDATION_ERROR",
                message="Data validation failed",
                detail={"errors": exc.errors()},
                status=422,
            ),
        )
        
        return JSONResponse(
            status_code=422,
            content=response.model_dump(),
        )
    
    @app.exception_handler(Exception)
    async def handle_generic_error(request: Request, exc: Exception) -> JSONResponse:
        """Handle unhandled exceptions."""
        logger.exception(
            "unhandled_exception",
            error=str(exc),
            type=type(exc).__name__,
            path=request.url.path,
        )
        
        response = APIResponse(
            success=False,
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                status=500,
            ),
        )
        
        return JSONResponse(
            status_code=500,
            content=response.model_dump(),
        )
