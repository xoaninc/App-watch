from dependency_injector import containers, providers

from src.reporting_bc.report.infrastructure.repositories import ReportRepository
from src.reporting_bc.report.infrastructure.services import (
    S3StorageService,
    PDFGeneratorService,
    ReportDataCollector,
)

# Command Handlers
from src.reporting_bc.report.application.commands import (
    CreateReportHandler,
    RetryReportHandler,
    DeleteReportHandler,
)

# Query Handlers
from src.reporting_bc.report.application.queries import (
    GetReportHandler,
    ListReportsHandler,
    GetDownloadUrlHandler,
)


class ReportingContainer(containers.DeclarativeContainer):
    """Dependency injection container for Reporting bounded context.

    Handler naming convention for CommandBus/QueryBus:
    - CreateReportCommand -> create_report_command_handler
    - GetReportQuery -> get_report_query_handler
    """

    # Database session dependency (injected from main container)
    database = providers.Dependency()

    # External repository dependencies (injected from main container)
    assessment_repository = providers.Dependency()
    response_repository = providers.Dependency()
    gap_repository = providers.Dependency()
    ai_system_repository = providers.Dependency()
    organization_repository = providers.Dependency()

    # Repository singletons
    report_repository = providers.Factory(
        ReportRepository,
        session=database.provided.session
    )

    # Services
    s3_storage_service = providers.Singleton(S3StorageService)

    pdf_generator_service = providers.Singleton(PDFGeneratorService)

    report_data_collector = providers.Factory(
        ReportDataCollector,
        assessment_repository=assessment_repository,
        response_repository=response_repository,
        gap_repository=gap_repository,
        ai_system_repository=ai_system_repository,
        organization_repository=organization_repository,
    )

    # ===== Command Handlers =====
    create_report_command_handler = providers.Factory(
        CreateReportHandler,
        report_repository=report_repository,
        assessment_repository=assessment_repository
    )

    retry_report_command_handler = providers.Factory(
        RetryReportHandler,
        report_repository=report_repository
    )

    delete_report_command_handler = providers.Factory(
        DeleteReportHandler,
        report_repository=report_repository,
        s3_storage=s3_storage_service
    )

    # ===== Query Handlers =====
    get_report_query_handler = providers.Factory(
        GetReportHandler,
        report_repository=report_repository
    )

    list_reports_query_handler = providers.Factory(
        ListReportsHandler,
        report_repository=report_repository
    )

    get_download_url_query_handler = providers.Factory(
        GetDownloadUrlHandler,
        report_repository=report_repository,
        s3_storage=s3_storage_service
    )
