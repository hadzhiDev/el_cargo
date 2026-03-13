from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from whatsapp_api_client_python import API

from .models import Load

greenAPI = API.GreenAPI(
    settings.GREEN_API_ID,
    settings.GREEN_API_TOKEN
)


@receiver(post_save, sender=Load)
def send_whatsapp_on_load_save(sender, instance, created, **kwargs):
    """
    Send WhatsApp message when Load is saved and has a client.
    """

    if instance.sent_to_client:
        return

    client = instance.client

    if not client:
        return

    if not client.whatsapp_chat_id:
        return

    chat_id = client.whatsapp_chat_id

    message = f"""👋 Ассалоому Алейкум, урматтуу кардар. Код {client.code}, {instance.date} — Складка жүгүңүз келип түштү!

🔢 Трек номер:
{instance.code}

💰 Төлөм суммасы: {instance.price} сом

📍 Дарек: Карасуйская 13а. Ошский район, Мээрим ресторандын жанында.
🕒 Иштөө убактысы: 11:00 — 18:00
📅 Жумуш күндөрү: Дүйшөмбүдөн ишембиге чейин

🤝 Урматтоо менен, EL CARGO
📞 Тел: 0772901547
"""

    try:
        response = greenAPI.sending.sendMessage(chat_id, message)
        print(response.code)
        print(response.data)
        if response.code == 200:
            instance.sent_to_client = True
            instance.save(update_fields=["sent_to_client"])

    except Exception as e:
        print("WhatsApp send error:", e)