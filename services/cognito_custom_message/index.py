"""Cognito Custom Message trigger — localized verification / reset emails (AUTH2).

Cognito's built-in verification email is generic and English-only. Cognito can't
know the visitor's UI language on its own, so the auth screens store the chosen
language in the user's standard ``locale`` attribute at sign-up; this trigger reads
it and returns the email subject + body in Czech (default, D7) or English.

The same trigger fires for sign-up, code resend, and the forgot-password reset, so
all three are localized. The reply must keep Cognito's ``codeParameter`` placeholder
(``{####}``) — Cognito substitutes the real code. Messages are HTML (Cognito sends
the body as HTML).

Pure standard-library handler — no dependencies, so the Lambda needs no bundling.
"""

# Sign-up / resend: a code to verify the new account.
_VERIFY = {
    "cs": {
        "subject": "Tvůj ověřovací kód – Fundraising Těnovice",
        "body": (
            "Ahoj,<br><br>"
            "zakládáš si účet na webu sbírky pro <strong>Těnovice</strong> "
            "(kalkulačka příslibů). Pro dokončení registrace zadej tento ověřovací kód:"
            "<br><br><strong style=\"font-size:20px\">{####}</strong><br><br>"
            "Kód nikomu nepřeposílej. Pokud sis účet nezakládal(a), tento e-mail ignoruj."
        ),
    },
    "en": {
        "subject": "Your verification code – Tenovice Fundraising",
        "body": (
            "Hi,<br><br>"
            "you're creating an account on the <strong>Tenovice</strong> fundraising "
            "site (the pledge calculator). To finish your registration, enter this "
            "verification code:"
            "<br><br><strong style=\"font-size:20px\">{####}</strong><br><br>"
            "Don't share this code with anyone. If you didn't create an account, you "
            "can ignore this email."
        ),
    },
}

# Forgot password: a code to set a new password.
_RESET = {
    "cs": {
        "subject": "Kód pro obnovu hesla – Fundraising Těnovice",
        "body": (
            "Ahoj,<br><br>"
            "požádal(a) jsi o obnovu hesla k účtu na webu sbírky pro "
            "<strong>Těnovice</strong>. Zadej tento kód a nastav si nové heslo:"
            "<br><br><strong style=\"font-size:20px\">{####}</strong><br><br>"
            "Pokud jsi o obnovu nežádal(a), tento e-mail ignoruj – heslo zůstává beze změny."
        ),
    },
    "en": {
        "subject": "Your password reset code – Tenovice Fundraising",
        "body": (
            "Hi,<br><br>"
            "you requested a password reset for your account on the "
            "<strong>Tenovice</strong> fundraising site. Enter this code to set a new "
            "password:"
            "<br><br><strong style=\"font-size:20px\">{####}</strong><br><br>"
            "If you didn't request this, you can ignore this email — your password "
            "stays unchanged."
        ),
    },
}


def _lang(locale: str) -> str:
    """Map a stored locale to one of our two languages; default CZ (D7)."""
    return "en" if (locale or "").lower().startswith("en") else "cs"


# Only the flows AUTH2 uses are customized. Any other CustomMessage trigger (MFA,
# admin-create-user, attribute updates…) is left to Cognito's default copy so we
# never send "finish your registration" text in the wrong context.
_VERIFY_TRIGGERS = ("CustomMessage_SignUp", "CustomMessage_ResendCode")
_RESET_TRIGGERS = ("CustomMessage_ForgotPassword",)


def handler(event, context=None):
    trigger = event.get("triggerSource", "")
    if trigger in _RESET_TRIGGERS:
        messages = _RESET
    elif trigger in _VERIFY_TRIGGERS:
        messages = _VERIFY
    else:
        return event  # leave Cognito's default message untouched

    request = event.get("request", {})
    lang = _lang(request.get("userAttributes", {}).get("locale", ""))
    chosen = messages[lang]

    response = event.setdefault("response", {})
    response["emailSubject"] = chosen["subject"]
    # codeParameter is "{####}"; our templates already contain that literal token.
    response["emailMessage"] = chosen["body"]
    return event
