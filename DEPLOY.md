# Deploy DocuReminder ke Railway

## Langkah-langkah

### 1. Push ke GitHub

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/username/docureminder.git
git push -u origin main
```

### 2. Setup di Railway

1. Buka [railway.app](https://railway.app) → Login dengan GitHub
2. Klik **New Project** → **Deploy from GitHub repo**
3. Pilih repo DocuReminder

Railway akan otomatis detect Python dan install `requirements.txt`.

### 3. Tambah PostgreSQL

Di Railway dashboard:
1. Klik **+ New** → **Database** → **PostgreSQL**
2. Railway otomatis set `DATABASE_URL` ke environment variables

### 4. Set Environment Variables

Di Railway → project → **Variables**, tambahkan:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | random string panjang (pakai: `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `VAPID_PRIVATE_KEY` | generate ulang (lihat .env.example) |
| `VAPID_PUBLIC_KEY` | generate ulang |
| `VAPID_CLAIMS_EMAIL` | email lo |
| `CLOUDINARY_CLOUD_NAME` | dari dashboard cloudinary.com |
| `CLOUDINARY_API_KEY` | dari dashboard cloudinary.com |
| `CLOUDINARY_API_SECRET` | dari dashboard cloudinary.com |

### 5. Setup Cloudinary (untuk upload foto)

1. Daftar gratis di [cloudinary.com](https://cloudinary.com)
2. Buka dashboard → copy Cloud Name, API Key, API Secret
3. Masukkan ke Railway Variables (langkah 4)

### 6. Deploy

Railway akan otomatis redeploy setiap kali lo push ke GitHub.
Domain gratis format: `https://docureminder-xxxx.railway.app`

---

## Catatan

- **Database** — Railway PostgreSQL persist permanen, tidak hilang seperti SQLite
- **File uploads** — tersimpan di Cloudinary, tidak hilang saat redeploy
- **Push notification** — generate VAPID keys baru untuk production (jangan pakai yang dev)
- **Email reminder** — scheduler jalan otomatis tiap hari jam 08:00 WIB
