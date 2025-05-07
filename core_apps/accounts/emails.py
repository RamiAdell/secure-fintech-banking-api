from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from loguru import logger
from core_apps.accounts.models import BankAccount


def send_account_creation_email(user, bank_account):
    subject = _("Your New Bank Account has been Created")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    context = {"user": user, "account": bank_account, "site_name": settings.SITE_NAME}
    html_email = render_to_string("emails/account_created.html", context)
    plain_email = strip_tags(html_email)
    email = EmailMultiAlternatives(subject, plain_email, from_email, recipient_list)
    email.attach_alternative(html_email, "text/html")
    try:
        email.send()
        logger.info(f"Account Created email sent to: {user.email}")
    except Exception as e:
        logger.error(f"Failed to send account created email to {email}: Error: {str(e)}")


def send_full_activation_email(account: BankAccount) -> None:
    subject = _("Your Bank Account is now fully activated")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [account.user.email]
    context = {"account": account, "site_name": settings.SITE_NAME}
    html_email = render_to_string("emails/bank_account_activated.html", context)
    plain_email = strip_tags(html_email)
    email = EmailMultiAlternatives(subject, plain_email, from_email, recipient_list)
    email.attach_alternative(html_email, "text/html")
    try:
        email.send()
        logger.info(f"Account Fully Activated email sent to: {account.user.email}")
    except Exception as e:
        logger.error(f"Failed to send Fully Activated email to  {account.user.email}: Error: {str(e)}")


def send_deposit_email(user, user_email, amount, currency, new_balance, account_number) -> None:
    subject = _("Deposit Confirmation")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]

    context = {
        "user": user,
        "amount": amount,
        "currency": currency,
        "new_balance": new_balance,
        "account_number": account_number,
        "site_name": settings.SITE_NAME,
    }

    html_email = render_to_string("emails/deposit_confirmation.html", context)
    plain_email = strip_tags(html_email)
    email = EmailMultiAlternatives(subject, plain_email, from_email, recipient_list)
    email.attach_alternative(html_email, "text/html")
    try:
        email.send()
        logger.info(f"Deposit Confirmation email sent to: {user_email}")
    except Exception as e:
        logger.error(f"Failed to send deposit confirmation email to  {user_email}. Error: {str(e)}")


def send_withdrawal_email( user, user_email, amount, currency, new_balance, account_number) -> None:
    subject = _("Withdrawal Confirmation")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]
    context = {
        "user": user,
        "amount": amount,
        "currency": currency,
        "new_balance": new_balance,
        "account_number": account_number,
        "site_name": settings.SITE_NAME,
    }
    html_email = render_to_string("emails/withdrawal_confirmation.html", context)
    plain_email = strip_tags(html_email)
    email = EmailMultiAlternatives(subject, plain_email, from_email, recipient_list)
    email.attach_alternative(html_email, "text/html")
    try:
        email.send()
        logger.info(f"Withdrawal Confirmation email sent to: {user_email}")
    except Exception as e:
        logger.error(f"Failed to send withdrawal confirmation email to  {user_email}. Error: {str(e)}")


def send_transfer_email(
    sender_name,
    sender_email,
    receiver_name,
    receiver_email,
    amount,
    currency,
    sender_new_balance,
    receiver_new_balance,
    sender_account_number,
    receiver_account_number,
) -> None:
    subject = _("Transfer Notification")
    from_email = settings.DEFAULT_FROM_EMAIL

    common_context = {
        "amount": amount,
        "currency": currency,
        "sender_account_number": sender_account_number,
        "receiver_account_number": receiver_account_number,
        "sender_name": sender_name,
        "receiver_name": receiver_name,
        "site_name": settings.SITE_NAME,
    }

    sender_context = {
        **common_context,
        "user": sender_name,
        "is_sender": True,
        "new_balance": sender_new_balance,
    }
    sender_html_email = render_to_string(
        "emails/transfer_notification.html", sender_context
    )
    sender_plain_email = strip_tags(sender_html_email)
    sender_email_obj = EmailMultiAlternatives(
        subject, sender_plain_email, from_email, [sender_email]
    )
    sender_email_obj.attach_alternative(sender_html_email, "text/html")
    receiver_context = {
        **common_context,
        "user": receiver_name,
        "is_sender": False,
        "new_balance": receiver_new_balance,
    }
    receiver_html_email = render_to_string(
        "emails/transfer_notification.html", receiver_context
    )
    receiver_plain_email = strip_tags(receiver_html_email)
    receiver_email_obj = EmailMultiAlternatives(
        subject, receiver_plain_email, from_email, [receiver_email]
    )
    receiver_email_obj.attach_alternative(receiver_html_email, "text/html")
    try:
        sender_email_obj.send()
        receiver_email_obj.send()
        logger.info(
            f"Transfer notification emails sent to sender: {sender_email} and receiver: "
            f"{receiver_email}"
        )
    except Exception as e:
        logger.error(f"Failed to send transfer notification emails. Error: {str(e)}")


def send_transfer_otp_email(email, otp) -> None:
    subject = _("Your OTP for Transfer Authorization")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]
    context = {
        "otp": otp,
        "expiry_time": settings.OTP_EXPIRATION,
        "site_name": settings.SITE_NAME,
    }
    html_email = render_to_string("emails/transfer_otp_email.html", context)
    plain_email = strip_tags(html_email)
    email = EmailMultiAlternatives(subject, plain_email, from_email, recipient_list)
    email.attach_alternative(html_email, "text/html")
    try:
        email.send()
        logger.info(f"OTP email sent successfully to: {email}")
    except Exception as e:
        logger.error(f"Failed to send OTP email email to  {email}. Error: {str(e)}")


def send_suspicious_activity_alert(suspicious_activities):
    subject = _("Suspicious Activity Alert")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [settings.ADMIN_EMAIL]

    context = {
        "suspicious_activities": suspicious_activities,
        "site_name": settings.SITE_NAME,
    }
    html_email = render_to_string("emails/suspicious_activity_alert.html", context)
    plain_email = strip_tags(html_email)

    email = EmailMultiAlternatives(subject, plain_email, from_email, recipient_list)
    email.attach_alternative(html_email, "text/html")

    try:
        email.send()
        logger.info(
            f"Suspicious activity alert sent successfully to: {settings.ADMIN_EMAIL}"
        )
        return len(suspicious_activities)
    except Exception as e:
        logger.error(
            f"Failed to send suspicious activity alert to  {settings.ADMIN_EMAIL}. Error: {str(e)}"
        )
        return 0