import logging

logger = logging.getLogger(__name__)

class SessionError(Exception):
    """Custom session error"""
    pass


class SessionManager:
    """
    Handles API session lifecycle (login, logout, refresh, etc.)
    """
    def __init__(self):
        self._session = None

    def login(self, client):
        """
        Create a new session using client SDK
        """
        try:
            self._session = client.login()
            logger.info("✅ Session created successfully.")
            return self._session
        except Exception as e:
            logger.error(f"❌ Failed to login: {e}")
            raise SessionError(str(e))

    def logout(self):
        """
        Destroy the current session
        """
        if self._session:
            try:
                self._session.logout()
                logger.info("✅ Session logged out.")
                self._session = None
            except Exception as e:
                logger.error(f"❌ Failed to logout: {e}")
                raise SessionError(str(e))

    def get_session(self):
        """
        Return current session if available
        """
        if not self._session:
            raise SessionError("⚠️ No active session. Please login first.")
        return self._session


# -------------------------
# Global session shortcuts
# -------------------------
_active_session = None


def set_session(session):
    """
    Store active session globally
    """
    global _active_session
    _active_session = session
    logger.info("🔑 Active session set.")


def get_session_safe():
    """
    Return active session safely (None if missing)
    """
    return _active_session


def clear_session():
    """
    Clear global session
    """
    global _active_session
    _active_session = None
    logger.info("🧹 Session cleared.")
