import time
import pyotp

class SessionError(Exception):
    pass

class SessionManager:
    def __init__(self, api_key, api_secret, totp_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.totp_secret = totp_secret
        self.session_key = None
        self.logged_in = False
        self.create_session()

    def create_session(self):
        # Simulate API login
        try:
            if self.totp_secret:
                totp = pyotp.TOTP(self.totp_secret)
                otp = totp.now()
                self.session_key = f"session_{otp}"
            else:
                self.session_key = f"session_{int(time.time())}"
            self.logged_in = True
        except Exception as e:
            raise SessionError(f"Session creation failed: {e}")

    def get_session(self):
        if not self.logged_in:
            raise SessionError("Session not active")
        return self.session_key
