from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import smtplib, os, shutil, json, uuid, random, string
from email.mime.text import MIMEText

load_dotenv()
EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")

UPLOAD_DIR = "uploads"
META_FILE = "files.json"
STATS_FILE = "downloads.json"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load metadata
if os.path.exists(META_FILE):
    with open(META_FILE, 'r') as f:
        files = json.load(f)
else:
    files = {}

if os.path.exists(STATS_FILE):
    with open(STATS_FILE, 'r') as f:
        stats = json.load(f)
else:
    stats = {}

def generate_short_id(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def send_email(to_email, download_link):
    msg = MIMEText(f"Your file has been uploaded.\nDownload it here: {download_link}")
    msg['Subject'] = 'Your File Upload Link'
    msg['From'] = EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL, PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Email send error:", e)

@app.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...), email: str = Form(...)):
    short_id = generate_short_id()
    file_path = os.path.join(UPLOAD_DIR, short_id + "_" + file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    files[short_id] = {"filename": file.filename, "email": email}
    with open(META_FILE, 'w') as f:
        json.dump(files, f)

    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto", "http")
    host = forwarded_host or request.client.host
    full_link = f"{proto}://{host}/f/{short_id}"

    send_email(email, full_link)

    return (
        "<html>"
        "<head>"
        "<link rel='stylesheet' href='/static/style.css'>"
        "<title>Link Generated</title>"
        "</head>"
        "<body>"
        "<div class='container'>"
        "<h1>✅ Upload Successful!</h1>"
        "<p>Here is your download link:</p>"
        f"<input type='text' value='{full_link}' id='link' readonly style='width:100%; padding:10px; font-size:16px;'/>"
        "<br><br>"
        "<button class='btn' onclick=\"copyLink()\">📋 Copy the Link</button>"
        "</div>"
        "<script>"
        "function copyLink() {"
        "  var copyText = document.getElementById('link');"
        "  copyText.select();"
        "  copyText.setSelectionRange(0, 99999);"
        "  document.execCommand('copy');"
        "  alert('Copied the link: ' + copyText.value);"
        "}"
        "</script>"
        "</body>"
        "</html>"
    )

@app.get("/f/{short_id}", response_class=HTMLResponse)
async def download_page(short_id: str):
    if short_id in files:
        filename = files[short_id]["filename"]
        stats.setdefault(short_id, {"downloads": 0, "last": None})
        stats[short_id]["downloads"] += 1
        stats[short_id]["last"] = str(requests.utils.default_headers()['User-Agent'])
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f)
        return f"""
        <html>
        <head>
            <link rel='stylesheet' href='/static/style.css'>
            <title>Download {filename}</title>
        </head>
        <body>
            <div class='container'>
                <h1>📦 File Ready to Download</h1>
                <p><strong>File:</strong> {filename}</p>
                <a class='btn' href='/download/{short_id}'>⬇️ Download File</a>
            </div>
        </body>
        </html>
        """
    return HTMLResponse("<h1>File not found</h1>", status_code=404)

@app.get("/download/{short_id}")
async def download_file(short_id: str):
    if short_id in files:
        filename = files[short_id]["filename"]
        file_path = os.path.join(UPLOAD_DIR, short_id + "_" + filename)
        return FileResponse(path=file_path, filename=filename)
    return {"error": "File not found"}

@app.get("/admin", response_class=HTMLResponse)
def admin():
    html = """
    <html><head><title>Admin Panel</title>
    <link rel='stylesheet' href='/static/style.css'>
    </head><body><div class='container'>
    <h1>📊 Admin Panel</h1>
    <table border='1' style='width:100%;background:white;color:black'>
    <tr><th>File</th><th>Email</th><th>Downloads</th><th>Last Access</th></tr>
    """
    for sid in files:
        filename = files[sid]["filename"]
        email = files[sid]["email"]
        count = stats.get(sid, {}).get("downloads", 0)
        last = stats.get(sid, {}).get("last", "-")
        html += f"<tr><td>{filename}</td><td>{email}</td><td>{count}</td><td>{last}</td></tr>"
    html += "</table></div></body></html>"
    return html

@app.get("/", response_class=HTMLResponse)
def main():
    return """
    <html>
    <head>
        <link rel='stylesheet' href='/static/style.css'>
        <title>Upload Files</title>
    </head>
    <body>
        <div class='container'>
            <h1>🚀 Share Files Instantly</h1>
            <form action="/upload" enctype="multipart/form-data" method="post">
                <input type="file" name="file" required/><br>
                <input type="email" name="email" placeholder="Your email" required/><br>
                <input type="submit" value="Upload & Get Link" class='btn'/>
            </form>
        </div>
    </body>
    </html>
    """
