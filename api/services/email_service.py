"""
Email service for sending transactional emails.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
from config import settings


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_USER

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str = None
    ) -> bool:
        """
        Send an email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body (fallback)

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.from_email
            message["To"] = to_email

            # Add plain text version if provided
            if text_content:
                part1 = MIMEText(text_content, "plain")
                message.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_content, "html")
            message.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)

            print(f"[INFO] Email sent successfully to {to_email}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to send email to {to_email}: {e}")
            return False

    def send_confirmation_email(self, to_email: str, token: str) -> bool:
        """
        Send email confirmation link.

        Args:
            to_email: User's email address
            token: Confirmation token

        Returns:
            True if email sent successfully
        """
        confirmation_link = f"{settings.FRONTEND_URL}/confirm-email?token={token}"

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Welcome to Surf Tracker!</h2>
                <p>Thank you for registering. Please confirm your email address by clicking the link below:</p>
                <p>
                    <a href="{confirmation_link}"
                       style="background-color: #0066cc; color: white; padding: 10px 20px;
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Confirm Email
                    </a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p><a href="{confirmation_link}">{confirmation_link}</a></p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't create an account, you can safely ignore this email.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">Surf Tracker - AI-powered surf performance analysis</p>
            </body>
        </html>
        """

        text_content = f"""
        Welcome to Surf Tracker!

        Thank you for registering. Please confirm your email address by clicking the link below:

        {confirmation_link}

        This link will expire in 24 hours.

        If you didn't create an account, you can safely ignore this email.
        """

        return self.send_email(
            to_email=to_email,
            subject="Confirm your Surf Tracker email",
            html_content=html_content,
            text_content=text_content
        )

    def send_password_reset_email(self, to_email: str, token: str) -> bool:
        """
        Send password reset link.

        Args:
            to_email: User's email address
            token: Password reset token

        Returns:
            True if email sent successfully
        """
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Password Reset Request</h2>
                <p>You requested to reset your password. Click the link below to create a new password:</p>
                <p>
                    <a href="{reset_link}"
                       style="background-color: #0066cc; color: white; padding: 10px 20px;
                              text-decoration: none; border-radius: 5px; display: inline-block;">
                        Reset Password
                    </a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p><a href="{reset_link}">{reset_link}</a></p>
                <p>This link will expire in 1 hour.</p>
                <p>If you didn't request a password reset, you can safely ignore this email.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">Surf Tracker - AI-powered surf performance analysis</p>
            </body>
        </html>
        """

        text_content = f"""
        Password Reset Request

        You requested to reset your password. Click the link below to create a new password:

        {reset_link}

        This link will expire in 1 hour.

        If you didn't request a password reset, you can safely ignore this email.
        """

        return self.send_email(
            to_email=to_email,
            subject="Reset your Surf Tracker password",
            html_content=html_content,
            text_content=text_content
        )


# Global email service instance
email_service = EmailService()
