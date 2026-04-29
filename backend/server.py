import json
import os
import mimetypes
import base64
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pymongo import MongoClient
import bcrypt

# ================= CONFIG =================
PORT = 8000
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
PROFILE_DIR = os.path.join(os.path.dirname(__file__), "profiles")
MAX_STORAGE_BYTES = 100 * 1024 * 1024  # 100 MB per user default

# ---- UPDATE THIS WITH YOUR MONGODB URI ----
MONGO_URI = "mongodb://gunjankokate76_db_user:rqaMoTOhvrBmkV2N@ac-icpkyup-shard-00-00.i7e69ra.mongodb.net:27017,ac-icpkyup-shard-00-01.i7e69ra.mongodb.net:27017,ac-icpkyup-shard-00-02.i7e69ra.mongodb.net:27017/?ssl=true&replicaSet=atlas-12is4c-shard-0&authSource=admin&appName=Cluster1"
# For Atlas use something like:
# MONGO_URI = "mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    db = client["cloud_system"]
    users_col   = db["users"]
    files_col   = db["files"]
    activity_col = db["activity"]
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    exit(1)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROFILE_DIR, exist_ok=True)

# ================= HELPERS =================
def send_json(handler, data, status=200):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", len(body))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Credentials", "true")
    handler.end_headers()
    handler.wfile.write(body)

def send_error(handler, message, status=400):
    send_json(handler, {"status": "error", "message": message}, status)

def get_file_type(filename):
    mime, _ = mimetypes.guess_type(filename)
    if mime:
        if mime.startswith("image"): return "image"
        if mime.startswith("video"): return "video"
        if mime.startswith("audio"): return "audio"
        if mime == "application/pdf": return "pdf"
        if "word" in mime or "document" in mime: return "doc"
        if "sheet" in mime or "excel" in mime: return "sheet"
        if "zip" in mime or "compressed" in mime: return "archive"
    return "file"

def log_activity(username, action, detail=""):
    activity_col.insert_one({
        "username": username,
        "action": action,
        "detail": detail,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

def get_user_storage(username):
    """Return total bytes used by a user."""
    result = files_col.aggregate([
        {"$match": {"owner": username}},
        {"$group": {"_id": None, "total": {"$sum": "$size"}}}
    ])
    r = list(result)
    return r[0]["total"] if r else 0

def get_storage_quota(username):
    user = users_col.find_one({"username": username})
    return user.get("storage_quota", MAX_STORAGE_BYTES) if user else MAX_STORAGE_BYTES

def parse_query(path):
    params = {}
    if "?" in path:
        _, qs = path.split("?", 1)
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
    return params

# ================= SERVER =================
class MyServer(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ================= POST =================
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")
        path = self.path.split("?")[0]

        # ---------- JSON REQUESTS ----------
        if "application/json" in content_type:
            try:
                data = json.loads(self.rfile.read(content_length))
            except Exception:
                return send_error(self, "Invalid JSON")

            # LOGIN
            if path == "/login":
                username = data.get("username", "").strip()
                password = data.get("password", "")
                if not username or not password:
                    return send_error(self, "Missing credentials")
                user = users_col.find_one({"username": username})
                if user and bcrypt.checkpw(password.encode(), user["password"]):
                    used = get_user_storage(username)
                    quota = user.get("storage_quota", MAX_STORAGE_BYTES)
                    profile_pic = user.get("profile_pic", "")
                    log_activity(username, "login")
                    send_json(self, {
                        "status": "success",
                        "role": user.get("role", "user"),
                        "username": username,
                        "storage_used": used,
                        "storage_quota": quota,
                        "profile_pic": profile_pic,
                        "display_name": user.get("display_name", username),
                        "email": user.get("email", "")
                    })
                else:
                    send_json(self, {"status": "fail", "message": "Invalid username or password"})

            # REGISTER
            elif path == "/register":
                username = data.get("username", "").strip()
                password = data.get("password", "")
                email    = data.get("email", "").strip()
                role     = data.get("role", "user")
                if not username or not password:
                    return send_error(self, "Missing fields")
                if users_col.find_one({"username": username}):
                    return send_json(self, {"status": "exists", "message": "Username already taken"})
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
                users_col.insert_one({
                    "username": username,
                    "password": hashed,
                    "role": role,
                    "email": email,
                    "display_name": username,
                    "profile_pic": "",
                    "storage_quota": MAX_STORAGE_BYTES,
                    "created_at": datetime.datetime.utcnow().isoformat()
                })
                log_activity(username, "register")
                send_json(self, {"status": "registered"})

            # UPDATE PROFILE
            elif path == "/update-profile":
                username = data.get("username", "")
                if not username:
                    return send_error(self, "Missing username")
                update_fields = {}
                if "display_name" in data: update_fields["display_name"] = data["display_name"]
                if "email" in data: update_fields["email"] = data["email"]
                if "profile_pic" in data: update_fields["profile_pic"] = data["profile_pic"]  # base64 data URL
                if update_fields:
                    users_col.update_one({"username": username}, {"$set": update_fields})
                    log_activity(username, "update_profile")
                send_json(self, {"status": "updated"})

            # CHANGE PASSWORD
            elif path == "/change-password":
                username  = data.get("username", "")
                old_pass  = data.get("old_password", "")
                new_pass  = data.get("new_password", "")
                if not username or not old_pass or not new_pass:
                    return send_error(self, "Missing fields")
                user = users_col.find_one({"username": username})
                if not user or not bcrypt.checkpw(old_pass.encode(), user["password"]):
                    return send_error(self, "Current password is incorrect")
                hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt())
                users_col.update_one({"username": username}, {"$set": {"password": hashed}})
                log_activity(username, "change_password")
                send_json(self, {"status": "password_changed"})

            # DELETE FILE
            elif path == "/delete":
                filename = data.get("name", "")
                username = data.get("username", "")
                if not filename:
                    return send_error(self, "Missing filename")
                filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
                if os.path.exists(filepath):
                    os.remove(filepath)
                files_col.delete_one({"name": filename})
                log_activity(username, "delete_file", filename)
                send_json(self, {"status": "deleted"})

            # DELETE USER (admin)
            elif path == "/delete-user":
                username = data.get("username", "")
                if not username:
                    return send_error(self, "Missing username")
                # Also delete their files
                user_files = list(files_col.find({"owner": username}, {"name": 1}))
                for f in user_files:
                    fp = os.path.join(UPLOAD_DIR, os.path.basename(f["name"]))
                    if os.path.exists(fp):
                        os.remove(fp)
                files_col.delete_many({"owner": username})
                users_col.delete_one({"username": username})
                log_activity("admin", "delete_user", username)
                send_json(self, {"status": "user deleted"})

            # UPDATE USER QUOTA (admin)
            elif path == "/update-quota":
                username = data.get("username", "")
                quota    = data.get("quota", MAX_STORAGE_BYTES)
                if not username:
                    return send_error(self, "Missing username")
                users_col.update_one({"username": username}, {"$set": {"storage_quota": int(quota)}})
                log_activity("admin", "update_quota", f"{username} -> {quota}")
                send_json(self, {"status": "quota updated"})

            # UPDATE USER ROLE (admin)
            elif path == "/update-role":
                username = data.get("username", "")
                role     = data.get("role", "user")
                if not username:
                    return send_error(self, "Missing username")
                users_col.update_one({"username": username}, {"$set": {"role": role}})
                log_activity("admin", "update_role", f"{username} -> {role}")
                send_json(self, {"status": "role updated"})

            else:
                send_error(self, "Unknown endpoint", 404)

        # ---------- FILE UPLOAD ----------
        elif "multipart/form-data" in content_type:
            if path != "/upload":
                return send_error(self, "Wrong endpoint", 404)
            try:
                boundary = content_type.split("boundary=")[1].strip().encode()
                body = self.rfile.read(content_length)
                parts = body.split(b"--" + boundary)
                uploaded = []
                owner = ""

                for part in parts:
                    if b'name="owner"' in part and b'filename="' not in part:
                        if b"\r\n\r\n" in part:
                            owner = part.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n--").decode("utf-8")
                        continue
                    if b'filename="' not in part:
                        continue
                    if b"\r\n\r\n" not in part:
                        continue

                    header_raw, file_data = part.split(b"\r\n\r\n", 1)
                    file_data = file_data.rstrip(b"\r\n--")
                    filename_raw = header_raw.split(b'filename="')[1].split(b'"')[0]
                    filename = filename_raw.decode("utf-8")
                    safe_name = os.path.basename(filename)
                    if not safe_name:
                        continue

                    # Check quota
                    if owner:
                        used  = get_user_storage(owner)
                        quota = get_storage_quota(owner)
                        if used + len(file_data) > quota:
                            send_json(self, {"status": "error", "message": "Storage quota exceeded"})
                            return

                    filepath = os.path.join(UPLOAD_DIR, safe_name)
                    # Avoid name collision
                    base, ext = os.path.splitext(safe_name)
                    counter = 1
                    while os.path.exists(filepath):
                        safe_name = f"{base}_{counter}{ext}"
                        filepath = os.path.join(UPLOAD_DIR, safe_name)
                        counter += 1

                    with open(filepath, "wb") as f:
                        f.write(file_data)

                    fsize = len(file_data)
                    ftype = get_file_type(safe_name)
                    url   = f"http://localhost:{PORT}/uploads/{safe_name}"
                    now   = datetime.datetime.utcnow().isoformat()

                    files_col.delete_one({"name": safe_name})
                    files_col.insert_one({
                        "name": safe_name,
                        "type": ftype,
                        "url": url,
                        "size": fsize,
                        "owner": owner,
                        "uploaded_at": now,
                        "shared": False
                    })
                    uploaded.append(safe_name)
                    if owner:
                        log_activity(owner, "upload", safe_name)

                send_json(self, {"status": "uploaded", "files": uploaded})
            except Exception as e:
                print(f"Upload error: {e}")
                send_error(self, f"Upload failed: {str(e)}")
        else:
            send_error(self, "Unsupported Content-Type", 415)

    # ================= PUT =================
    def do_PUT(self):
        content_length = int(self.headers.get("Content-Length", 0))
        content_type   = self.headers.get("Content-Type", "")
        path = self.path.split("?")[0]

        if "application/json" in content_type:
            try:
                data = json.loads(self.rfile.read(content_length))
            except Exception:
                return send_error(self, "Invalid JSON")

            # TOGGLE SHARE
            if path == "/toggle-share":
                filename = data.get("name", "")
                username = data.get("username", "")
                if not filename:
                    return send_error(self, "Missing filename")
                f = files_col.find_one({"name": filename})
                if not f:
                    return send_error(self, "File not found")
                new_shared = not f.get("shared", False)
                files_col.update_one({"name": filename}, {"$set": {"shared": new_shared}})
                log_activity(username, "toggle_share", f"{filename} -> {'shared' if new_shared else 'private'}")
                send_json(self, {"status": "ok", "shared": new_shared})
            else:
                send_error(self, "Unknown endpoint", 404)
        else:
            send_error(self, "Unsupported Content-Type", 415)

    # ================= GET =================
    def do_GET(self):
        path = self.path.split("?")[0]
        params = parse_query(self.path)

        # FILES LIST (by owner or all for admin)
        if path == "/files":
            owner = params.get("owner", "")
            if owner:
                file_list = list(files_col.find({"owner": owner}, {"_id": 0}))
            else:
                file_list = list(files_col.find({}, {"_id": 0}))
            return send_json(self, file_list)

        # USERS LIST
        elif path == "/users":
            user_list = []
            for u in users_col.find({}, {"_id": 0, "password": 0}):
                u["storage_used"] = get_user_storage(u["username"])
                u["file_count"]   = files_col.count_documents({"owner": u["username"]})
                user_list.append(u)
            return send_json(self, user_list)

        # STORAGE INFO for a user
        elif path == "/storage":
            username = params.get("username", "")
            if not username:
                return send_error(self, "Missing username")
            used  = get_user_storage(username)
            quota = get_storage_quota(username)
            count = files_col.count_documents({"owner": username})
            return send_json(self, {"used": used, "quota": quota, "count": count})

        # ACTIVITY LOG
        elif path == "/activity":
            username = params.get("username", "")
            limit    = int(params.get("limit", 20))
            if username:
                logs = list(activity_col.find({"username": username}, {"_id": 0}).sort("timestamp", -1).limit(limit))
            else:
                logs = list(activity_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
            return send_json(self, logs)

        # ADMIN STATS
        elif path == "/stats":
            total_users  = users_col.count_documents({})
            total_files  = files_col.count_documents({})
            total_admins = users_col.count_documents({"role": "admin"})
            size_result  = list(files_col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$size"}}}]))
            total_size   = size_result[0]["total"] if size_result else 0
            recent_users = list(users_col.find({}, {"_id": 0, "password": 0}).sort("created_at", -1).limit(5))
            return send_json(self, {
                "total_users": total_users,
                "total_files": total_files,
                "total_admins": total_admins,
                "total_size": total_size,
                "recent_users": recent_users
            })

        # USER PROFILE
        elif path == "/profile":
            username = params.get("username", "")
            if not username:
                return send_error(self, "Missing username")
            user = users_col.find_one({"username": username}, {"_id": 0, "password": 0})
            if not user:
                return send_error(self, "User not found", 404)
            user["storage_used"] = get_user_storage(username)
            user["file_count"]   = files_col.count_documents({"owner": username})
            return send_json(self, user)

        # SERVE UPLOADED FILES
        elif path.startswith("/uploads/"):
            filename = os.path.basename(path)
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(filepath):
                mime, _ = mimetypes.guess_type(filepath)
                mime = mime or "application/octet-stream"
                with open(filepath, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", len(content))
                self.send_header("Content-Disposition", f'inline; filename="{filename}"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()

        # HEALTH
        elif path == "/health":
            send_json(self, {"status": "ok"})

        else:
            self.send_response(404)
            self.end_headers()

# ================= RUN =================
if __name__ == "__main__":
    print(f"🚀 Server running at http://localhost:{PORT}")
    print("   Press Ctrl+C to stop")
    server = HTTPServer(("0.0.0.0", PORT), MyServer)
    server.serve_forever()
