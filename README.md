# ☁️ CloudVault – Enhanced File Management System

A full-stack file management system with user/admin dashboards, profile pictures, storage quotas, activity logs, and more.

---

## 📁 Project Structure

```
FileManagementSystem/
├── backend/
│   ├── server.py          ← Python HTTP server (all API endpoints)
│   └── uploads/           ← Uploaded files stored here
├── frontend/
│   ├── index.html         ← Login + Register page
│   ├── dashboard.html     ← User dashboard
│   └── admin.html         ← Admin panel
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure MongoDB

Open `backend/server.py` and update the `MONGO_URI` at line ~14:

- **Local MongoDB**: `"mongodb://localhost:27017/"`
- **MongoDB Atlas**: `"mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority"`

### 3. Start the backend

```bash
cd backend
python server.py
```

You should see:
```
✅ Connected to MongoDB
🚀 Server running at http://localhost:8000
```

### 4. Open the frontend

Open `frontend/index.html` in your browser (double-click it or use Live Server in VS Code).

---

## 👑 First Admin Setup

After starting the server, run this one-time script to create your first admin:

```bash
python - <<'EOF'
from pymongo import MongoClient
import bcrypt, datetime

MONGO_URI = "mongodb://localhost:27017/"  # update this
client = MongoClient(MONGO_URI)
db = client["cloud_system"]

hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
db["users"].insert_one({
    "username": "admin",
    "password": hashed,
    "role": "admin",
    "email": "admin@example.com",
    "display_name": "Administrator",
    "profile_pic": "",
    "storage_quota": 1073741824,
    "created_at": datetime.datetime.utcnow().isoformat()
})
print("✅ Admin created: admin / admin123")
EOF
```

Then log in with `admin` / `admin123`.

---

## ✨ New Features Added

### 👤 User Dashboard
| Feature | Description |
|---|---|
| **Profile Picture** | Upload & display a custom avatar (stored as base64) |
| **Storage Meter** | Visual bar showing used/free/total storage with color warning |
| **Overview Stats** | Total files, images, docs, shared files at a glance |
| **File Sharing** | Toggle any file as public, auto-copies share link to clipboard |
| **Activity Log** | Personal history: logins, uploads, deletes, profile changes |
| **Grid/List View** | Toggle between card grid and compact list view |
| **Filter by Type** | Filter files: All / Images / PDFs / Videos / Docs / Shared |
| **Change Password** | Secure password change from Settings tab |
| **Edit Profile** | Update display name and email |
| **Upload Progress** | Real-time progress bar per file during upload |
| **Search** | Live search across your files |

### 👑 Admin Panel
| Feature | Description |
|---|---|
| **System Overview** | Total users, admins, files, storage across the platform |
| **Recent Users** | See newly joined users on the overview page |
| **Add User** | Create users with specific role and quota from the UI |
| **Storage Quota Control** | Slider to set per-user storage quota (10 MB – 10 GB) |
| **Role Management** | Promote/demote users between user ↔ admin with one click |
| **Delete User** | Deletes user + all their files at once |
| **All Files View** | Browse every file on the system with owner, size, share status |
| **Admin Delete** | Delete any file from the admin panel |
| **Activity Log** | System-wide log: who did what and when |
| **Profile in Sidebar** | Admin sees their own avatar in the sidebar |

### 🔧 Backend Improvements
| Improvement | Description |
|---|---|
| **Per-user file ownership** | Files are tagged with their owner |
| **Storage tracking** | Real-time used/quota per user via MongoDB aggregation |
| **Activity logging** | All key actions logged to `activity` collection |
| **Filename deduplication** | Prevents overwriting existing files (appends `_1`, `_2`, etc.) |
| **Quota enforcement** | Upload blocked if it would exceed user's quota |
| **Toggle share endpoint** | `PUT /toggle-share` toggles file public/private |
| **Profile update endpoint** | `POST /update-profile` saves display name, email, avatar |
| **Change password endpoint** | `POST /change-password` with old password verification |
| **Admin stats endpoint** | `GET /stats` returns system-wide counts |
| **Per-user file list** | `GET /files?owner=username` returns only that user's files |

---

## 🌐 API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/login` | Authenticate user |
| POST | `/register` | Register new user |
| POST | `/upload` | Upload file(s) (multipart, send `owner` field) |
| POST | `/delete` | Delete a file |
| POST | `/delete-user` | Delete a user + their files |
| POST | `/update-profile` | Update display name / email / avatar |
| POST | `/change-password` | Change password (requires old password) |
| POST | `/update-quota` | Set storage quota for a user |
| POST | `/update-role` | Change user role |
| PUT | `/toggle-share` | Toggle file sharing on/off |
| GET | `/files?owner=X` | List files (filter by owner) |
| GET | `/users` | List all users with storage stats |
| GET | `/storage?username=X` | Get storage usage for a user |
| GET | `/stats` | Admin system statistics |
| GET | `/activity?username=X&limit=N` | Activity log |
| GET | `/profile?username=X` | Get user profile |
| GET | `/uploads/<filename>` | Download/serve a file |
| GET | `/health` | Health check |

---

## 🐛 Troubleshooting

**"Cannot connect to server"** → Make sure `python server.py` is running in the `backend/` folder.

**MongoDB connection fails** → Check your `MONGO_URI` in `server.py`. For Atlas, ensure your IP is whitelisted.

**Files not appearing after upload** → Check the browser console; verify the server is running on port 8000.

**Profile picture not saving** → Images must be under 2 MB. The avatar is stored as a base64 data URL in MongoDB.

**Quota not enforced** → Quota is checked on upload. If a user had files before quotas were added, run `loadStorage()` on their next login.
