import logging

class SessionError(Exception):
    """Custom exception for session-related errors"""
    pass


class SessionManager:
    """
    Handles API session lifecycle (login, logout, refresh, etc.)
    Stores credentials safely inside the manager.
    """

    def __init__(self, api_key: str, api_secret: str, totp_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.totp_secret = totp_secret
        self._session = None

    def login(self, client_cls):
        """
        Create a new session using client SDK
        """
        try:
            client = client_cls(self.api_key, self.api_secret, self.totp_secret)
            self._session = client.login()
            logging.info("Login successful")
            return self._session
        except Exception as e:
            logging.error(f"Login failed: {e}")
            raise SessionError(str(e))

    def get_session(self):
        """
        Return the current active session, if any
        """
        if not self._session:
            raise SessionError("No active session. Please login first.")
        return self._session

    def logout(self):
        """
        Destroy the session
        """
        if self._session:
            try:
                self._session.logout()
            except Exception:
                pass
        self._session = None
        logging.info("Logged out successfully")
