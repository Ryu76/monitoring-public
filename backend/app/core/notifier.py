import logging
import json
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

class Notifier:
    """알림 채널 연동 모듈 (Email, SMS, Slack 등)"""

    @staticmethod
    def send_email(to_address: str, subject: str, body: str):
        # 실제 구현 시 smtplib 등을 사용하여 발송합니다.
        logger.info(f"📧 [EMAIL SENT] To: {to_address} | Subject: {subject} | Body: {body}")

    @staticmethod
    def send_sms(phone_number: str, message: str):
        # 실제 구현 시 알리고, Twilio 등의 SMS API를 호출합니다.
        logger.info(f"📱 [SMS SENT] To: {phone_number} | Message: {message}")

    @staticmethod
    def send_slack(webhook_url: str, message: str):
        # Slack Webhook 연동
        payload = {"text": message}
        try:
            if not webhook_url or not webhook_url.startswith("http"):
                logger.info(f"💬 [SLACK SENT] (Mock) Message: {message}")
                return

            req = urllib.request.Request(webhook_url)
            req.add_header('Content-Type', 'application/json; charset=utf-8')
            jsondata = json.dumps(payload)
            jsondataasbytes = jsondata.encode('utf-8')
            req.add_header('Content-Length', str(len(jsondataasbytes)))
            
            with urllib.request.urlopen(req, jsondataasbytes, timeout=5) as response:
                if response.status == 200:
                    logger.info("💬 [SLACK SENT] Successfully sent to Slack webhook.")
                else:
                    logger.error(f"Failed to send Slack: {response.status}")
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")

    @classmethod
    def dispatch(cls, channel: str, target: str, title: str, message: str):
        """채널 코드에 따라 적절한 발송기 호출"""
        channel = channel.upper()
        if channel == 'EMAIL':
            cls.send_email(target, title, message)
        elif channel == 'SMS':
            cls.send_sms(target, message)
        elif channel == 'SLACK':
            cls.send_slack(target, f"*{title}*\n{message}")
        else:
            logger.warning(f"Unknown notification channel: {channel}. Defaulting to console log.")
            logger.info(f"[{channel} SENT] {title} - {message}")
