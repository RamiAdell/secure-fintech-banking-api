from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from loguru import logger


def send_virtual_card_topup_email(user, virtual_card, amount, new_balance):
    subject = "Virtual Card Top-Up Confirmation"
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = user.email

    context = {
        "user_full_name": user.full_name,
        "card_last_four": virtual_card.card_number[-4:],
        "amount": amount,
        "new_balance": new_balance,
        "currency": virtual_card.bank_account.currency,
        "site_name": settings.SITE_NAME,
    }
    html_email = render_to_string("emails/virtual_card_topup.html", context)
    text_email = strip_tags(html_email)

    msg = EmailMultiAlternatives(subject, text_email, from_email, [to_email])

    try:
        msg.send()
        logger.info(f"Virtual card top-up email sent to {user.email}")
    except Exception as e:
        logger.error(
            f"Failed to send virtual card top-up email to {user.email}: {str(e)}"
        )