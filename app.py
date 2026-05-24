import os, io, uuid, json, logging, urllib.request, tempfile
from datetime import datetime, date, timedelta

from flask import (Flask, render_template, request, redirect,
                   url_for, send_file, flash, jsonify, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from apscheduler.schedulers.background import BackgroundScheduler
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable,
                                 Image as RLImage)
from reportlab.lib.units import cm
from PIL import Image as PILImage

from config import Config
from models import db, bcrypt, User, Document, PushSubscription
from notifications import send_push, send_email, email_html, run_daily_notifications

# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
bcrypt.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view       = 'login'
login_manager.login_message    = 'Silakan login terlebih dahulu.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

# ── Scheduler ──────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone='Asia/Jakarta')
scheduler.add_job(run_daily_notifications, 'cron',
                  hour=8, minute=0, args=[app])
scheduler.start()

# ── Constants ──────────────────────────────────────────────────────────────────
DOC_TYPES    = ['SIM','STNK','Paspor','Asuransi','KTP','BPJS','Visa','Lainnya']
ALLOWED_EXT  = {'png','jpg','jpeg','gif','webp'}
PAGE_W       = A4[0] - 4*cm

STATUS_COLORS = {
    'active':   colors.HexColor('#16a34a'),
    'warning':  colors.HexColor('#d97706'),
    'critical': colors.HexColor('#dc2626'),
    'expired':  colors.HexColor('#6b7280'),
}

# ── Cloudinary setup ───────────────────────────────────────────────────────────
if Config.USE_CLOUDINARY:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name = Config.CLOUDINARY_CLOUD_NAME,
        api_key    = Config.CLOUDINARY_API_KEY,
        api_secret = Config.CLOUDINARY_API_SECRET,
    )

@app.context_processor
def inject_helpers():
    return dict(get_upload_url=get_upload_url)

# ── Upload helpers ─────────────────────────────────────────────────────────────
def allowed(fn):
    return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED_EXT

def save_upload(f):
    """Save to Cloudinary in production, local folder in dev. Returns identifier."""
    if app.config['USE_CLOUDINARY']:
        result = cloudinary.uploader.upload(f, folder='docureminder')
        return result['public_id']          # e.g. "docureminder/abc123"
    else:
        ext   = f.filename.rsplit('.',1)[1].lower()
        fname = f"{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        return fname

def get_upload_url(identifier):
    """Get URL for serving an uploaded file."""
    if app.config['USE_CLOUDINARY']:
        import cloudinary.utils
        url, _ = cloudinary.utils.cloudinary_url(identifier, secure=True)
        return url
    return url_for('uploaded_file', filename=identifier)

def handle_uploads(existing=None):
    files = list(existing or [])
    for f in request.files.getlist('doc_files'):
        if f and f.filename and allowed(f.filename):
            files.append(save_upload(f))
    return files

def delete_uploads(identifiers):
    for ident in identifiers:
        if app.config['USE_CLOUDINARY']:
            try:
                cloudinary.uploader.destroy(ident)
            except Exception:
                pass
        else:
            p = os.path.join(app.config['UPLOAD_FOLDER'], ident)
            if os.path.exists(p): os.remove(p)

# ── PDF helpers ────────────────────────────────────────────────────────────────
def image_flowable(identifier, max_w, max_h):
    """Load image from local path or Cloudinary URL for PDF embedding."""
    try:
        if app.config['USE_CLOUDINARY']:
            url = get_upload_url(identifier)
            with urllib.request.urlopen(url) as resp:
                data = resp.read()
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            tmp.write(data); tmp.close()
            filepath = tmp.name
        else:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], identifier)

        with PILImage.open(filepath) as im:
            w, h = im.size
        r = min(max_w/w, max_h/h)
        return RLImage(filepath, width=w*r, height=h*r)
    except Exception:
        return None

def generate_pdf(docs, title):
    buf     = io.BytesIO()
    doc_tpl = SimpleDocTemplate(buf, pagesize=A4,
                                 leftMargin=2*cm, rightMargin=2*cm,
                                 topMargin=2*cm,  bottomMargin=2*cm)
    T  = lambda s,**kw: ParagraphStyle(s, **kw)
    st = {
        'title':     T('t', fontSize=20, fontName='Helvetica-Bold',
                        textColor=colors.HexColor('#1a1a2e'), spaceAfter=4),
        'sub':       T('s', fontSize=10, fontName='Helvetica',
                        textColor=colors.HexColor('#666'), spaceAfter=16),
        'doc_title': T('dt', fontSize=14, fontName='Helvetica-Bold',
                        spaceAfter=6, spaceBefore=14),
        'img_label': T('il', fontSize=9, fontName='Helvetica',
                        textColor=colors.HexColor('#666'), spaceAfter=4, spaceBefore=8),
    }
    story = [
        Paragraph(title, st['title']),
        Paragraph(f"Digenerate pada {date.today().strftime('%d %B %Y')}", st['sub']),
        HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#e2e8f0')),
        Spacer(1, .4*cm),
    ]
    for d in docs:
        story.append(Paragraph(
            f"<b>{d.name}</b>  <font color='#666' size='10'>({d.doc_type})</font>",
            st['doc_title']))
        sc   = STATUS_COLORS[d.status]
        data = [
            ['Field','Detail'],
            ['Pemilik',         d.person_name or '\u2014'],
            ['No. Dokumen',     d.doc_number  or '\u2014'],
            ['Tanggal Terbit',  d.issued_date.strftime('%d %b %Y') if d.issued_date else '\u2014'],
            ['Berlaku s/d',     d.expiry_date.strftime('%d %b %Y')],
            ['Sisa Hari',       f"{d.days_left} hari" if d.days_left>=0 else f"Lewat {abs(d.days_left)} hari"],
            ['Status',          d.status_label],
            ['Catatan',         d.notes or '\u2014'],
        ]
        tbl = Table(data, colWidths=[4.5*cm, PAGE_W-4.5*cm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(1,0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR',     (0,0),(1,0), colors.white),
            ('FONTNAME',      (0,0),(1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0),(-1,-1), 9),
            ('FONTNAME',      (0,1),(0,-1), 'Helvetica-Bold'),
            ('BACKGROUND',    (0,1),(0,-1), colors.HexColor('#f8fafc')),
            ('ROWBACKGROUNDS',(1,1),(1,-1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID',          (0,0),(-1,-1), .5, colors.HexColor('#e2e8f0')),
            ('PADDING',       (0,0),(-1,-1), 6),
            ('TEXTCOLOR',     (1,6),(1,6), sc),
            ('FONTNAME',      (1,6),(1,6), 'Helvetica-Bold'),
        ]))
        story.append(tbl)
        imgs = [f for f in d.files if not f.lower().endswith('.pdf')]
        if imgs:
            story.append(Paragraph('Scan / Foto Dokumen:', st['img_label']))
            for fn in imgs:
                img = image_flowable(fn, PAGE_W, 14*cm)
                if img:
                    story.append(img)
                    story.append(Spacer(1, .2*cm))
        story += [Spacer(1, .5*cm),
                  HRFlowable(width='100%', thickness=.5, color=colors.HexColor('#e2e8f0'))]
    doc_tpl.build(story)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── Landing ───────────────────────────────────────────────────────────────────
@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/')
def root():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return redirect(url_for('landing'))

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email'].lower().strip()
        if User.query.filter_by(email=email).first():
            flash('Email sudah terdaftar.', 'danger')
            return redirect(url_for('register'))
        user = User(name=request.form['name'], email=email)
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Selamat datang, {user.name}! 🎉', 'success')
        return redirect(url_for('index'))
    return render_template('auth.html', mode='register')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email'].lower().strip()).first()
        if user and user.check_password(request.form['password']):
            login_user(user, remember=request.form.get('remember'))
            return redirect(request.args.get('next') or url_for('index'))
        flash('Email atau password salah.', 'danger')
    return render_template('auth.html', mode='login')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route('/app')
@login_required
def index():
    docs   = Document.query.filter_by(user_id=current_user.id).order_by(Document.expiry_date).all()
    stats  = {k: sum(1 for d in docs if d.status==k)
              for k in ('active','warning','critical','expired')}
    stats['total'] = len(docs)
    urgent = [d for d in docs if d.status in ('critical','expired')]
    return render_template('index.html', docs=docs, stats=stats,
                           urgent=urgent, today=date.today())

# ── Documents CRUD ─────────────────────────────────────────────────────────────
@app.route('/app/add', methods=['GET','POST'])
@login_required
def add():
    if request.method == 'POST':
        issued_raw = request.form.get('issued_date')
        files = handle_uploads()
        doc = Document(
            user_id     = current_user.id,
            name        = request.form['name'],
            doc_type    = request.form['doc_type'],
            doc_number  = request.form.get('doc_number',''),
            person_name = request.form.get('owner',''),
            issued_date = datetime.strptime(issued_raw,'%Y-%m-%d').date() if issued_raw else None,
            expiry_date = datetime.strptime(request.form['expiry_date'],'%Y-%m-%d').date(),
            notes       = request.form.get('notes',''),
            file_paths  = '\n'.join(files),
        )
        db.session.add(doc)
        db.session.commit()
        flash('Dokumen berhasil ditambahkan!', 'success')
        return redirect(url_for('index'))
    return render_template('add.html', doc_types=DOC_TYPES)

@app.route('/app/edit/<int:doc_id>', methods=['GET','POST'])
@login_required
def edit(doc_id):
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        issued_raw = request.form.get('issued_date')
        to_delete  = request.form.getlist('delete_file')
        kept       = [f for f in doc.files if f not in to_delete]
        delete_uploads(to_delete)
        kept = handle_uploads(existing=kept)
        doc.name        = request.form['name']
        doc.doc_type    = request.form['doc_type']
        doc.doc_number  = request.form.get('doc_number','')
        doc.person_name = request.form.get('owner','')
        doc.issued_date = datetime.strptime(issued_raw,'%Y-%m-%d').date() if issued_raw else None
        doc.expiry_date = datetime.strptime(request.form['expiry_date'],'%Y-%m-%d').date()
        doc.notes       = request.form.get('notes','')
        doc.file_paths  = '\n'.join(kept)
        db.session.commit()
        flash('Dokumen berhasil diperbarui!', 'success')
        return redirect(url_for('index'))
    return render_template('edit.html', doc=doc, doc_types=DOC_TYPES)

@app.route('/app/delete/<int:doc_id>', methods=['POST'])
@login_required
def delete(doc_id):
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    delete_uploads(doc.files)
    db.session.delete(doc)
    db.session.commit()
    flash('Dokumen berhasil dihapus.', 'info')
    return redirect(url_for('index'))

# ── File serving ──────────────────────────────────────────────────────────────
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    if app.config['USE_CLOUDINARY']:
        from flask import redirect as redir
        return redir(get_upload_url(filename))
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

# ── Export PDF ────────────────────────────────────────────────────────────────
@app.route('/app/export/pdf/<int:doc_id>')
@login_required
def export_pdf_single(doc_id):
    doc = Document.query.filter_by(id=doc_id, user_id=current_user.id).first_or_404()
    pdf = generate_pdf([doc], f"DocuReminder \u2014 {doc.name}")
    return send_file(pdf, mimetype='application/pdf', as_attachment=True,
                     download_name=f"{doc.name.replace(' ','_')}.pdf")

@app.route('/app/export/pdf/all')
@login_required
def export_pdf_all():
    docs = Document.query.filter_by(user_id=current_user.id).order_by(Document.expiry_date).all()
    pdf  = generate_pdf(docs, "DocuReminder \u2014 Semua Dokumen")
    return send_file(pdf, mimetype='application/pdf', as_attachment=True,
                     download_name="DocuReminder_Semua.pdf")

# ── Settings ──────────────────────────────────────────────────────────────────
@app.route('/app/settings', methods=['GET','POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.gmail_address      = request.form.get('gmail_address','').strip()
        current_user.gmail_app_password = request.form.get('gmail_app_password','').strip()
        current_user.notify_days        = request.form.get('notify_days','90,30,7,1')
        current_user.email_notify       = bool(request.form.get('email_notify'))
        current_user.push_notify        = bool(request.form.get('push_notify'))
        # password change
        new_pw = request.form.get('new_password','').strip()
        if new_pw:
            if current_user.check_password(request.form.get('current_password','')):
                current_user.set_password(new_pw)
            else:
                flash('Password saat ini salah.', 'danger')
                return redirect(url_for('settings'))
        db.session.commit()
        flash('Pengaturan disimpan!', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html')

# ── Test notifications ─────────────────────────────────────────────────────────
@app.route('/app/notify/test/email')
@login_required
def test_email():
    if not (current_user.gmail_address and current_user.gmail_app_password):
        flash('Isi Gmail settings dulu di halaman Pengaturan.', 'danger')
        return redirect(url_for('settings'))
    docs = Document.query.filter_by(user_id=current_user.id).limit(3).all()
    ok   = send_email(
        current_user.gmail_address, current_user.gmail_app_password,
        current_user.email,
        'DocuReminder — Test Email Notifikasi',
        email_html(current_user.name, docs or []),
    )
    flash('Email test berhasil dikirim! ✅' if ok else 'Gagal kirim email. Cek Gmail settings.', 'success' if ok else 'danger')
    return redirect(url_for('settings'))

# ── Push subscription API ──────────────────────────────────────────────────────
@app.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json()
    sub  = PushSubscription(
        user_id  = current_user.id,
        endpoint = data['endpoint'],
        p256dh   = data['keys']['p256dh'],
        auth     = data['keys']['auth'],
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    data = request.get_json()
    PushSubscription.query.filter_by(
        user_id=current_user.id, endpoint=data.get('endpoint')).delete()
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/api/push/test')
@login_required
def push_test():
    subs = PushSubscription.query.filter_by(user_id=current_user.id).all()
    if not subs:
        return jsonify({'ok': False, 'msg': 'Tidak ada push subscription aktif.'})
    results = [send_push(s, '🔔 DocuReminder', 'Push notification berhasil! ✅', '/app') for s in subs]
    return jsonify({'ok': any(results)})

@app.route('/api/vapid-public-key')
def vapid_public_key():
    return jsonify({'key': app.config['VAPID_PUBLIC_KEY']})

# ── Service Worker ─────────────────────────────────────────────────────────────
@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js'), 200, {'Content-Type': 'application/javascript'}

# ── Bootstrap ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)

# Auto-create tables on startup
import logging
with app.app_context():
    try:
        db.create_all()
        logging.info("DB tables created OK")
    except Exception as e:
        logging.error(f"DB create_all failed: {e}")
