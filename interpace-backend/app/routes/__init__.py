from .auth_routes import router as auth_router
from .config_routes import router as config_router
from .interview_routes import router as interview_router
from .note_routes import router as note_router
from .quiz_routes import router as quiz_router
from .resource_routes import router as resource_router
from .search_routes import router as search_router
from .resume_routes import router as resume_router
from .session_routes import router as session_router
from .speech_routes import router as speech_router
from .user_routes import router as user_router
from .user_profile_routes import router as user_profile_router
from .upload_routes import router as upload_router
from .prompt_routes import router as prompt_router
from .profile_proposal_routes import router as profile_proposal_router

__all__ = [
    "auth_router",
    "config_router",
    "interview_router",
    "note_router",
    "quiz_router",
    "resource_router",
    "search_router",
    "resume_router",
    "session_router",
    "speech_router",
    "user_router",
    "user_profile_router",
    "upload_router",
    "prompt_router",
    "profile_proposal_router",
]
