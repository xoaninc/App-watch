from dependency_injector import containers, providers

# Repositories
from src.auth_bc.organization.infrastructure.repositories import OrganizationRepository
from src.auth_bc.user.infrastructure.repositories import UserRepository
from src.auth_bc.session.infrastructure.repositories import SessionRepository
from src.auth_bc.membership.infrastructure.repositories import MembershipRepository
from src.auth_bc.password_reset.infrastructure.repositories import PasswordResetTokenRepository
from src.auth_bc.email_change.infrastructure.repositories import EmailChangeRequestRepository
from src.auth_bc.invitation.infrastructure.repositories import UserInvitationRepository
from src.auth_bc.department.infrastructure.repositories import DepartmentRepository

# Services
from src.auth_bc.session.infrastructure.services import JwtService
from src.shared_bc.notification.infrastructure.services import (
    MockEmailService,
    SmtpEmailService,
    MailgunEmailService,
)
from core.config import settings
from src.shared_bc.storage.infrastructure import LocalFileStorage

# Command Handlers
from src.auth_bc.organization.application.commands import (
    RegisterOrganizationHandler,
    UpdateOrganizationProfileHandler,
)
from src.auth_bc.user.application.commands import (
    LoginHandler, VerifyEmailHandler, ResendVerificationHandler,
    UpdateProfileHandler, UploadAvatarHandler, RemoveAvatarHandler,
    ChangeUserRoleHandler, DeactivateUserHandler, ReactivateUserHandler, DeleteUserHandler
)
from src.auth_bc.session.application.commands import (
    LogoutHandler, RefreshTokenHandler,
    RevokeSessionHandler, RevokeAllSessionsHandler
)
from src.auth_bc.password_reset.application.commands import (
    RequestPasswordResetHandler, ResetPasswordHandler, ChangePasswordHandler
)
from src.auth_bc.email_change.application.commands import (
    RequestEmailChangeHandler, ConfirmEmailChangeHandler
)
from src.auth_bc.invitation.application.commands import (
    InviteUserHandler, AcceptInvitationHandler,
    ResendInvitationHandler, CancelInvitationHandler
)
from src.auth_bc.membership.application.commands import (
    SwitchOrganizationHandler, LeaveOrganizationHandler
)
from src.auth_bc.department.application.commands import (
    CreateDepartmentHandler, UpdateDepartmentHandler, DeleteDepartmentHandler
)
from src.auth_bc.department.application.queries import (
    GetDepartmentHandler, ListDepartmentsHandler
)

# Query Handlers
from src.auth_bc.user.application.queries import (
    GetCurrentUserHandler, GetUsersHandler, GetUserByIdHandler
)
from src.auth_bc.organization.application.queries import (
    GetOrganizationHandler,
    GetWebAnalysisStatusHandler,
)
from src.auth_bc.session.application.queries import GetActiveSessionsHandler
from src.auth_bc.invitation.application.queries import GetPendingInvitationsHandler
from src.auth_bc.membership.application.queries import (
    GetUserMembershipsHandler, GetOrganizationMembersHandler
)

# Event Handlers
from src.auth_bc.user.application.handlers import SendVerificationEmailHandler
from src.auth_bc.user.application.event_handlers import SendRoleChangedNotificationHandler
from src.auth_bc.password_reset.application.event_handlers import (
    SendPasswordResetEmailHandler, SendPasswordChangedEmailHandler
)
from src.auth_bc.email_change.application.event_handlers import (
    SendEmailChangeVerificationHandler, SendEmailChangeNotificationHandler
)
from src.auth_bc.invitation.application.event_handlers import SendInvitationEmailHandler


def _create_email_service(frontend_url: str):
    """Factory function to create the appropriate email service based on config."""
    if settings.EMAIL_SERVICE == "mailgun":
        return MailgunEmailService(
            api_key=settings.MAILGUN_API_KEY,
            domain=settings.MAILGUN_DOMAIN,
            from_email=settings.SMTP_FROM_EMAIL,
            base_url=frontend_url,
        )
    elif settings.EMAIL_SERVICE == "smtp":
        return SmtpEmailService(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            from_email=settings.SMTP_FROM_EMAIL,
            use_tls=settings.SMTP_USE_TLS,
            base_url=frontend_url,
        )
    else:
        return MockEmailService(base_url=frontend_url)


class AuthContainer(containers.DeclarativeContainer):
    """Dependency injection container for Auth bounded context.

    Handler naming convention for CommandBus/QueryBus:
    - RegisterOrganizationCommand -> register_organization_command_handler
    - GetCurrentUserQuery -> get_current_user_query_handler
    """

    # External dependencies (injected from main container)
    config = providers.Configuration()
    database = providers.Dependency()

    # ===== Services =====
    jwt_service = providers.Singleton(
        JwtService,
        secret_key=config.auth.secret_key,
        access_token_expire_minutes=config.auth.access_token_expire_minutes,
        refresh_token_expire_days=config.auth.refresh_token_expire_days
    )

    email_service = providers.Singleton(
        _create_email_service,
        frontend_url=config.frontend_url
    )

    file_storage = providers.Singleton(LocalFileStorage)

    # ===== Repositories =====
    organization_repository = providers.Factory(
        OrganizationRepository,
        session=database.provided.session
    )

    user_repository = providers.Factory(
        UserRepository,
        session=database.provided.session
    )

    session_repository = providers.Factory(
        SessionRepository,
        session=database.provided.session
    )

    membership_repository = providers.Factory(
        MembershipRepository,
        session=database.provided.session
    )

    password_reset_token_repository = providers.Factory(
        PasswordResetTokenRepository,
        session=database.provided.session
    )

    email_change_repository = providers.Factory(
        EmailChangeRequestRepository,
        session=database.provided.session
    )

    invitation_repository = providers.Factory(
        UserInvitationRepository,
        session=database.provided.session
    )

    department_repository = providers.Factory(
        DepartmentRepository,
        session=database.provided.session
    )

    # ===== Command Handlers (snake_case for CommandBus convention) =====

    # Organization commands
    register_organization_command_handler = providers.Factory(
        RegisterOrganizationHandler,
        organization_repository=organization_repository,
        user_repository=user_repository,
        session_repository=session_repository,
        membership_repository=membership_repository,
        jwt_service=jwt_service
    )

    update_organization_profile_command_handler = providers.Factory(
        UpdateOrganizationProfileHandler,
        organization_repository=organization_repository
    )

    # User/Login commands
    login_command_handler = providers.Factory(
        LoginHandler,
        user_repository=user_repository,
        organization_repository=organization_repository,
        session_repository=session_repository,
        membership_repository=membership_repository,
        jwt_service=jwt_service
    )

    verify_email_command_handler = providers.Factory(
        VerifyEmailHandler,
        user_repository=user_repository
    )

    resend_verification_command_handler = providers.Factory(
        ResendVerificationHandler,
        user_repository=user_repository,
        email_service=email_service
    )

    update_profile_command_handler = providers.Factory(
        UpdateProfileHandler,
        user_repository=user_repository
    )

    upload_avatar_command_handler = providers.Factory(
        UploadAvatarHandler,
        user_repository=user_repository,
        file_storage=file_storage
    )

    remove_avatar_command_handler = providers.Factory(
        RemoveAvatarHandler,
        user_repository=user_repository,
        file_storage=file_storage
    )

    change_user_role_command_handler = providers.Factory(
        ChangeUserRoleHandler,
        user_repository=user_repository,
        membership_repository=membership_repository
    )

    deactivate_user_command_handler = providers.Factory(
        DeactivateUserHandler,
        user_repository=user_repository,
        session_repository=session_repository,
        membership_repository=membership_repository
    )

    reactivate_user_command_handler = providers.Factory(
        ReactivateUserHandler,
        user_repository=user_repository,
        membership_repository=membership_repository
    )

    delete_user_command_handler = providers.Factory(
        DeleteUserHandler,
        user_repository=user_repository,
        session_repository=session_repository,
        membership_repository=membership_repository
    )

    # Session commands
    logout_command_handler = providers.Factory(
        LogoutHandler,
        session_repository=session_repository
    )

    refresh_token_command_handler = providers.Factory(
        RefreshTokenHandler,
        session_repository=session_repository,
        jwt_service=jwt_service
    )

    revoke_session_command_handler = providers.Factory(
        RevokeSessionHandler,
        session_repository=session_repository
    )

    revoke_all_sessions_command_handler = providers.Factory(
        RevokeAllSessionsHandler,
        session_repository=session_repository
    )

    # Password reset commands
    request_password_reset_command_handler = providers.Factory(
        RequestPasswordResetHandler,
        user_repository=user_repository,
        token_repository=password_reset_token_repository,
        email_service=email_service
    )

    reset_password_command_handler = providers.Factory(
        ResetPasswordHandler,
        token_repository=password_reset_token_repository,
        user_repository=user_repository,
        session_repository=session_repository
    )

    change_password_command_handler = providers.Factory(
        ChangePasswordHandler,
        user_repository=user_repository,
        session_repository=session_repository
    )

    # Email change commands
    request_email_change_command_handler = providers.Factory(
        RequestEmailChangeHandler,
        user_repository=user_repository,
        email_change_repository=email_change_repository
    )

    confirm_email_change_command_handler = providers.Factory(
        ConfirmEmailChangeHandler,
        email_change_repository=email_change_repository,
        user_repository=user_repository
    )

    # Invitation commands
    invite_user_command_handler = providers.Factory(
        InviteUserHandler,
        user_repository=user_repository,
        organization_repository=organization_repository,
        invitation_repository=invitation_repository,
        membership_repository=membership_repository
    )

    accept_invitation_command_handler = providers.Factory(
        AcceptInvitationHandler,
        invitation_repository=invitation_repository,
        user_repository=user_repository,
        organization_repository=organization_repository,
        session_repository=session_repository,
        membership_repository=membership_repository,
        jwt_service=jwt_service
    )

    resend_invitation_command_handler = providers.Factory(
        ResendInvitationHandler,
        invitation_repository=invitation_repository,
        user_repository=user_repository,
        organization_repository=organization_repository,
        membership_repository=membership_repository
    )

    cancel_invitation_command_handler = providers.Factory(
        CancelInvitationHandler,
        invitation_repository=invitation_repository,
        user_repository=user_repository,
        membership_repository=membership_repository
    )

    # Membership commands
    switch_organization_command_handler = providers.Factory(
        SwitchOrganizationHandler,
        membership_repository=membership_repository,
        user_repository=user_repository,
        session_repository=session_repository,
        jwt_service=jwt_service
    )

    leave_organization_command_handler = providers.Factory(
        LeaveOrganizationHandler,
        membership_repository=membership_repository
    )

    # Department commands
    create_department_command_handler = providers.Factory(
        CreateDepartmentHandler,
        repository=department_repository
    )

    update_department_command_handler = providers.Factory(
        UpdateDepartmentHandler,
        repository=department_repository
    )

    delete_department_command_handler = providers.Factory(
        DeleteDepartmentHandler,
        repository=department_repository
    )

    # ===== Query Handlers (snake_case for QueryBus convention) =====

    get_current_user_query_handler = providers.Factory(
        GetCurrentUserHandler,
        user_repository=user_repository
    )

    get_users_query_handler = providers.Factory(
        GetUsersHandler,
        user_repository=user_repository,
        membership_repository=membership_repository
    )

    get_user_by_id_query_handler = providers.Factory(
        GetUserByIdHandler,
        user_repository=user_repository,
        membership_repository=membership_repository
    )

    get_organization_query_handler = providers.Factory(
        GetOrganizationHandler,
        organization_repository=organization_repository
    )

    get_web_analysis_status_query_handler = providers.Factory(
        GetWebAnalysisStatusHandler,
        organization_repository=organization_repository
    )

    get_active_sessions_query_handler = providers.Factory(
        GetActiveSessionsHandler,
        session_repository=session_repository
    )

    get_pending_invitations_query_handler = providers.Factory(
        GetPendingInvitationsHandler,
        invitation_repository=invitation_repository,
        user_repository=user_repository,
        membership_repository=membership_repository
    )

    get_user_memberships_query_handler = providers.Factory(
        GetUserMembershipsHandler,
        membership_repository=membership_repository,
        organization_repository=organization_repository
    )

    get_organization_members_query_handler = providers.Factory(
        GetOrganizationMembersHandler,
        membership_repository=membership_repository,
        user_repository=user_repository
    )

    # Department queries
    get_department_query_handler = providers.Factory(
        GetDepartmentHandler,
        repository=department_repository
    )

    list_departments_query_handler = providers.Factory(
        ListDepartmentsHandler,
        repository=department_repository
    )

    # ===== Event Handlers =====

    send_verification_email_handler = providers.Factory(
        SendVerificationEmailHandler,
        email_service=email_service
    )

    send_role_changed_notification_handler = providers.Factory(
        SendRoleChangedNotificationHandler,
        email_service=email_service
    )

    send_password_reset_email_handler = providers.Factory(
        SendPasswordResetEmailHandler,
        email_service=email_service
    )

    send_password_changed_email_handler = providers.Factory(
        SendPasswordChangedEmailHandler,
        email_service=email_service
    )

    send_email_change_verification_handler = providers.Factory(
        SendEmailChangeVerificationHandler,
        email_service=email_service
    )

    send_email_change_notification_handler = providers.Factory(
        SendEmailChangeNotificationHandler,
        email_service=email_service
    )

    send_invitation_email_handler = providers.Factory(
        SendInvitationEmailHandler,
        email_service=email_service
    )
