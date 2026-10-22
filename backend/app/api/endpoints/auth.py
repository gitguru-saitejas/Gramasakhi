from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import logging
import secrets

from app.database.session import get_db
from app.models.citizen_account import CitizenAccount, OTPVerification
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    OTPRequest,
    OTPVerifyRequest,
    RegisterRequest,
    ForgotPasswordResetRequest,
    OTPDevRetrievalResponse,
    OTPSendResponse,
)
from app.services.otp_delivery import (
    build_otp_send_response,
    dev_popup_active,
    dispatch_otp_sms,
)
from app.core.config import settings
from app.core import security
from app.services.auth_rate_limit import auth_rate_limit_ok, client_ip
from app.services.otp_dev_retrieval import (
    dev_retrieval_openapi_visible,
    mask_phone_number,
    otp_dev_key_valid,
    recover_otp_from_hash,
)

router = APIRouter()
logger = logging.getLogger("gramsakhi.auth")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return True
    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return exp < _utc_now()


def _log_otp_simulator(phone_number: str, code: str, *, purpose: str) -> None:
    from app.services.otp_console import emit_dev_otp_to_terminal

    emit_dev_otp_to_terminal(phone_number, code, purpose=purpose)


def _create_otp_record(db: Session, phone_number: str) -> tuple[OTPVerification, str]:
    code = security.generate_otp()
    otp_hash = security.get_otp_hash(code)
    otp_record = OTPVerification(
        phone_number=phone_number,
        otp_hash=otp_hash,
        expires_at=_utc_now() + timedelta(minutes=3),
        verified=False,
        attempt_count=0,
    )
    db.add(otp_record)
    db.commit()
    db.refresh(otp_record)
    return otp_record, code


def _active_otp_record(
    db: Session,
    phone_number: str,
    *,
    otp_verification_id: str | None = None,
) -> OTPVerification | None:
    q = db.query(OTPVerification).filter(
        OTPVerification.phone_number == phone_number,
        OTPVerification.verified == False,  # noqa: E712
    )
    if otp_verification_id:
        q = q.filter(OTPVerification.id == otp_verification_id)
    return q.order_by(OTPVerification.created_at.desc()).first()


def _consume_verified_otp(db: Session, phone_number: str) -> OTPVerification:
    otp_rec = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone_number == phone_number,
            OTPVerification.verified == True,  # noqa: E712
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    if not otp_rec or _is_expired(otp_rec.expires_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP verification is required before registration.",
        )
    otp_rec.verified = False
    db.commit()
    return otp_rec


def _token_payload(account: CitizenAccount) -> dict:
    token = security.create_access_token(subject=str(account.id), token_use="citizen")
    return {
        "accessToken": token,
        "citizen_account_id": account.id,
        "family_account_id": account.id,  # backward-compatible alias
        "phone_number": account.phone_number,
        "display_name": account.display_name,
    }


_GENERIC_LOGIN_ERROR = "Invalid phone number or password."


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    ip = client_ip(http_request)
    rate_key = f"{ip}:{request.phone_number}"

    account = db.query(CitizenAccount).filter(
        CitizenAccount.phone_number == request.phone_number
    ).first()
    if not account or not account.is_active:
        if not auth_rate_limit_ok(rate_key, bucket="login"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait before trying again.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_GENERIC_LOGIN_ERROR,
        )

    if request.login_type == "password":
        if not request.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required for password login.",
            )
        if not security.verify_password(request.password, account.password_hash):
            if not auth_rate_limit_ok(rate_key, bucket="login"):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please wait before trying again.",
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_GENERIC_LOGIN_ERROR,
            )
    elif request.login_type == "otp":
        otp_rec = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.phone_number == request.phone_number,
                OTPVerification.verified == True,  # noqa: E712
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )
        if not otp_rec or _is_expired(otp_rec.expires_at):
            if not auth_rate_limit_ok(rate_key, bucket="login"):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please wait before trying again.",
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_GENERIC_LOGIN_ERROR,
            )
        otp_rec.verified = False
        db.commit()
    else:
        raise HTTPException(status_code=400, detail="Invalid login method type.")

    return _token_payload(account)


@router.post("/otp/send", response_model=OTPSendResponse, response_model_exclude_none=True)
def send_otp(request: OTPRequest, db: Session = Depends(get_db)):
    if not auth_rate_limit_ok(request.phone_number, bucket="otp_send"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait before trying again.",
        )

    otp_record, code = _create_otp_record(db, request.phone_number)

    if not dev_popup_active():
        dispatch_otp_sms(request.phone_number, code, purpose="verification")
    _log_otp_simulator(request.phone_number, code, purpose="verification")

    return build_otp_send_response(
        otp_verification_id=str(otp_record.id),
        expires_at=otp_record.expires_at,
        dev_code=code if dev_popup_active() else None,
    )


@router.get(
    "/otp/dev",
    response_model=OTPDevRetrievalResponse,
    include_in_schema=dev_retrieval_openapi_visible(),
)
def dev_retrieve_otp(
    phone_number: str = Query(..., min_length=1),
    x_dev_otp_key: str | None = Header(None, alias="X-Dev-OTP-Key"),
    db: Session = Depends(get_db),
):
    """Development-only OTP lookup for manual testing (disabled in production)."""
    if not otp_dev_key_valid(x_dev_otp_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    phone = OTPRequest(phone_number=phone_number).phone_number

    otp_rec = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone_number == phone,
            OTPVerification.verified == False,  # noqa: E712
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    if not otp_rec or _is_expired(otp_rec.expires_at):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    code = recover_otp_from_hash(otp_rec.otp_hash)
    if not code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return OTPDevRetrievalResponse(
        otp=code,
        expires_at=otp_rec.expires_at,
        phone_number=mask_phone_number(phone),
    )


@router.post("/otp/verify")
def verify_otp(request: OTPVerifyRequest, http_request: Request, db: Session = Depends(get_db)):
    if not auth_rate_limit_ok(f"{client_ip(http_request)}:{request.phone_number}", bucket="otp_verify"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait before trying again.",
        )
    otp_rec = _active_otp_record(
        db,
        request.phone_number,
        otp_verification_id=request.otp_verification_id,
    )

    if not otp_rec:
        raise HTTPException(status_code=400, detail="No active OTP request found for this phone.")

    if _is_expired(otp_rec.expires_at):
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new code.")

    if otp_rec.attempt_count >= 5:
        raise HTTPException(status_code=400, detail="Too many failed verification attempts.")

    if not security.verify_otp_hash(request.code, otp_rec.otp_hash):
        otp_rec.attempt_count += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    otp_rec.verified = True
    db.commit()

    account = db.query(CitizenAccount).filter(
        CitizenAccount.phone_number == request.phone_number
    ).first()
    if account:
        otp_rec.verified = False
        db.commit()
        return _token_payload(account)

    return {"message": "OTP verification completed. Proceed to register your citizen account."}


@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    _consume_verified_otp(db, request.credentials.phone_number)

    existing = db.query(CitizenAccount).filter(
        CitizenAccount.phone_number == request.credentials.phone_number
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An account with this mobile number already exists. Please login.",
        )

    # DB column requires a hash; citizens authenticate via OTP only (no user-facing password).
    password_hash = security.get_password_hash(secrets.token_urlsafe(32))
    account = CitizenAccount(
        phone_number=request.credentials.phone_number,
        password_hash=password_hash,
        display_name=request.display_name,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return _token_payload(account)


@router.post("/forgot-password/request")
def request_password_reset(request: OTPRequest, db: Session = Depends(get_db)):
    if not auth_rate_limit_ok(request.phone_number, bucket="otp_send"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait before trying again.",
        )

    account = db.query(CitizenAccount).filter(
        CitizenAccount.phone_number == request.phone_number
    ).first()
    if not account:
        return {"message": "OTP verification code sent."}

    otp_record, code = _create_otp_record(db, request.phone_number)
    if not dev_popup_active():
        dispatch_otp_sms(request.phone_number, code, purpose="password_reset")
    _log_otp_simulator(request.phone_number, code, purpose="password_reset")

    return build_otp_send_response(
        otp_verification_id=str(otp_record.id),
        expires_at=otp_record.expires_at,
        dev_code=code if dev_popup_active() else None,
    )


@router.post("/forgot-password/reset")
def reset_password(request: ForgotPasswordResetRequest, db: Session = Depends(get_db)):
    otp_rec = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.phone_number == request.phone_number,
            OTPVerification.verified == False,  # noqa: E712
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp_rec or _is_expired(otp_rec.expires_at):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code.")

    if otp_rec.attempt_count >= 5:
        raise HTTPException(status_code=400, detail="Too many failed verification attempts.")

    if not security.verify_otp_hash(request.otp_code, otp_rec.otp_hash):
        otp_rec.attempt_count += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP code.")

    account = db.query(CitizenAccount).filter(
        CitizenAccount.phone_number == request.phone_number
    ).first()
    if not account:
        raise HTTPException(status_code=400, detail="Account not found.")

    account.password_hash = security.get_password_hash(request.new_password)
    otp_rec.verified = True
    db.commit()

    return {"message": "Password updated successfully."}
