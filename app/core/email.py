import logging
import resend
from app.core.config import settings

logger = logging.getLogger(__name__)


def _init_resend() -> None:
    resend.api_key = settings.RESEND_API_KEY


def send_arcade_owner_invitation(
    to_email: str,
    arcade_name: str,
    activation_link: str,
) -> None:
    """Envoie l'email d'invitation à un nouveau propriétaire de borne."""
    _init_resend()

    html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Invitation RetroNova</title>
</head>
<body style="margin:0;padding:0;background:#F2F4F8;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F2F4F8;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border-radius:8px;overflow:hidden;border:1px solid #DDE1E6;">

          <!-- Header -->
          <tr>
            <td style="background:#0062FE;padding:32px 40px;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:rgba(255,255,255,0.15);border-radius:6px;padding:8px 14px;
                              font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:700;
                              color:#FFFFFF;letter-spacing:0.05em;">
                    RN
                  </td>
                  <td style="padding-left:12px;font-size:18px;font-weight:600;color:#FFFFFF;">
                    RetroNova
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px;">
              <p style="margin:0 0 8px;font-size:22px;font-weight:600;color:#343A3F;">
                Bienvenue sur RetroNova
              </p>
              <p style="margin:0 0 24px;font-size:14px;color:#697077;line-height:1.6;">
                Vous avez été invité à gérer la borne <strong style="color:#343A3F;">{arcade_name}</strong>
                sur la plateforme RetroNova Back Office.
              </p>

              <p style="margin:0 0 16px;font-size:14px;color:#343A3F;line-height:1.6;">
                Cliquez sur le bouton ci-dessous pour créer votre mot de passe et accéder à votre espace&nbsp;:
              </p>

              <table cellpadding="0" cellspacing="0" style="margin:0 0 32px;">
                <tr>
                  <td style="background:#0062FE;border-radius:6px;">
                    <a href="{activation_link}"
                       style="display:inline-block;padding:12px 28px;font-size:14px;font-weight:600;
                              color:#FFFFFF;text-decoration:none;letter-spacing:0.01em;">
                      Créer mon mot de passe
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 8px;font-size:12px;color:#697077;">
                Ce lien est valable <strong>24 heures</strong>. Si vous ne vous attendiez pas à recevoir cet email, ignorez-le.
              </p>
              <p style="margin:0;font-size:12px;color:#A8B0BA;word-break:break-all;">
                {activation_link}
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 40px;border-top:1px solid #DDE1E6;background:#F2F4F8;">
              <p style="margin:0;font-size:12px;color:#A8B0BA;">
                RetroNova — Plateforme de gestion de bornes d'arcade
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    try:
        resend.Emails.send({
            "from": f"RetroNova <{settings.RESEND_FROM_EMAIL}>",
            "to": [to_email],
            "subject": f"Invitation RetroNova — Gérez votre borne {arcade_name}",
            "html": html,
        })
        logger.info("Email d'invitation envoyé à %s", to_email)
    except Exception as e:
        logger.error("Échec envoi email invitation à %s : %s", to_email, e)
        raise
