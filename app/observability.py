"""
Observability module for CineAgent.

Sets up OpenTelemetry tracing with AWS X-Ray propagation.
Traces are exported to CloudWatch via the OTLP exporter or
printed to console for local development.

Usage:
    from app.observability import init_tracing, get_tracer
    init_tracing()
    tracer = get_tracer()
"""

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

_initialized = False


def init_tracing(service_name: str = "cineagent") -> None:
    """Initialize OpenTelemetry tracing.

    Configures a TracerProvider with AWS X-Ray compatible settings.
    Falls back to console export for local development.
    """
    global _initialized
    if _initialized:
        return

    try:
        resource = Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": "workshop",
        })

        provider = TracerProvider(resource=resource)

        # Try OTLP exporter for CloudWatch (via OTEL collector)
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info("OTLP tracing enabled: %s", otlp_endpoint)
            except Exception as e:
                logger.warning("OTLP exporter failed, using console: %s", e)
                provider.add_span_processor(
                    SimpleSpanProcessor(ConsoleSpanExporter())
                )
        else:
            # Console export for local development
            provider.add_span_processor(
                SimpleSpanProcessor(ConsoleSpanExporter())
            )
            logger.info("Console tracing enabled (set OTEL_EXPORTER_OTLP_ENDPOINT for CloudWatch)")

        trace.set_tracer_provider(provider)
        _initialized = True
        logger.info("Observability initialized for service: %s", service_name)

    except Exception as e:
        logger.warning("Failed to initialize tracing: %s. Continuing without.", e)


def get_tracer(name: str = "cineagent") -> trace.Tracer:
    """Get a tracer instance for creating spans."""
    return trace.get_tracer(name)
