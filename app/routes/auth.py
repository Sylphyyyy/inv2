import hashlib
import secrets
import smtplib
import time
from email.message import EmailMessage

from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, session
from sqlalchemy import update
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)
RESET_TOKEN_TTL_SECONDS = 3600
RESET_REQUEST_COOLDOWN_SECONDS = 60


def _send_password_reset_email(recipient, reset_url):
    config = current_app.config
    if not config['MAIL_SERVER'] or not config['MAIL_DEFAULT_SENDER']:
        current_app.logger.warning(
            'SMTP is not configured; password reset link not emailed to %s. '
            'Reset link: %s',
            recipient, reset_url,
        )
        return False
    if bool(config['MAIL_USERNAME']) != bool(config['MAIL_PASSWORD']):
        raise RuntimeError('MAIL_USERNAME and MAIL_PASSWORD must both be configured or both omitted.')

    message = EmailMessage()
    message['Subject'] = 'Reset your Inventory Procurement System password'
    message['From'] = config['MAIL_DEFAULT_SENDER']
    message['To'] = recipient
    message.set_content(
        'A password reset was requested for your account. '
        'Use the link below within one hour to choose a new password:\n\n'
        f'{reset_url}\n\n'
        'If you did not request this, you can ignore this email.'
    )

    if config['MAIL_PORT'] == 465:
        with smtplib.SMTP_SSL(config['MAIL_SERVER'], config['MAIL_PORT'], timeout=10) as smtp:
            if config['MAIL_USERNAME']:
                smtp.login(config['MAIL_USERNAME'], config['MAIL_PASSWORD'])
            smtp.send_message(message)
    else:
        with smtplib.SMTP(config['MAIL_SERVER'], config['MAIL_PORT'], timeout=10) as smtp:
            smtp.starttls()
            if config['MAIL_USERNAME']:
                smtp.login(config['MAIL_USERNAME'], config['MAIL_PASSWORD'])
            smtp.send_message(message)
    return True

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Logged in successfully.', 'success')
            return redirect(url_for('inventory.index'))
        
        flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        users = User.query.filter(db.func.lower(User.email) == email).limit(2).all()
        if len(users) == 1:
            user = users[0]
            now = int(time.time())
            last_requested_at = (
                user.reset_token_expires_at - RESET_TOKEN_TTL_SECONDS
                if user.reset_token_expires_at
                else 0
            )
            if now - last_requested_at >= RESET_REQUEST_COOLDOWN_SECONDS:
                token = secrets.token_urlsafe(32)
                user.reset_token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
                user.reset_token_expires_at = now + RESET_TOKEN_TTL_SECONDS
                db.session.commit()

                reset_path = url_for('auth.reset_password', token=token)
                reset_url = request.url_root.rstrip('/') + reset_path
                try:
                    sent = _send_password_reset_email(user.email, reset_url)
                except (OSError, smtplib.SMTPException, RuntimeError):
                    current_app.logger.exception('Unable to send password reset email.')
                    sent = False
                if sent:
                    flash('If an account uses that email, a password reset link has been sent.', 'success')
                    return redirect(url_for('auth.login'))
                # Email could not be sent: show the link directly (no SMTP configured)
                flash('Reset link (copy and open it):', 'warning')
                return render_template('auth/forgot_password.html', reset_url=reset_url)

        flash('If an account uses that email, a password reset link has been sent.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    now = int(time.time())
    user = User.query.filter_by(reset_token_hash=token_hash).first()
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at <= now:
        flash('That password reset link is invalid or has expired. Request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirmation = request.form.get('confirm_password', '')
        if len(password) < 12 or len(password) > 128:
            flash('Choose a password between 12 and 128 characters.', 'danger')
        elif password != confirmation:
            flash('The passwords do not match.', 'danger')
        else:
            result = db.session.execute(
                update(User)
                .where(
                    User.id == user.id,
                    User.reset_token_hash == token_hash,
                    User.reset_token_expires_at > now,
                )
                .values(
                    password_hash=generate_password_hash(password),
                    reset_token_hash=None,
                    reset_token_expires_at=None,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                db.session.rollback()
                flash('That password reset link is invalid or has expired. Request a new one.', 'danger')
                return redirect(url_for('auth.forgot_password'))
            db.session.commit()
            flash('Your password has been changed. You can now log in.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))