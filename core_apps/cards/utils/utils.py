import hashlib
import hmac
import random
from os import getenv

BANK_CARD_PREFIX = getenv("BANK_CARD_PREFIX")
BANK_CARD_CODE = getenv("BANK_CARD_CODE")


def generate_card_number( prefix=BANK_CARD_PREFIX, card_code=BANK_CARD_CODE, length=16) -> str:
    
    total_prefix = prefix + card_code
    random_digits_length = length - len(total_prefix) - 1

    if random_digits_length < 0:
        raise ValueError(f"Prefix and code are too long for the specified card length")

    number = total_prefix

    number += "".join([str(random.randint(0, 9)) for _ in range(random_digits_length)])

    digits = [int(d) for d in number]

    for i in range(len(digits) - 1, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9

    check_digit = (10 - sum(digits) % 10) % 10

    return number + str(check_digit)


def generate_cvv(card_number, expiry_date):
    secret_key = getenv("CVV_SECRET_KEY").encode()

    data = f"{card_number}{expiry_date}".encode()

    hmac_obj = hmac.new(secret_key, data, hashlib.sha256)

    cvv = str(int(hmac_obj.hexdigest(), 16))[:3]

    return cvv.zfill(3)