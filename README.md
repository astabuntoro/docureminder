# DocuReminder 🗂️

Aplikasi pengingat masa berlaku dokumen penting — multi-user, dengan push notification & email reminder.

## Instalasi

```bash
pip install flask flask-sqlalchemy flask-login flask-bcrypt pywebpush apscheduler reportlab Pillow
```

## Jalankan

```bash
cd docureminder
python app.py
```

Buka: http://localhost:5000

## Halaman

| URL | Keterangan |
|-----|-----------|
| `/` | Redirect ke landing / dashboard |
| `/landing` | Landing page |
| `/register` | Daftar akun baru |
| `/login` | Login |
| `/app` | Dashboard dokumen |
| `/app/settings` | Pengaturan notifikasi & Gmail |

## Setup Email Reminder (Gmail SMTP)

1. Buka https://myaccount.google.com/apppasswords
2. Buat App Password baru (pilih "Mail")
3. Isi di Settings → Gmail Address + App Password
4. Klik "Test Kirim Email" untuk verifikasi

## Setup Push Notification

1. Login ke app
2. Klik "Aktifkan" di banner yang muncul, atau ke Settings
3. Izinkan notifikasi di browser
4. Test via tombol "Test Push" di Settings

## Scheduler

APScheduler berjalan otomatis setiap hari jam 08:00 WIB.
Dokumen dengan sisa hari sesuai `notify_days` (default: 90,30,7,1) akan memicu notifikasi.

## Akun Demo

```
Email:    budi@test.com
Password: password123
```
