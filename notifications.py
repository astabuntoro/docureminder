"""
Notification helpers — web push + Gmail SMTP email.
Called by the APScheduler daily job AND manually from routes.
"""
import json, smtplib, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pywebpush import webpush, WebPushException
from flask import current_app
from datetime import date

log = logging.getLogger(__name__)


# ── Web Push ───────────────────────────────────────────────────────────────────
def send_push(subscription, title, body, url='/'):
    """Send a single Web Push notification to one subscription."""
    data = json.dumps({'title': title, 'body': body, 'url': url})
    try:
        webpush(
            subscription_info={
                'endpoint': subscription.endpoint,
                'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
            },
            data=data,
            vapid_private_key=current_app.config['VAPID_PRIVATE_KEY'],
            vapid_claims={'sub': f"mailto:{current_app.config['VAPID_CLAIMS_EMAIL']}"},
        )
        return True
    except WebPushException as e:
        log.warning(f"Push failed for sub {subscription.id}: {e}")
        return False
    except Exception as e:
        log.error(f"Push error: {e}")
        return False


# ── Email ──────────────────────────────────────────────────────────────────────
def send_email(gmail_address, gmail_app_password, to_email, subject, html_body):
    """Send email via Gmail SMTP using App Password."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"DocuReminder <{gmail_address}>"
        msg['To']      = to_email
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.ehlo()
            s.starttls()
            s.login(gmail_address, gmail_app_password)
            s.sendmail(gmail_address, to_email, msg.as_string())
        return True
    except Exception as e:
        log.error(f"Email error: {e}")
        return False


def email_html(user_name, docs):
    """Build reminder email HTML body."""
    rows = ''
    for d in docs:
        color = {'active':'#16a34a','warning':'#d97706','critical':'#dc2626','expired':'#6b7280'}[d.status]
        days  = f"{d.days_left} hari lagi" if d.days_left >= 0 else f"Lewat {abs(d.days_left)} hari"
        rows += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{d.name}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{d.doc_type}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;">{d.expiry_date.strftime('%d %b %Y')}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #e2e8f0;color:{color};font-weight:600;">{days}</td>
        </tr>"""
    return f"""
    <div style="font-family:'Segoe UI',sans-serif;max-width:600px;margin:0 auto;background:#f0f4f8;padding:24px;">
      <div style="background:#1a1a2e;border-radius:12px 12px 0 0;padding:24px;text-align:center;">
        <h1 style="color:#fff;font-size:22px;margin:0;">🗂️ DocuReminder</h1>
        <p style="color:rgba(255,255,255,.6);margin:6px 0 0;font-size:13px;">Pengingat Masa Berlaku Dokumen</p>
      </div>
      <div style="background:#fff;padding:24px;border-radius:0 0 12px 12px;">
        <p style="font-size:15px;color:#1e293b;">Halo <strong>{user_name}</strong>,</p>
        <p style="color:#64748b;font-size:14px;margin-bottom:20px;">
          Berikut dokumen yang perlu perhatian Anda:
        </p>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <thead>
            <tr style="background:#f8fafc;">
              <th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;">Dokumen</th>
              <th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;">Tipe</th>
              <th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;">Berlaku s/d</th>
              <th style="padding:10px 12px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;">Sisa</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="margin-top:24px;font-size:13px;color:#64748b;">
          Segera perpanjang dokumen Anda sebelum kedaluwarsa.<br>
          Login ke DocuReminder untuk detail lebih lanjut.
        </p>
      </div>
      <p style="text-align:center;font-size:11px;color:#94a3b8;margin-top:16px;">
        DocuReminder &mdash; Semua dokumen penting, satu tempat.
      </p>
    </div>"""


# ── Scheduler job ──────────────────────────────────────────────────────────────
def run_daily_notifications(app):
    """
    Called by APScheduler every day at 08:00.
    Checks all users' documents and fires push + email as needed.
    """
    from models import User, Document, PushSubscription
    with app.app_context():
        users = User.query.all()
        for user in users:
            thresholds = user.notify_days_list
            docs_to_notify = [
                d for d in user.documents
                if d.days_left in thresholds or (d.days_left < 0 and d.days_left >= -1)
            ]
            if not docs_to_notify:
                continue

            # Web push
            if user.push_notify:
                for sub in user.push_subs:
                    names = ', '.join(d.name for d in docs_to_notify[:3])
                    extra = f' +{len(docs_to_notify)-3} lainnya' if len(docs_to_notify) > 3 else ''
                    send_push(sub,
                              title='⏰ DocuReminder — Dokumen Perlu Perhatian',
                              body=f'{names}{extra} segera berakhir.',
                              url='/')

            # Email
            if user.email_notify and user.gmail_address and user.gmail_app_password:
                send_email(
                    gmail_address=user.gmail_address,
                    gmail_app_password=user.gmail_app_password,
                    to_email=user.email,
                    subject=f'⏰ DocuReminder — {len(docs_to_notify)} dokumen perlu perhatian',
                    html_body=email_html(user.name, docs_to_notify),
                )
        log.info("Daily notification job done.")
