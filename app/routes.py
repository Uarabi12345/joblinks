import os
import random
import string
import shutil
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import create_token, current_user, hash_password, verify_password
from app.database import get_db
from app.models import JobLink, Payment, User, SystemConfig
from app import mpesa
from app.email_utils import send_email

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

def get_current_batch(db: Session) -> int:
    config = db.query(SystemConfig).first()
    if not config:
        config = SystemConfig(id=1, current_batch=1)
        db.add(config)
        db.commit()
    return config.current_batch

def ensure_admin(db: Session):
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not existing:
            db.add(User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), is_admin=True, is_verified=True))
            db.commit()

def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("+", "")
    if phone.startswith("0"): phone = "254" + phone[1:]
    elif phone.startswith("7") or phone.startswith("1"): phone = "254" + phone
    return phone

def generate_code():
    return ''.join(random.choices(string.digits, k=6))


# ---------------- Home / dashboard (WORKER VIEW) ----------------

@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    ensure_admin(db)
    user = current_user(request, db)
    
    if user and user.is_admin:
        return RedirectResponse("/admin", status_code=302)

    current_batch = get_current_batch(db)
    links = db.query(JobLink).filter(JobLink.batch_id == current_batch).order_by(JobLink.id.desc()).all()

    my_claimed_jobs = []
    if user:
        my_claimed_jobs = db.query(JobLink).filter(JobLink.taken_by == user.id).order_by(JobLink.id.desc()).all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "links": links,
            "my_claimed_jobs": my_claimed_jobs,
            "current_batch": current_batch,
            "available_jobs": sum(1 for l in links if l.status == "available"),
        },
    )


# ---------------- Register / Verify / login / logout ----------------

@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "user": None, "error": None})

@router.post("/register")
def register(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("register.html", {"request": request, "user": None, "error": "Email already exists"})
        
    code = generate_code()
    new_user = User(email=email, password_hash=hash_password(password), is_verified=False, verification_code=code)
    db.add(new_user)
    db.commit()
    
    send_email(email, "Verify Your JobLinks Account", f"Welcome to JobLinks!\n\nYour 6-digit verification code is: {code}")
    return RedirectResponse(f"/verify?email={email}", status_code=302)

@router.get("/verify", response_class=HTMLResponse)
def verify_form(request: Request, email: str):
    return templates.TemplateResponse("verify.html", {"request": request, "user": None, "email": email, "error": None})

@router.post("/verify")
def verify_account(request: Request, email: str = Form(...), code: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user: return RedirectResponse("/login", status_code=302)
    if user.verification_code != code:
        return templates.TemplateResponse("verify.html", {"request": request, "user": None, "email": email, "error": "Invalid code."})
        
    user.is_verified = True
    user.verification_code = None
    db.commit()
    
    welcome_subject = "Welcome to JobLinks! 🚀"
    welcome_body = f"Hi there,\n\nWelcome to JobLinks! Your account is now fully verified and ready to go.\n\nYou can now browse available jobs on your dashboard, pay the small unlock fee, and start earning real money from your phone today.\n\nBest regards,\nThe JobLinks Team\n\nGo to your dashboard here: {BASE_URL}"
    send_email(email, welcome_subject, welcome_body)

    token = create_token(user.email)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=7 * 24 * 3600)
    return response

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": None})

@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Invalid credentials"})
    if not user.is_verified and not user.is_admin:
        return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": "Please verify your email first."})
    
    token = create_token(user.email)
    response = RedirectResponse("/admin" if user.is_admin else "/", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=7 * 24 * 3600)
    return response

@router.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response


# ---------------- Forgot / Reset Password ----------------

@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request, "user": None, "error": None})

@router.post("/forgot-password")
def forgot_password(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse("forgot_password.html", {"request": request, "user": None, "error": "Email not found."})
        
    code = generate_code()
    user.reset_code = code
    db.commit()
    send_email(email, "Reset Your JobLinks Password", f"Your reset code is: {code}")
    return RedirectResponse(f"/reset-password?email={email}", status_code=302)

@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, email: str):
    return templates.TemplateResponse("reset_password.html", {"request": request, "user": None, "email": email, "error": None})

@router.post("/reset-password")
def reset_password(request: Request, email: str = Form(...), code: str = Form(...), new_password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or user.reset_code != code:
        return templates.TemplateResponse("reset_password.html", {"request": request, "user": None, "email": email, "error": "Invalid code."})
        
    user.password_hash = hash_password(new_password)
    user.reset_code = None
    db.commit()
    return RedirectResponse("/login", status_code=302)


# ---------------- Worker Profile ----------------

@router.get("/profile", response_class=HTMLResponse)
def profile(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=302)
    
    my_jobs = db.query(JobLink).filter(JobLink.taken_by == user.id).order_by(JobLink.id.desc()).all()
    my_payments = db.query(Payment).filter(Payment.user_id == user.id, Payment.status == "success").order_by(Payment.id.desc()).all()
    
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "my_jobs": my_jobs, "my_payments": my_payments})


# ---------------- Pay-Per-Job Activation ----------------

@router.post("/pay/{link_id}")
def pay_for_job(request: Request, link_id: int, phone: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: raise HTTPException(401, "Login required")
    
    link = db.query(JobLink).filter(JobLink.id == link_id).first()
    if not link or link.status != "available":
        raise HTTPException(400, "This job is already taken.")

    phone = normalize_phone(phone)
    response = mpesa.stk_push(
        phone=phone,
        amount=link.unlock_fee,
        account_ref=f"JOB{link.id}",
        description=f"Unlock {link.title}",
    )

    if "CheckoutRequestID" not in response:
        raise HTTPException(400, f"M-Pesa error: {response}")

    payment = Payment(
        user_id=user.id,
        job_link_id=link.id,
        payment_type="job_unlock",
        checkout_request_id=response["CheckoutRequestID"],
        merchant_request_id=response.get("MerchantRequestID"),
        amount=link.unlock_fee,
        phone=phone,
        status="pending",
    )
    db.add(payment)
    db.commit()

    return JSONResponse({"message": "STK push sent. Enter your PIN.", "checkout_id": response["CheckoutRequestID"]})


@router.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    stk = data.get("Body", {}).get("stkCallback", {})
    checkout_id = stk.get("CheckoutRequestID")
    result_code = stk.get("ResultCode")

    payment = db.query(Payment).filter(Payment.checkout_request_id == checkout_id).first()
    if not payment: return {"ResultCode": 0, "ResultDesc": "Ignored"}

    if result_code == 0:
        payment.status = "success"
        if payment.job_link_id:
            link = db.query(JobLink).filter(JobLink.id == payment.job_link_id).first()
            if link and link.status == "available":
                link.status = "taken"
                link.taken_by = payment.user_id
    else:
        payment.status = "failed"

    db.commit()
    return {"ResultCode": 0, "ResultDesc": "OK"}


# ---------------- Manual Payment (Fallback) ----------------

@router.post("/submit-manual/{link_id}")
def submit_manual(request: Request, link_id: int, message: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: raise HTTPException(401, "Login required")
    
    link = db.query(JobLink).filter(JobLink.id == link_id).first()
    if not link or link.status != "available":
        raise HTTPException(400, "This job is already taken.")

    payment = Payment(
        user_id=user.id,
        job_link_id=link.id,
        payment_type="manual_job_unlock",
        message=message,
        status="pending",
        amount=link.unlock_fee,
    )
    db.add(payment)
    db.commit()
    return RedirectResponse("/", status_code=302)


# ---------------- Admin panel ----------------

@router.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or not user.is_admin: raise HTTPException(403, "Admin only")
    
    current_batch = get_current_batch(db)
    links = db.query(JobLink).filter(JobLink.batch_id == current_batch).order_by(JobLink.id.desc()).all()
    pending_payments = db.query(Payment).filter(Payment.status == "pending", Payment.payment_type.like("manual%")).order_by(Payment.id.desc()).all()
    workers = db.query(User).filter(User.is_admin == False).order_by(User.id.desc()).all()
    
    return templates.TemplateResponse("admin.html", {
        "request": request, 
        "user": user, 
        "links": links, 
        "pending_payments": pending_payments, 
        "current_batch": current_batch, 
        "workers": workers
    })

@router.post("/admin/add")
def admin_add(
    request: Request, 
    title: str = Form(...), 
    description: str = Form(""), 
    real_url: str = Form(...), 
    image_url: str = Form(""), 
    image_file: UploadFile = File(None),
    unlock_fee: int = Form(...), 
    payout_amount: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = current_user(request, db)
    if not user or not user.is_admin: raise HTTPException(403, "Admin only")
        
    current_batch = get_current_batch(db)
    
    final_image_url = image_url
    if image_file and image_file.filename:
        os.makedirs("app/static/uploads", exist_ok=True)
        file_ext = image_file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = f"app/static/uploads/{unique_filename}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
            
        final_image_url = f"/static/uploads/{unique_filename}"

    db.add(JobLink(
        title=title, 
        description=description, 
        real_url=real_url, 
        image_url=final_image_url,
        unlock_fee=unlock_fee, 
        payout_amount=payout_amount, 
        batch_id=current_batch
    ))
    db.commit()
    return RedirectResponse("/admin", status_code=302)

@router.post("/admin/delete/{link_id}")
def admin_delete(request: Request, link_id: int, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or not user.is_admin: raise HTTPException(403, "Admin only")
    db.query(JobLink).filter(JobLink.id == link_id).delete()
    db.commit()
    return RedirectResponse("/admin", status_code=302)

@router.post("/admin/delete-user/{user_id}")
def admin_delete_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or not user.is_admin: raise HTTPException(403, "Admin only")
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(404, "User not found")
        
    if target_user.email == ADMIN_EMAIL:
        raise HTTPException(400, "The primary admin account cannot be deleted.")
        
    db.query(Payment).filter(Payment.user_id == user_id).delete()
    db.query(JobLink).filter(JobLink.taken_by == user_id).update({"status": "available", "taken_by": None})
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    return RedirectResponse("/admin", status_code=302)

@router.post("/admin/approve-payment/{payment_id}")
def admin_approve_payment(request: Request, payment_id: int, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or not user.is_admin: raise HTTPException(403, "Admin only")
        
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment and payment.status == "pending":
        payment.status = "success"
        if payment.job_link_id:
            link = db.query(JobLink).filter(JobLink.id == payment.job_link_id).first()
            if link and link.status == "available":
                link.status = "taken"
                link.taken_by = payment.user_id
        db.commit()
    return RedirectResponse("/admin", status_code=302)

@router.post("/admin/archive")
def admin_archive(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or not user.is_admin: raise HTTPException(403, "Admin only")
    config = db.query(SystemConfig).first()
    if config:
        config.current_batch += 1
        db.commit()
    return RedirectResponse("/admin", status_code=302)

@router.post("/admin/make-admin/{user_id}")
def admin_make_admin(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or not user.is_admin: raise HTTPException(403, "Admin only")
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(404, "User not found")
        
    target_user.is_admin = True
    db.commit()
    return RedirectResponse("/admin", status_code=302)