from dependency_injector import containers, providers

from core.config import settings

from src.onboarding_bc.process_suggestion.infrastructure.services import (
    GroqSuggestionService,
    FallbackSuggestionService,
)
from src.onboarding_bc.process_suggestion.application.queries import (
    SuggestProcessesHandler,
)
from src.onboarding_bc.process_suggestion.application.commands import (
    CompleteOnboardingHandler,
)
from src.onboarding_bc.department_suggestion.infrastructure.services import (
    GroqDepartmentSuggestionService,
    FallbackDepartmentSuggestionService,
)
from src.onboarding_bc.department_suggestion.application.queries import (
    SuggestDepartmentsHandler,
)


class OnboardingContainer(containers.DeclarativeContainer):
    """Dependency injection container for Onboarding bounded context.

    Handler naming convention for CommandBus/QueryBus:
    - CompleteOnboardingCommand -> complete_onboarding_command_handler
    - SuggestProcessesQuery -> suggest_processes_query_handler
    - SuggestDepartmentsQuery -> suggest_departments_query_handler
    """

    # External dependencies (injected from main container)
    config = providers.Configuration()
    database = providers.Dependency()

    # External repository dependencies
    organization_repository = providers.Dependency()
    business_process_repository = providers.Dependency()
    department_repository = providers.Dependency()
    mapping_repository = providers.Dependency()

    # Services
    groq_suggestion_service = providers.Singleton(
        GroqSuggestionService,
        api_key=config.groq.api_key,
        model=config.groq.model,
        timeout=config.groq.timeout,
        max_tokens=config.groq.max_tokens,
        temperature=config.groq.temperature,
    )

    fallback_suggestion_service = providers.Singleton(
        FallbackSuggestionService
    )

    # Department Suggestion Services
    groq_department_suggestion_service = providers.Singleton(
        GroqDepartmentSuggestionService,
        api_key=config.groq.api_key,
        model=config.groq.model,
        timeout=15,  # Slightly longer timeout for department suggestions
        max_tokens=1500,  # More tokens needed for department + process mappings
        temperature=config.groq.temperature,
    )

    fallback_department_suggestion_service = providers.Singleton(
        FallbackDepartmentSuggestionService
    )

    # ===== Command Handlers =====
    complete_onboarding_command_handler = providers.Factory(
        CompleteOnboardingHandler,
        organization_repository=organization_repository,
        business_process_repository=business_process_repository,
        department_repository=department_repository,
        mapping_repository=mapping_repository,
    )

    # ===== Query Handlers =====
    suggest_processes_query_handler = providers.Factory(
        SuggestProcessesHandler,
        ai_service=groq_suggestion_service,
        fallback_service=fallback_suggestion_service
    )

    suggest_departments_query_handler = providers.Factory(
        SuggestDepartmentsHandler,
        ai_service=groq_department_suggestion_service,
        fallback_service=fallback_department_suggestion_service
    )
