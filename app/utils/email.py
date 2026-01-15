import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.settings import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME
        self.use_tls = settings.SMTP_TLS
        self.use_ssl = settings.SMTP_SSL

    def _get_connection(self):
        """Create SMTP connection"""
        if self.use_ssl:
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        else:
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            if self.use_tls:
                server.starttls()
        
        if self.smtp_user and self.smtp_password:
            server.login(self.smtp_user, self.smtp_password)
        
        return server

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email

            if text_content:
                part1 = MIMEText(text_content, 'plain')
                msg.attach(part1)

            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)

            # In debug mode without SMTP config, just log
            if settings.DEBUG and not self.smtp_user:
                logger.info(f"[DEBUG] Would send email to {to_email}: {subject}")
                logger.debug(f"[DEBUG] Email content: {html_content}")
                return True

            with self._get_connection() as server:
                server.sendmail(self.from_email, to_email, msg.as_string())
            
            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            if settings.DEBUG:
                logger.info(f"[DEBUG MODE] Email would have been sent to {to_email}")
                return True  # Don't fail in debug mode
            return False


# Global email service instance
email_service = EmailService()


def _build_email_template(title: str, body: str) -> str:
    """Build a simple HTML email template"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .button {{ 
                display: inline-block; 
                background-color: #4F46E5; 
                color: white; 
                padding: 12px 24px; 
                text-decoration: none; 
                border-radius: 4px; 
                margin: 20px 0;
            }}
            .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{settings.PROJECT_NAME}</h1>
        </div>
        <div class="content">
            {body}
        </div>
        <div class="footer">
            <p>© {settings.PROJECT_NAME}. All rights reserved.</p>
            <p>If you didn't request this email, please ignore it.</p>
        </div>
    </body>
    </html>
    """


def send_verification_email(email: str, token: str) -> bool:
    """Send email verification email"""
    verification_url = f"{settings.BACKEND_URL}{settings.API_V1_STR}/auth/verify-email?token={token}"
    
    body = f"""
        <h2>Welcome!</h2>
        <p>Please verify your email address by clicking the button below:</p>
        <p style="text-align: center;">
            <a href="{verification_url}" class="button">Verify Email</a>
        </p>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #4F46E5;">{verification_url}</p>
        <p><strong>This link will expire in {settings.VERIFICATION_TOKEN_EXPIRE_HOURS} hours.</strong></p>
    """
    
    html_content = _build_email_template("Verify Your Email", body)
    
    return email_service.send_email(
        to_email=email,
        subject=f"Verify your email for {settings.PROJECT_NAME}",
        html_content=html_content
    )


def send_password_reset_email(email: str, token: str) -> bool:
    """Send password reset email"""
    reset_url = f"{settings.BACKEND_URL}{settings.API_V1_STR}/auth/reset-password?token={token}"
    
    body = f"""
        <h2>Password Reset Request</h2>
        <p>You requested to reset your password. Click the button below to proceed:</p>
        <p style="text-align: center;">
            <a href="{reset_url}" class="button">Reset Password</a>
        </p>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #4F46E5;">{reset_url}</p>
        <p><strong>This link will expire in {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hour(s).</strong></p>
        <p>If you didn't request this, please ignore this email. Your password will remain unchanged.</p>
    """
    
    html_content = _build_email_template("Password Reset", body)
    
    return email_service.send_email(
        to_email=email,
        subject=f"Password Reset for {settings.PROJECT_NAME}",
        html_content=html_content
    )


def send_password_changed_email(email: str) -> bool:
    """Send password changed notification"""
    body = """
        <h2>Password Changed Successfully</h2>
        <p>Your password has been successfully changed.</p>
        <p>If you did not make this change, please contact support immediately and secure your account.</p>
    """
    
    html_content = _build_email_template("Password Changed", body)
    
    return email_service.send_email(
        to_email=email,
        subject=f"Password Changed - {settings.PROJECT_NAME}",
        html_content=html_content
    )


def send_email_change_verification(new_email: str, token: str) -> bool:
    """Send email change verification"""
    verification_url = f"{settings.BACKEND_URL}{settings.API_V1_STR}/auth/verify-email?token={token}"
    
    body = f"""
        <h2>Verify Your New Email Address</h2>
        <p>Please verify your new email address by clicking the button below:</p>
        <p style="text-align: center;">
            <a href="{verification_url}" class="button">Verify New Email</a>
        </p>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #4F46E5;">{verification_url}</p>
        <p><strong>This link will expire in {settings.VERIFICATION_TOKEN_EXPIRE_HOURS} hours.</strong></p>
    """
    
    html_content = _build_email_template("Verify New Email", body)
    
    return email_service.send_email(
        to_email=new_email,
        subject=f"Verify your new email for {settings.PROJECT_NAME}",
        html_content=html_content
    )


def send_account_deleted_email(email: str) -> bool:
    """Send account deletion confirmation"""
    body = """
        <h2>Account Deleted</h2>
        <p>Your account has been successfully deleted.</p>
        <p>We're sorry to see you go. All your data has been permanently removed from our systems.</p>
        <p>If you change your mind, you're always welcome to create a new account.</p>
    """
    
    html_content = _build_email_template("Account Deleted", body)
    
    return email_service.send_email(
        to_email=email,
        subject=f"Account Deleted - {settings.PROJECT_NAME}",
        html_content=html_content
    )


def send_security_alert_email(email: str, message: str) -> bool:
    """Send security alert"""
    body = f"""
        <h2>⚠️ Security Alert</h2>
        <p style="background-color: #FEF2F2; border-left: 4px solid #EF4444; padding: 15px;">
            {message}
        </p>
        <p>If this was you, no action is needed.</p>
        <p>If this wasn't you, please:</p>
        <ul>
            <li>Change your password immediately</li>
            <li>Review your recent account activity</li>
            <li>Contact support if you notice any suspicious activity</li>
        </ul>
    """
    
    html_content = _build_email_template("Security Alert", body)
    
    return email_service.send_email(
        to_email=email,
        subject=f"🔒 Security Alert - {settings.PROJECT_NAME}",
        html_content=html_content
    )