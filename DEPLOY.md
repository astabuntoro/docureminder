# Deploy DocuReminder ke Render

## Langkah-langkah

### 1. Push ke GitHub (kalau belum)

```bash
git add .
git commit -m "fix: auto create db tables on startup"
git push
```

### 2. Daftar & setup Render

1. Buka [render.com](https://render.com) → **Sign up with GitHub**
2. Klik **New +** → **Web Service**
3. Pilih repo `docureminder`
4. Isi form:
   - **Name**: docureminder
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Klik **Create Web Service**

### 3. Tambah PostgreSQL

1. Klik **New +** → **PostgreSQL**
2. Isi nama, pilih region terdekat (Singapore)
3. Klik **Create Database**
4. Setelah selesai, klik database → copy **Internal Database URL**

### 4. Set Environment Variables

Di Render → Web Service → **Environment**, tambahkan:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Internal Database URL dari step 3 |
| `SECRET_KEY` | jalanin `python -c "import secrets; print(secrets.token_hex(32))"` |
| `VAPID_PRIVATE_KEY` | lihat .env.example |
| `VAPID_PUBLIC_KEY` | lihat .env.example |
| `VAPID_CLAIMS_EMAIL` | email lo |
| `CLOUDINARY_CLOUD_NAME` | dari cloudinary.com |
| `CLOUDINARY_API_KEY` | dari cloudinary.com |
| `CLOUDINARY_API_SECRET` | dari cloudinary.com |

### 5. Deploy

Render otomatis deploy. Dapat domain gratis:
`https://docureminder.onrender.com`

---

## Catatan

- Free tier Render spin down setelah 15 menit tidak ada request — request pertama agak lambat (~30 detik)
- Untuk menghindari spin down, upgrade ke plan $7/bulan atau pakai UptimeRobot (gratis) untuk ping app tiap 10 menit
