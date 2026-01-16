from dependency_injector import containers, providers

from src.framework_bc.framework.infrastructure.repositories import FrameworkRepository
from src.framework_bc.framework.application.queries import (
    GetFrameworkQueryHandler,
    ListFrameworksQueryHandler,
    GetFrameworkFunctionsQueryHandler,
)


class FrameworkContainer(containers.DeclarativeContainer):
    """Dependency injection container for Framework bounded context."""

    # Database session dependency (injected from parent)
    database = providers.Dependency()

    # Repository
    framework_repository = providers.Factory(
        FrameworkRepository,
        session=database.provided.session
    )

    # Query Handlers (named in snake_case for QueryBus convention)
    get_framework_query_handler = providers.Factory(
        GetFrameworkQueryHandler,
        repository=framework_repository
    )

    list_frameworks_query_handler = providers.Factory(
        ListFrameworksQueryHandler,
        repository=framework_repository
    )

    get_framework_functions_query_handler = providers.Factory(
        GetFrameworkFunctionsQueryHandler,
        repository=framework_repository
    )
