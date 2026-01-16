from dependency_injector import containers, providers

# Repositories
from src.assessment_bc.ai_system.infrastructure.repositories import AISystemRepository
from src.assessment_bc.business_process.infrastructure.repositories import BusinessProcessRepository
from src.assessment_bc.assessment.infrastructure.repositories import (
    AssessmentRepository, ResponseRepository, GapRepository
)
from src.assessment_bc.common_answer.infrastructure.repositories import CommonAnswerRepository
from src.assessment_bc.department_mapping.infrastructure.repositories import MappingRepository

# CommonAnswer Command Handlers
from src.assessment_bc.common_answer.application.commands import UpdateCommonAnswersHandler

# AI System Command Handlers
from src.assessment_bc.ai_system.application.commands import (
    CreateAISystemHandler, UpdateAISystemHandler,
    ArchiveAISystemHandler, RestoreAISystemHandler,
    DeleteAISystemHandler, AssignAISystemToProcessHandler,
)

# AI System Query Handlers
from src.assessment_bc.ai_system.application.queries import (
    GetAISystemHandler, ListAISystemsHandler, GetDashboardStatsHandler,
)

# Business Process Command Handlers
from src.assessment_bc.business_process.application.commands import (
    CreateBusinessProcessHandler, UpdateBusinessProcessHandler,
    DeleteBusinessProcessHandler,
)

# Business Process Query Handlers
from src.assessment_bc.business_process.application.queries import (
    GetBusinessProcessHandler, ListBusinessProcessesHandler,
    GetDashboardHandler,
)

# Assessment Command Handlers
from src.assessment_bc.assessment.application.commands import (
    CreateAssessmentHandler, DeleteAssessmentHandler,
    SaveResponseHandler, CompleteAssessmentHandler,
    AcknowledgeGapHandler, ResolveGapHandler,
    AcceptRiskHandler, ReopenGapHandler,
)

# Assessment Query Handlers
from src.assessment_bc.assessment.application.queries import (
    GetAssessmentHandler, ListAssessmentsHandler,
    GetAssessmentProgressHandler, GetQuestionsHandler,
    GetScoresHandler, GetResultsHandler,
    GetGapsHandler, GetGapHandler,
    GetGapSummaryHandler, GetAllGapsSummaryHandler,
    ListAllGapsHandler,
)

# Department Mapping Command/Query Handlers
from src.assessment_bc.department_mapping.application.commands import UpdateMappingsHandler
from src.assessment_bc.department_mapping.application.queries import GetMappingMatrixHandler


class AssessmentContainer(containers.DeclarativeContainer):
    """Dependency injection container for Assessment bounded context.

    Handler naming convention for CommandBus/QueryBus:
    - CreateAISystemCommand -> create_ai_system_command_handler
    - GetAISystemQuery -> get_ai_system_query_handler
    """

    # External dependencies (injected from main container)
    config = providers.Configuration()
    database = providers.Dependency()

    # ===== Repositories =====
    ai_system_repository = providers.Factory(
        AISystemRepository,
        session=database.provided.session
    )

    business_process_repository = providers.Factory(
        BusinessProcessRepository,
        session=database.provided.session
    )

    assessment_repository = providers.Factory(
        AssessmentRepository,
        session=database.provided.session
    )

    response_repository = providers.Factory(
        ResponseRepository,
        session=database.provided.session
    )

    gap_repository = providers.Factory(
        GapRepository,
        session=database.provided.session
    )

    common_answer_repository = providers.Factory(
        CommonAnswerRepository,
        session=database.provided.session
    )

    mapping_repository = providers.Factory(
        MappingRepository,
        session=database.provided.session
    )

    # ===== AI System Command Handlers =====
    create_ai_system_command_handler = providers.Factory(
        CreateAISystemHandler,
        ai_system_repository=ai_system_repository
    )

    update_ai_system_command_handler = providers.Factory(
        UpdateAISystemHandler,
        ai_system_repository=ai_system_repository
    )

    archive_ai_system_command_handler = providers.Factory(
        ArchiveAISystemHandler,
        ai_system_repository=ai_system_repository
    )

    restore_ai_system_command_handler = providers.Factory(
        RestoreAISystemHandler,
        ai_system_repository=ai_system_repository
    )

    delete_ai_system_command_handler = providers.Factory(
        DeleteAISystemHandler,
        ai_system_repository=ai_system_repository
    )

    assign_ai_system_to_process_command_handler = providers.Factory(
        AssignAISystemToProcessHandler,
        ai_system_repository=ai_system_repository,
        business_process_repository=business_process_repository
    )

    # ===== AI System Query Handlers =====
    get_ai_system_query_handler = providers.Factory(
        GetAISystemHandler,
        ai_system_repository=ai_system_repository
    )

    list_ai_systems_query_handler = providers.Factory(
        ListAISystemsHandler,
        ai_system_repository=ai_system_repository
    )

    get_dashboard_stats_query_handler = providers.Factory(
        GetDashboardStatsHandler,
        ai_system_repository=ai_system_repository,
        assessment_repository=assessment_repository
    )

    # ===== Business Process Command Handlers =====
    create_business_process_command_handler = providers.Factory(
        CreateBusinessProcessHandler,
        repository=business_process_repository
    )

    update_business_process_command_handler = providers.Factory(
        UpdateBusinessProcessHandler,
        repository=business_process_repository
    )

    delete_business_process_command_handler = providers.Factory(
        DeleteBusinessProcessHandler,
        repository=business_process_repository
    )

    # ===== Business Process Query Handlers =====
    get_business_process_query_handler = providers.Factory(
        GetBusinessProcessHandler,
        repository=business_process_repository
    )

    list_business_processes_query_handler = providers.Factory(
        ListBusinessProcessesHandler,
        repository=business_process_repository
    )

    get_dashboard_query_handler = providers.Factory(
        GetDashboardHandler,
        business_process_repository=business_process_repository,
        assessment_repository=assessment_repository
    )

    # ===== Assessment Command Handlers =====
    create_assessment_command_handler = providers.Factory(
        CreateAssessmentHandler,
        assessment_repository=assessment_repository,
        ai_system_repository=ai_system_repository
    )

    delete_assessment_command_handler = providers.Factory(
        DeleteAssessmentHandler,
        assessment_repository=assessment_repository
    )

    save_response_command_handler = providers.Factory(
        SaveResponseHandler,
        assessment_repository=assessment_repository,
        response_repository=response_repository
    )

    # ===== CommonAnswer Command Handlers =====
    update_common_answers_command_handler = providers.Factory(
        UpdateCommonAnswersHandler,
        assessment_repository=assessment_repository,
        response_repository=response_repository,
        common_answer_repository=common_answer_repository
    )

    complete_assessment_command_handler = providers.Factory(
        CompleteAssessmentHandler,
        assessment_repository=assessment_repository,
        response_repository=response_repository,
        gap_repository=gap_repository,
        update_common_answers_handler=update_common_answers_command_handler
    )

    # ===== Assessment Query Handlers =====
    get_assessment_query_handler = providers.Factory(
        GetAssessmentHandler,
        assessment_repository=assessment_repository
    )

    list_assessments_query_handler = providers.Factory(
        ListAssessmentsHandler,
        assessment_repository=assessment_repository
    )

    get_assessment_progress_query_handler = providers.Factory(
        GetAssessmentProgressHandler,
        assessment_repository=assessment_repository,
        response_repository=response_repository
    )

    get_questions_query_handler = providers.Factory(
        GetQuestionsHandler,
        assessment_repository=assessment_repository,
        response_repository=response_repository,
        common_answer_repository=common_answer_repository
    )

    get_scores_query_handler = providers.Factory(
        GetScoresHandler,
        assessment_repository=assessment_repository,
        response_repository=response_repository
    )

    get_results_query_handler = providers.Factory(
        GetResultsHandler,
        assessment_repository=assessment_repository,
        response_repository=response_repository,
        gap_repository=gap_repository,
        ai_system_repository=ai_system_repository
    )

    # ===== Gap Command Handlers =====
    acknowledge_gap_command_handler = providers.Factory(
        AcknowledgeGapHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    resolve_gap_command_handler = providers.Factory(
        ResolveGapHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    accept_risk_command_handler = providers.Factory(
        AcceptRiskHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    reopen_gap_command_handler = providers.Factory(
        ReopenGapHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    # ===== Gap Query Handlers =====
    get_gaps_query_handler = providers.Factory(
        GetGapsHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    get_gap_query_handler = providers.Factory(
        GetGapHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    get_gap_summary_query_handler = providers.Factory(
        GetGapSummaryHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    get_all_gaps_summary_query_handler = providers.Factory(
        GetAllGapsSummaryHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    list_all_gaps_query_handler = providers.Factory(
        ListAllGapsHandler,
        assessment_repository=assessment_repository,
        gap_repository=gap_repository
    )

    # ===== Department Mapping Command Handlers =====
    update_mappings_command_handler = providers.Factory(
        UpdateMappingsHandler,
        mapping_repository=mapping_repository
    )

    # ===== Department Mapping Query Handlers =====
    get_mapping_matrix_query_handler = providers.Factory(
        GetMappingMatrixHandler,
        mapping_repository=mapping_repository,
        session=database.provided.session
    )
