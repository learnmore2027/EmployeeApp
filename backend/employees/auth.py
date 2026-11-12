from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication without CSRF enforcement.
    Safe for cross-origin frontend on same machine (localhost).
    """
    def enforce_csrf(self, request):
        return  # skip CSRF check completely
