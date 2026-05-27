import logging
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.config import settings
from app.core.security import set_admin_custom_claims
from app.models.admin import Admin, AdminRole

logger = logging.getLogger(__name__)


def bootstrap_super_admin() -> None:
    """
    Crée le premier super_admin au démarrage si aucun n'existe encore.
    Nécessite BOOTSTRAP_SUPER_ADMIN_UID et BOOTSTRAP_SUPER_ADMIN_EMAIL dans .env.
    Idempotent : ne fait rien si un super_admin existe déjà.
    """
    if not settings.BOOTSTRAP_SUPER_ADMIN_UID or not settings.BOOTSTRAP_SUPER_ADMIN_EMAIL:
        return

    db: Session = SessionLocal()
    try:
        existing = db.query(Admin).filter(
            Admin.role == AdminRole.super_admin,
            Admin.is_deleted == False
        ).first()

        if existing:
            logger.info("Bootstrap ignoré : un super_admin existe déjà (%s)", existing.email)
            return

        already_registered = db.query(Admin).filter(
            Admin.firebase_uid == settings.BOOTSTRAP_SUPER_ADMIN_UID
        ).first()

        if already_registered:
            logger.warning("Bootstrap ignoré : UID déjà enregistré (%s)", settings.BOOTSTRAP_SUPER_ADMIN_UID)
            return

        admin = Admin(
            firebase_uid=settings.BOOTSTRAP_SUPER_ADMIN_UID,
            email=settings.BOOTSTRAP_SUPER_ADMIN_EMAIL,
            role=AdminRole.super_admin,
        )
        db.add(admin)
        db.commit()

        set_admin_custom_claims(settings.BOOTSTRAP_SUPER_ADMIN_UID, AdminRole.super_admin.value)

        logger.info(
            "✅ Super admin bootstrapé avec succès : %s (uid=%s)",
            settings.BOOTSTRAP_SUPER_ADMIN_EMAIL,
            settings.BOOTSTRAP_SUPER_ADMIN_UID
        )
    except Exception as e:
        db.rollback()
        logger.error("Échec du bootstrap super_admin : %s", e)
        raise
    finally:
        db.close()
